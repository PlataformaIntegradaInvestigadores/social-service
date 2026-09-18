import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import models
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response

from apps.concensus.domain.entities.user_satisfaction import UserSatisfaction
from apps.concensus.infrastructure.api.v1.serializers.user_satisfaction_serializer import (
    UserSatisfactionSerializer,
)
from apps.custom_auth.identity_principal import snapshot_from_principal

logger = logging.getLogger(__name__)


class UserSatisfactionView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSatisfactionSerializer

    def post(self, request, *args, **kwargs):
        group_id = str(self.kwargs["group_id"])
        user_id = str(request.user.id)
        satisfaction_level = request.data.get("satisfaction_level")

        if not satisfaction_level:
            return Response(
                {"error": "Satisfaction level is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_snapshot = snapshot_from_principal(request.user)
        group_snapshot = {"id": group_id}
        display_name = request.user.get_full_name() or request.user.username or user_id
        notification_message = f"{display_name} is {satisfaction_level}"

        satisfaction, _created = UserSatisfaction.objects.update_or_create(
            user_identity_id=user_id,
            group_identity_id=group_id,
            defaults={
                "user_snapshot": user_snapshot,
                "group_snapshot": group_snapshot,
                "satisfaction_level": satisfaction_level,
                "message": notification_message,
            },
        )

        satisfaction_counts = (
            UserSatisfaction.objects.filter(group_identity_id=group_id)
            .values("satisfaction_level")
            .annotate(count=models.Count("satisfaction_level"))
        )
        counts = {
            item["satisfaction_level"]: item["count"] for item in satisfaction_counts
        }

        message = {
            "type": "user_satisfaction",
            "user_id": user_id,
            "group_id": group_id,
            "satisfaction_level": satisfaction_level,
            "notification_message": notification_message,
            "added_at": timezone.now().isoformat(),
            "profile_picture_url": user_snapshot.get("profile_picture"),
            "counts": counts,
        }

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"phase3_group_{group_id}", {"type": "group_message", "message": message}
        )

        logger.info(
            f"WebSocket notification sent for group: {group_id} with "
            f"satisfaction level: {satisfaction_level}"
        )
        serializer = self.get_serializer(satisfaction, context={"request": request})
        return Response(
            {
                "message": "Satisfaction recorded successfully.",
                "data": message,
                "record": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


class LoadUserSatisfactionNotificationsView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSatisfactionSerializer

    def get_queryset(self):
        group_id = self.kwargs["group_id"]
        return UserSatisfaction.objects.filter(
            group_identity_id=str(group_id)
        ).order_by("-created_at")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context


class LoadSatisfactionCountsView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, group_id):
        satisfaction_counts = (
            UserSatisfaction.objects.filter(group_identity_id=str(group_id))
            .values("satisfaction_level")
            .annotate(count=models.Count("satisfaction_level"))
        )
        counts = {
            item["satisfaction_level"]: item["count"] for item in satisfaction_counts
        }
        return Response({"counts": counts}, status=status.HTTP_200_OK)
