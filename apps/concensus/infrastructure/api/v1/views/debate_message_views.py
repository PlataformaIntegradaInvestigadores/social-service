from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.concensus.domain.entities.debate_message import Message
from apps.concensus.infrastructure.api.v1.serializers.debate_message_serializer import (
    MessageSerializer,
)


class MessageHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, debate_id):
        messages = Message.objects.filter(debate_id=debate_id, parent=None).order_by(
            "created_at"
        )
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)
