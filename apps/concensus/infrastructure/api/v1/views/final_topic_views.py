from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.apps import apps
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response

from apps.concensus.domain.entities.final_topic_order import FinalTopicOrder
from apps.concensus.domain.entities.user_phase import UserPhase
from apps.concensus.infrastructure.api.v1.serializers.final_topic_serializer import (
    FinalTopicOrderSerializer,
)
from apps.concensus.infrastructure.api.v1.serializers.notification_serializer import (
    NotificationPhaseTwoSerializer,
)
from apps.custom_auth.identity_principal import snapshot_from_principal


class SaveFinalTopicOrderView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = FinalTopicOrderSerializer

    def post(self, request, group_id):
        user_id = str(request.user.id)
        final_topic_orders = request.data.get("final_topic_orders", [])

        if not final_topic_orders:
            return Response(
                {"error": "No topic order data provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        group_snapshot = {"id": str(group_id)}
        user_snapshot = snapshot_from_principal(request.user)

        FinalTopicOrder.objects.filter(
            idGroup_identity_id=str(group_id),
            idUser_identity_id=user_id,
        ).delete()

        for order in final_topic_orders:
            order["idGroup_identity_id"] = str(group_id)
            order["idGroup_snapshot"] = group_snapshot
            order["idUser_identity_id"] = user_id
            order["idUser_snapshot"] = user_snapshot
            serializer = self.serializer_class(data=order)
            if serializer.is_valid():
                serializer.save()
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        UserPhase.objects.update_or_create(
            user_identity_id=user_id,
            group_identity_id=str(group_id),
            defaults={
                "user_snapshot": user_snapshot,
                "group_snapshot": group_snapshot,
                "phase": 2,
                "completed_at": timezone.now(),
            },
        )

        display_name = request.user.get_full_name() or request.user.username or user_id
        message = f"{display_name} has completed the phase Two"

        NotificationPhaseTwo = apps.get_model("concensus", "NotificationPhaseTwo")
        notification = NotificationPhaseTwo.objects.create(
            user_identity_id=user_id,
            user_snapshot=user_snapshot,
            group_identity_id=str(group_id),
            group_snapshot=group_snapshot,
            notification_type="consensus_finalized",
            message=message,
        )

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"phase2_group_{group_id}",
            {
                "type": "group_message",
                "message": {
                    "type": "consensus_finalized",
                    "user_id": user_id,
                    "group_id": str(group_id),
                    "notification_message": message,
                    "added_at": timezone.now().isoformat(),
                    "profile_picture_url": user_snapshot.get("profile_picture"),
                },
            },
        )

        notification_serializer = NotificationPhaseTwoSerializer(
            notification, context={"request": request}
        )
        return Response(notification_serializer.data, status=status.HTTP_201_CREATED)
