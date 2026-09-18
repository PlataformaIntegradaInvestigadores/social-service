import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.apps import apps
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response

from apps.concensus.domain.entities.notification import NotificationPhaseOne
from apps.concensus.domain.entities.user_expertice import UserExpertise
from apps.concensus.infrastructure.api.v1.serializers.user_expertice_serializer import (
    UserExpertiseSerializer,
)
from apps.custom_auth.identity_principal import snapshot_from_principal

logger = logging.getLogger(__name__)


class UserExpertiseView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserExpertiseSerializer

    def create(self, request, *args, **kwargs):
        group_id = str(self.kwargs["group_id"])
        topic_id = request.data.get("topic_id")
        user_id = str(request.data.get("user_id") or request.user.id)
        expertise_level = request.data.get("expertise_level", 1)

        if not topic_id or not user_id:
            return Response(
                {"error": "Invalid data"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            expertise_value = int(expertise_level)
            expertise_value = max(1, min(expertise_value, 100))
        except ValueError:
            return Response(
                {"error": "experticeValue must be an integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        expertise_level = max(1, expertise_value // 10)

        RecommendedTopic = apps.get_model("concensus", "RecommendedTopic")
        TopicAddedUser = apps.get_model("concensus", "TopicAddedUser")

        try:
            recommended_topic = RecommendedTopic.objects.get(
                id=topic_id, group_identity_id=group_id
            )
        except RecommendedTopic.DoesNotExist:
            try:
                topic_added_user = TopicAddedUser.objects.get(
                    id=topic_id, group_identity_id=group_id
                )
                recommended_topic = topic_added_user.topic
            except TopicAddedUser.DoesNotExist:
                return Response(
                    {"error": "Topic does not exist in this group"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        user_snapshot = snapshot_from_principal(request.user)
        group_snapshot = {"id": group_id}

        try:
            user_expertise, created = UserExpertise.objects.update_or_create(
                user_identity_id=user_id,
                group_identity_id=group_id,
                topic=recommended_topic,
                defaults={
                    "user_snapshot": user_snapshot,
                    "group_snapshot": group_snapshot,
                    "expertise_level": expertise_level,
                    "has_provided_expertise": True,
                },
            )
            logger.info(
                f"User expertise {'created' if created else 'updated'} successfully"
            )
        except Exception as e:
            logger.error(f"Error in update_or_create: {str(e)}")
            return Response(
                {"error": "Error updating or creating user expertise"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        display_name = request.user.get_full_name() or request.user.username or user_id
        if expertise_level <= 3:
            message = (
                f"{display_name} is a junior in <i>{recommended_topic.topic_name}</i>"
            )
        elif expertise_level <= 7:
            message = (
                f"{display_name} has intermediate knowledge in "
                f"<i>{recommended_topic.topic_name}</i>"
            )
        else:
            message = (
                f"{display_name} is an expert in <i>{recommended_topic.topic_name}</i>"
            )

        existing_notification = NotificationPhaseOne.objects.filter(
            user_identity_id=user_id,
            group_identity_id=group_id,
            notification_type="user_expertise",
            message=message,
        ).first()

        if existing_notification:
            existing_notification.created_at = timezone.now()
            existing_notification.save()
            notification = existing_notification
        else:
            notification = NotificationPhaseOne.objects.create(
                user_identity_id=user_id,
                user_snapshot=user_snapshot,
                group_identity_id=group_id,
                group_snapshot=group_snapshot,
                notification_type="user_expertise",
                message=message,
            )

        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"group_{group_id}",
                {
                    "type": "group_message",
                    "message": {
                        "id": notification.id,
                        "type": "user_expertise",
                        "user_id": user_id,
                        "group_id": group_id,
                        "topic_id": topic_id,
                        "expertise_level": expertise_level,
                        "added_at": user_expertise.updated_at.isoformat(),
                        "notification_message": message,
                        "profile_picture_url": user_snapshot.get("profile_picture"),
                    },
                },
            )
        except Exception as e:
            logger.error(f"Error sending message through channels: {str(e)}")
            return Response(
                {"error": "Error sending message through channels"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        serializer = self.get_serializer(user_expertise)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
