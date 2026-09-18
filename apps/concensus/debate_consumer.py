import json

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.cache import cache

from apps.concensus.domain.entities.debate import Debate
from apps.concensus.domain.entities.debate_message import Message
from apps.custom_auth.identity_principal import snapshot_from_principal


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.group_id = self.scope["url_route"]["kwargs"]["group_id"]
        self.debate_id = self.scope["url_route"]["kwargs"]["debate_id"]
        self.room_group_name = f"chat_{self.group_id}_{self.debate_id}"

        if not self.scope["user"].is_authenticated:
            await self.close(code=403)
            return

        debate = await self.get_debate(self.debate_id)
        if debate is None or debate.is_time_exceeded():
            await self.close(code=403)
            return

        # Agregar usuario a Redis
        connected_users = cache.get(f"chat_users_{self.debate_id}", set())
        connected_users.add(self.scope["user"].id)
        cache.set(f"chat_users_{self.debate_id}", connected_users)

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # Enviar mensajes iniciales si es necesario
        await self.send_initial_messages(debate)

    async def disconnect(self, close_code):
        connected_users = cache.get(f"chat_users_{self.debate_id}", set())
        connected_users.discard(self.scope["user"].id)
        cache.set(f"chat_users_{self.debate_id}", connected_users)

        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        user = self.scope["user"]
        group_id = self.group_id
        debate_id = self.debate_id
        message_text = data["text"]
        posture = data.get("posture", "neutral")
        parent_id = data.get("parent")

        parent = None
        if parent_id:
            parent = await sync_to_async(Message.objects.get)(id=parent_id)

        message = await sync_to_async(Message.objects.create)(
            user_identity_id=str(user.id),
            user_snapshot=snapshot_from_principal(user),
            group_identity_id=str(group_id),
            group_snapshot={"id": str(group_id)},
            debate_id=debate_id,
            text=message_text,
            posture=posture,
            parent=parent,
        )

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": {
                    "id": message.id,
                    "user": user.username,
                    "text": message_text,
                    "posture": posture,
                    "parent": parent_id,
                    "created_at": message.created_at.isoformat(),
                },
            },
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event["message"]))

    @sync_to_async
    def get_debate(self, debate_id):
        try:
            return Debate.objects.get(id=debate_id)
        except Debate.DoesNotExist:
            return None

    @sync_to_async
    def has_initial_messages(self, debate):
        """
        Verifica si los mensajes iniciales ya existen en la base de datos.
        """
        first_message = f"I want to understand {debate.title} better, how do you see it, do you have experience or knowledge that you can contribute?"
        second_message = debate.description

        return Message.objects.filter(
            debate_id=debate.id, text__in=[first_message, second_message]
        ).exists()

    async def send_initial_messages(self, debate):
        """
        Envía los dos primeros mensajes automáticamente **solo si no han sido enviados antes**.
        """
        messages_exist = await self.has_initial_messages(debate)
        if messages_exist:
            return  # No enviar si ya existen

        first_message = f"I want to understand {debate.title} better, how do you see it, do you have experience or knowledge that you can contribute?"
        second_message = debate.description

        for text in [first_message, second_message]:
            message = await sync_to_async(Message.objects.create)(
                user_identity_id=str(self.scope["user"].id),
                user_snapshot=snapshot_from_principal(self.scope["user"]),
                group_identity_id=str(self.group_id),
                group_snapshot={"id": str(self.group_id)},
                debate_id=self.debate_id,
                text=text,
                posture="neutral",
            )

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "message": {
                        "id": message.id,
                        "user": self.scope["user"].username,
                        "text": text,
                        "posture": "neutral",
                        "parent": None,
                        "created_at": message.created_at.isoformat(),
                    },
                },
            )
