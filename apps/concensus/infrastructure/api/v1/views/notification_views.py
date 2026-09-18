from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.apps import apps
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response

from apps.concensus.domain.entities.notification import (
    NotificationPhaseOne,
    NotificationPhaseTwo,
)
from apps.concensus.domain.entities.user_phase import UserPhase
from apps.concensus.infrastructure.api.v1.serializers.notification_serializer import (
    NotificationPhaseTwoSerializer,
    NotificationSerializer,
)
from apps.custom_auth.identity_principal import snapshot_from_principal


def _group_snapshot(group_id):
    return {"id": str(group_id)}


def _display_name(user):
    return user.get_full_name() or user.username or str(user.id)


def _emit(channel, payload):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        channel, {"type": "group_message", "message": payload}
    )


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return NotificationPhaseOne.objects.filter(
            group_identity_id=str(self.kwargs["group_id"])
        ).order_by("created_at")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context


class NotificationPhaseTwoListView(generics.ListAPIView):
    serializer_class = NotificationPhaseTwoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return NotificationPhaseTwo.objects.filter(
            group_identity_id=str(self.kwargs["group_id"])
        ).order_by("created_at")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context


class TopicVisitedView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        group_id = str(self.kwargs["group_id"])
        topic_id = request.data.get("topic_id")
        user_id = str(request.data.get("user_id") or request.user.id)

        if not topic_id or not user_id:
            return Response(
                {"error": "Invalid data"}, status=status.HTTP_400_BAD_REQUEST
            )

        Topic = apps.get_model("concensus", "RecommendedTopic")
        TopicAddedUser = apps.get_model("concensus", "TopicAddedUser")

        try:
            topic = Topic.objects.get(id=topic_id, group_identity_id=group_id)
        except Topic.DoesNotExist:
            try:
                topic_added_user = TopicAddedUser.objects.get(
                    id=topic_id, group_identity_id=group_id
                )
                topic = topic_added_user.topic
            except TopicAddedUser.DoesNotExist:
                return Response(
                    {"error": "Topic does not exist in this group"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        user_snapshot = snapshot_from_principal(request.user)
        group_snapshot = _group_snapshot(group_id)
        message = f"{_display_name(request.user)} visited <i>{topic.topic_name}</i>"

        notification, _created = NotificationPhaseOne.objects.update_or_create(
            user_identity_id=user_id,
            group_identity_id=group_id,
            notification_type="topic_visited",
            message=message,
            defaults={
                "user_snapshot": user_snapshot,
                "group_snapshot": group_snapshot,
                "created_at": timezone.now(),
            },
        )

        _emit(
            f"group_{group_id}",
            {
                "id": notification.id,
                "user_id": user_id,
                "group_id": group_id,
                "type": "topic_visited",
                "notification_message": message,
                "added_at": notification.created_at.isoformat(),
                "topic_id": topic_id,
                "profile_picture_url": user_snapshot.get("profile_picture"),
            },
        )

        serializer = NotificationSerializer(notification, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CombinedSearchView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        group_id = str(self.kwargs["group_id"])
        topics = request.data.get("topics", [])
        user_id = str(request.data.get("user_id") or request.user.id)

        if not topics or not user_id:
            return Response(
                {"error": "Invalid data"}, status=status.HTTP_400_BAD_REQUEST
            )

        Topic = apps.get_model("concensus", "RecommendedTopic")
        TopicAddedUser = apps.get_model("concensus", "TopicAddedUser")
        topic_names = []
        for topic_id in topics:
            try:
                topic = Topic.objects.get(id=topic_id, group_identity_id=group_id)
            except Topic.DoesNotExist:
                try:
                    topic_added_user = TopicAddedUser.objects.get(
                        id=topic_id, group_identity_id=group_id
                    )
                    topic = topic_added_user.topic
                except TopicAddedUser.DoesNotExist:
                    return Response(
                        {
                            "error": f"Topic with id {topic_id} does not exist "
                            "in this group"
                        },
                        status=status.HTTP_404_NOT_FOUND,
                    )
            topic_names.append(topic.topic_name)

        user_snapshot = snapshot_from_principal(request.user)
        group_snapshot = _group_snapshot(group_id)
        combined_topics = ", ".join(topic_names)
        message = (
            f"{_display_name(request.user)} made a combined search "
            f"for Topics: {combined_topics}"
        )

        notification, _created = NotificationPhaseOne.objects.update_or_create(
            user_identity_id=user_id,
            group_identity_id=group_id,
            notification_type="combined_search",
            message=message,
            defaults={
                "user_snapshot": user_snapshot,
                "group_snapshot": group_snapshot,
                "created_at": timezone.now(),
            },
        )

        _emit(
            f"group_{group_id}",
            {
                "id": notification.id,
                "type": "combined_search",
                "topics": topics,
                "user_id": user_id,
                "group_id": group_id,
                "notification_message": message,
                "added_at": notification.created_at.isoformat(),
                "profile_picture_url": user_snapshot.get("profile_picture"),
            },
        )

        serializer = NotificationSerializer(notification, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PhaseOneCompletedView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        group_id = str(self.kwargs["group_id"])
        user_id = str(request.user.id)
        user_snapshot = snapshot_from_principal(request.user)
        group_snapshot = _group_snapshot(group_id)

        message = f"{_display_name(request.user)} has completed the phase One"
        notification = NotificationPhaseOne.objects.create(
            user_identity_id=user_id,
            user_snapshot=user_snapshot,
            group_identity_id=group_id,
            group_snapshot=group_snapshot,
            notification_type="phase_one_completed",
            message=message,
        )

        UserPhase.objects.update_or_create(
            user_identity_id=user_id,
            group_identity_id=group_id,
            defaults={
                "user_snapshot": user_snapshot,
                "group_snapshot": group_snapshot,
                "phase": 1,
                "completed_at": timezone.now(),
            },
        )

        _emit(
            f"group_{group_id}",
            {
                "id": notification.id,
                "type": "consensus_completed",
                "user_id": user_id,
                "group_id": group_id,
                "added_at": notification.created_at.isoformat(),
                "notification_message": message,
                "profile_picture_url": user_snapshot.get("profile_picture"),
            },
        )

        serializer = NotificationSerializer(notification, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class TopicReorderView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, group_id):
        return _phase_two_topic_notification(request, str(group_id), "topic_reorder")


class TopicTagView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, group_id):
        return _phase_two_topic_notification(request, str(group_id), "topic_tag")


def _phase_two_topic_notification(request, group_id, notification_type):
    topic_id = request.data.get("topic_id")
    user_id = str(request.data.get("user_id") or request.user.id)
    Topic = apps.get_model("concensus", "RecommendedTopic")

    try:
        topic = Topic.objects.get(id=topic_id, group_identity_id=group_id)
    except Topic.DoesNotExist:
        return Response(
            {"error": "Topic does not exist in this group"},
            status=status.HTTP_404_NOT_FOUND,
        )

    user_snapshot = snapshot_from_principal(request.user)
    group_snapshot = _group_snapshot(group_id)

    if notification_type == "topic_tag":
        tag = request.data.get("tag")
        if not tag:
            return Response(
                {"error": "Invalid data"}, status=status.HTTP_400_BAD_REQUEST
            )
        message = (
            f'{_display_name(request.user)} tagged topic "{topic.topic_name}" '
            f'as "{tag}"'
        )
    else:
        original_position = request.data.get("original_position")
        new_position = request.data.get("new_position")
        if original_position is None or new_position is None:
            return Response(
                {"error": "Invalid data"}, status=status.HTTP_400_BAD_REQUEST
            )
        direction = "up" if new_position < original_position else "down"
        message = (
            f"{_display_name(request.user)} moved {direction} topic "
            f'"{topic.topic_name}" from {original_position} to {new_position}'
        )

    notification = NotificationPhaseTwo.objects.create(
        user_identity_id=user_id,
        user_snapshot=user_snapshot,
        group_identity_id=group_id,
        group_snapshot=group_snapshot,
        notification_type=notification_type,
        message=message,
    )

    _emit(
        f"phase2_group_{group_id}",
        {
            "type": notification_type,
            "topic_id": topic_id,
            "user_id": user_id,
            "group_id": group_id,
            "added_at": notification.created_at.isoformat(),
            "notification_message": message,
            "profile_picture_url": user_snapshot.get("profile_picture"),
        },
    )

    serializer = NotificationPhaseTwoSerializer(
        notification, context={"request": request}
    )
    return Response(serializer.data, status=status.HTTP_201_CREATED)
