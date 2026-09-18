"""Unitarias de los 4 consumers de WebSocket de concensus: GroupConsumer,
PhaseTwoConsumer, PhaseThreeConsumer (mismo patron: join al grupo + contador
de conexiones en Redis) y ChatConsumer (auth + expiracion del debate +
mensajes iniciales + broadcast de mensajes nuevos).

Usa channels.layers.InMemoryChannelLayer en vez del Redis real (mas rapido,
sin flakiness de red) y mockea redis.StrictRedis para el contador de
conexiones, que es un cliente Redis aparte del channel layer.

Nota sobre el runner async elegido por clase (no es intercambiable):
- TestGroupLikeConsumers usa asyncio.run(): esos 3 consumers llaman
  async_to_sync(channel_layer.group_send) DENTRO de un metodo ya envuelto en
  sync_to_async: si el test tambien usara asgiref.sync.async_to_sync como
  runner externo, esa segunda capa de async_to_sync choca con la primera en
  el mismo CurrentThreadExecutor de asgiref y hace deadlock.
- TestChatConsumer usa asgiref.sync.async_to_sync(): ChatConsumer solo hace
  sync_to_async (sin async_to_sync anidado), pero SI necesita que esas
  consultas a la DB compartan el hilo/conexion de la transaccion de
  TestCase; con asyncio.run() (un event loop nuevo y ajeno) el
  sync_to_async(thread_sensitive=True) se despacha a otro hilo que no ve la
  transaccion todavia sin commit, y Debate.objects.get() falla con
  DoesNotExist."""

import asyncio
from datetime import timedelta
from unittest.mock import MagicMock, patch

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.test import TestCase, override_settings

from apps.concensus.consumer import GroupConsumer
from apps.concensus.consumer_phase_three import PhaseThreeConsumer
from apps.concensus.consumer_phase_two import PhaseTwoConsumer
from apps.concensus.debate_consumer import ChatConsumer
from apps.concensus.domain.entities.debate import Debate
from apps.concensus.domain.entities.debate_message import Message
from apps.custom_auth.identity_principal import IdentityPrincipal

IN_MEMORY_LAYER = override_settings(
    CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
)


def _mock_redis_client():
    client = MagicMock()
    client.get.return_value = None
    return client


@IN_MEMORY_LAYER
class TestGroupLikeConsumers(TestCase):
    """Los 3 consumers de conteo de conexiones comparten exactamente el mismo
    comportamiento (solo cambia el nombre del grupo y la clase)."""

    def _connect(self, consumer_cls, group_id="g1"):
        async def _run():
            communicator = WebsocketCommunicator(consumer_cls.as_asgi(), "/ws/")
            communicator.scope["url_route"] = {"kwargs": {"group_id": group_id}}
            with patch(
                f"{consumer_cls.__module__}.redis.StrictRedis",
                return_value=_mock_redis_client(),
            ):
                connected, _ = await communicator.connect()
            return communicator, connected

        return asyncio.run(_run())

    def test_group_consumer_acepta_conexion(self):
        communicator, connected = self._connect(GroupConsumer)
        self.assertTrue(connected)
        asyncio.run(communicator.disconnect())

    def test_phase_two_consumer_acepta_conexion(self):
        communicator, connected = self._connect(PhaseTwoConsumer)
        self.assertTrue(connected)
        asyncio.run(communicator.disconnect())

    def test_phase_three_consumer_acepta_conexion(self):
        communicator, connected = self._connect(PhaseThreeConsumer)
        self.assertTrue(connected)
        asyncio.run(communicator.disconnect())

    def test_group_message_reenvia_por_el_websocket(self):
        async def _run():
            communicator = WebsocketCommunicator(GroupConsumer.as_asgi(), "/ws/")
            communicator.scope["url_route"] = {"kwargs": {"group_id": "g1"}}
            with patch(
                "apps.concensus.consumer.redis.StrictRedis",
                return_value=_mock_redis_client(),
            ):
                await communicator.connect()
                # connect() ya dispara su propio group_send de connection_count;
                # hay que drenarlo antes de mandar el mensaje que nos interesa.
                await communicator.receive_json_from()
                from channels.layers import get_channel_layer

                channel_layer = get_channel_layer()
                await channel_layer.group_send(
                    "group_g1",
                    {"type": "group_message", "message": {"hello": "world"}},
                )
                response = await communicator.receive_json_from()
                await communicator.disconnect()
            return response

        response = asyncio.run(_run())
        self.assertEqual(response["message"], {"hello": "world"})

    def _increment_and_decrement(self, consumer_cls, group_id="g1"):
        async def _run():
            redis_client = _mock_redis_client()
            communicator = WebsocketCommunicator(consumer_cls.as_asgi(), "/ws/")
            communicator.scope["url_route"] = {"kwargs": {"group_id": group_id}}
            with patch(
                f"{consumer_cls.__module__}.redis.StrictRedis",
                return_value=redis_client,
            ):
                await communicator.connect()
                await communicator.disconnect()
            return redis_client

        return asyncio.run(_run())

    def test_increment_and_decrement_actualizan_redis(self):
        redis_client = self._increment_and_decrement(GroupConsumer)
        # increment (connect) escribe 1, decrement (disconnect) escribe 0
        set_calls = [call.args[1] for call in redis_client.set.call_args_list]
        self.assertEqual(set_calls, [1, 0])

    def test_phase_two_increment_and_decrement_actualizan_redis(self):
        redis_client = self._increment_and_decrement(PhaseTwoConsumer)
        set_calls = [call.args[1] for call in redis_client.set.call_args_list]
        self.assertEqual(set_calls, [1, 0])

    def test_phase_three_increment_and_decrement_actualizan_redis(self):
        redis_client = self._increment_and_decrement(PhaseThreeConsumer)
        set_calls = [call.args[1] for call in redis_client.set.call_args_list]
        self.assertEqual(set_calls, [1, 0])


