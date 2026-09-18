import json
import logging

import redis
from asgiref.sync import async_to_sync, sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

logger = logging.getLogger(__name__)


class PhaseThreeConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_id = self.scope["url_route"]["kwargs"]["group_id"]
        self.group_name = f"phase3_group_{self.group_id}"
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
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        await self.decrement_connection_count()

    async def receive(self, text_data):
        pass

    async def group_message(self, event):
        message = event["message"]
        await self.send(text_data=json.dumps({"message": message}))

    @sync_to_async
    def increment_connection_count(self):
        connection_count = self.get_connection_count() + 1
        self.set_connection_count(connection_count)
        self.notify_connection_count(connection_count)

    @sync_to_async
    def decrement_connection_count(self):
        connection_count = self.get_connection_count() - 1
        if connection_count < 0:
            connection_count = 0
        self.set_connection_count(connection_count)
        self.notify_connection_count(connection_count)

    def get_connection_count(self):
        connection_count = self.redis.get(self.group_name)
        return int(connection_count) if connection_count else 0

    def set_connection_count(self, count):
        self.redis.set(self.group_name, count)

    def notify_connection_count(self, count):
        async_to_sync(self.channel_layer.group_send)(
            self.group_name,
            {
                "type": "group_message",
                "message": {"type": "connection_count", "active_connections": count},
            },
        )
