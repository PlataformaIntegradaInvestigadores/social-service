"""Se encargará de recibir y enviar mensajes a los usuarios conectados"""

import json
import logging

import redis
from asgiref.sync import async_to_sync, sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

logger = logging.getLogger(__name__)


class GroupConsumer(AsyncWebsocketConsumer):
    """
    Consumer de WebSocket para manejar conexiones y mensajes de un grupo específico.
    """

    # 1. Métodos de Conexión y Desconexión
    async def connect(self):
        """
        Método asíncrono llamado cuando un cliente intenta conectarse.
        Se añade el cliente al grupo de canales y se acepta la conexión WebSocket.
        También incrementa el contador de conexiones activas.
        """
        self.group_id = self.scope["url_route"]["kwargs"]["group_id"]
        self.group_name = f"group_{self.group_id}"
        self.redis = redis.StrictRedis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,  # Agrega la autenticación
            db=0,
        )

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        await self.increment_connection_count()

    async def disconnect(self, close_code):
        """
        Método asíncrono llamado cuando un cliente se desconecta.
        Se elimina el cliente del grupo de canales y se decrementa el contador de conexiones activas.
        """
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

        await self.decrement_connection_count()

    # 2. Método de Envío de Mensajes del WebSocket del Servidor
    async def receive(self, text_data):
        pass

    async def group_message(self, event):
        """
        Método asíncrono que maneja los mensajes recibidos en el grupo y los envía a través del WebSocket.
        """
        message = event["message"]

        await self.send(text_data=json.dumps({"message": message}))

    # 3. Métodos Adicionales: Conteo de Conexiones y Notificación de Nuevo Tema
    @sync_to_async
    def increment_connection_count(self):
        """
        Incrementa el contador de conexiones activas en el grupo y notifica a los clientes.

        TODO: AGREGAR EL ID DEL USUARIO MAS ID DE GRUPO PARA SUAMR +1 SI AUN NO ESTA EL REGISTRO
        Actualmente si se detiene docker y luego se inicia se quedan guardadas las conexiones y toca borrar manualmente
        esto se controlaria con el id de usuario y el id de grupo sumar +1 si aun no esta el registro.
        Si se detiene el docker se construye desde cero no hay problema ya q los datos se crean segun la interacion del usuario
        """
        connection_count = self.get_connection_count() + 1
        self.set_connection_count(connection_count)
        self.notify_connection_count(connection_count)

    @sync_to_async
    def decrement_connection_count(self):
        """
        Decrementa el contador de conexiones activas en el grupo y notifica a los clientes.
        """
        connection_count = self.get_connection_count() - 1
        if connection_count < 0:
            connection_count = 0
        self.set_connection_count(connection_count)
        self.notify_connection_count(connection_count)

    def get_connection_count(self):
        """
        Obtiene el número actual de conexiones activas desde Redis.
        """
        connection_count = self.redis.get(self.group_name)
        return int(connection_count) if connection_count else 0

    def set_connection_count(self, count):
        """
        Establece el número de conexiones activas en Redis.
        """
        self.redis.set(self.group_name, count)

    def notify_connection_count(self, count):
        """
        Notifica a los clientes el número actualizado de conexiones activas en el grupo.
        """
        async_to_sync(self.channel_layer.group_send)(
            self.group_name,
            {
                "type": "group_message",
                "message": {"type": "connection_count", "active_connections": count},
            },
        )