@IN_MEMORY_LAYER
class TestChatConsumer(TestCase):
    def setUp(self):
        cache.clear()
        self.debate = Debate.objects.create(
            title="T1",
            description="desc",
            end_time=timedelta(hours=1),
            group_identity_id="g1",
            group_snapshot={"id": "g1"},
        )
        self.user = IdentityPrincipal(id="u1", username="ana")

    def _communicator(self, user):
        communicator = WebsocketCommunicator(ChatConsumer.as_asgi(), "/ws/")
        communicator.scope["url_route"] = {
            "kwargs": {"group_id": "g1", "debate_id": str(self.debate.id)}
        }
        communicator.scope["user"] = user
        return communicator

    def test_usuario_no_autenticado_es_rechazado(self):
        async def _run():
            communicator = self._communicator(AnonymousUser())
            connected, code = await communicator.connect()
            await communicator.disconnect()
            return connected, code

        connected, code = async_to_sync(_run)()
        self.assertFalse(connected)

    def test_debate_inexistente_es_rechazado(self):
        async def _run():
            communicator = WebsocketCommunicator(ChatConsumer.as_asgi(), "/ws/")
            communicator.scope["url_route"] = {
                "kwargs": {"group_id": "g1", "debate_id": "99999"}
            }
            communicator.scope["user"] = self.user
            connected, _ = await communicator.connect()
            await communicator.disconnect()
            return connected

        self.assertFalse(async_to_sync(_run)())

    def test_debate_expirado_es_rechazado(self):
        expired = Debate.objects.create(
            title="Viejo",
            description="d",
            end_time=timedelta(seconds=-1),
            group_identity_id="g1",
            group_snapshot={"id": "g1"},
        )

        async def _run():
            communicator = WebsocketCommunicator(ChatConsumer.as_asgi(), "/ws/")
            communicator.scope["url_route"] = {
                "kwargs": {"group_id": "g1", "debate_id": str(expired.id)}
            }
            communicator.scope["user"] = self.user
            connected, _ = await communicator.connect()
            await communicator.disconnect()
            return connected

        self.assertFalse(async_to_sync(_run)())

    def test_conexion_valida_envia_mensajes_iniciales(self):
        async def _run():
            communicator = self._communicator(self.user)
            connected, _ = await communicator.connect()
            first = await communicator.receive_json_from()
            second = await communicator.receive_json_from()
            await communicator.disconnect()
            return connected, first, second

        connected, first, second = async_to_sync(_run)()
        self.assertTrue(connected)
        self.assertIn("understand", first["text"])
        self.assertEqual(second["text"], "desc")
        self.assertEqual(Message.objects.count(), 2)

    def test_no_reenvia_mensajes_iniciales_si_ya_existen(self):
        async def _run():
            communicator = self._communicator(self.user)
            await communicator.connect()
            await communicator.receive_json_from()
            await communicator.receive_json_from()
            await communicator.disconnect()

            # segunda conexion: ya no deberian reenviarse los 2 iniciales
            communicator2 = self._communicator(self.user)
            await communicator2.connect()
            has_more = await communicator2.receive_nothing(timeout=0.2)
            await communicator2.disconnect()
            return has_more

        has_more = async_to_sync(_run)()
        self.assertTrue(has_more)  # receive_nothing=True significa que NO llego nada
        self.assertEqual(Message.objects.count(), 2)

    def test_receive_crea_mensaje_y_lo_transmite(self):
        async def _run():
            communicator = self._communicator(self.user)
            await communicator.connect()
            await communicator.receive_json_from()
            await communicator.receive_json_from()

            await communicator.send_json_to({"text": "Hola a todos"})
            response = await communicator.receive_json_from()
            await communicator.disconnect()
            return response

        response = async_to_sync(_run)()
        self.assertEqual(response["text"], "Hola a todos")
        self.assertEqual(response["user"], "ana")
        self.assertEqual(Message.objects.filter(text="Hola a todos").count(), 1)

    def test_receive_con_parent_crea_respuesta(self):
        root = Message.objects.create(
            debate=self.debate, text="raiz", user_identity_id="u2"
        )

        async def _run():
            communicator = self._communicator(self.user)
            await communicator.connect()
            await communicator.receive_json_from()
            await communicator.receive_json_from()

            await communicator.send_json_to({"text": "respuesta", "parent": root.id})
            response = await communicator.receive_json_from()
            await communicator.disconnect()
            return response

        response = async_to_sync(_run)()
        self.assertEqual(response["parent"], root.id)
        reply = Message.objects.get(text="respuesta")
        self.assertEqual(reply.parent_id, root.id)

    def test_disconnect_remueve_usuario_de_connected_users(self):
        async def _run():
            communicator = self._communicator(self.user)
            await communicator.connect()
            await communicator.receive_json_from()
            await communicator.receive_json_from()
            await communicator.disconnect()

        async_to_sync(_run)()
        connected_users = cache.get(f"chat_users_{self.debate.id}", set())
        self.assertNotIn("u1", connected_users)
