import pytz
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.apps import apps
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.concensus.domain.entities.debate import Debate
from apps.concensus.infrastructure.api.v1.serializers.debate_serializer import (
    DebateSerializer,
)
from apps.custom_auth.identity_principal import snapshot_from_principal


def _group_snapshot(group_id):
    return {"id": str(group_id)}


def send_notification(user, group_id, notification_type, message, extra_data=None):
    if extra_data is None:
        extra_data = {}

    NotificationPhaseOne = apps.get_model("concensus", "NotificationPhaseOne")
    user_snapshot = snapshot_from_principal(user)
    group_snapshot = _group_snapshot(group_id)

    existing_notification = NotificationPhaseOne.objects.filter(
        user_identity_id=str(user.id),
        group_identity_id=str(group_id),
        notification_type=notification_type,
        message=message,
    ).first()

    if existing_notification:
        existing_notification.created_at = timezone.now()
        existing_notification.save()
        return existing_notification

    notification = NotificationPhaseOne.objects.create(
        user_identity_id=str(user.id),
        user_snapshot=user_snapshot,
        group_identity_id=str(group_id),
        group_snapshot=group_snapshot,
        notification_type=notification_type,
        message=message,
    )

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"group_{group_id}",
        {
            "type": "group_message",
            "message": {
                "id": notification.id,
                "type": notification_type,
                "user_id": str(user.id),
                "group_id": str(group_id),
                "notification_message": message,
                "added_at": notification.created_at.isoformat(),
                "profile_picture_url": user_snapshot.get("profile_picture"),
                **extra_data,
            },
        },
    )
    return notification


class DebateViewSet(viewsets.ModelViewSet):
    queryset = Debate.objects.all()
    serializer_class = DebateSerializer
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        user_timezone = getattr(request.user, "timezone", None) or "UTC"
        timezone.activate(pytz.timezone(user_timezone))

    def finalize_response(self, request, response, *args, **kwargs):
        timezone.deactivate()
        return super().finalize_response(request, response, *args, **kwargs)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["group_id"] = self.kwargs.get("group_id")
        return context

    def get_queryset(self):
        group_id = self.kwargs.get("group_id")
        queryset = Debate.objects.filter(group_identity_id=str(group_id))
        for debate in queryset.filter(is_closed=False):
            if debate.is_time_exceeded():
                debate.is_closed = True
                debate.save()
        return queryset

    @staticmethod
    def validate_debate_status(debate_instance):
        if debate_instance.is_closed:
            raise ValidationError(
                {
                    "detail": "El debate esta cerrado y no se pueden "
                    "realizar mas acciones."
                }
            )

    @action(detail=True, methods=["get"], url_path="validate-status")
    def validate_status(self, _request, *_args, **_kwargs):
        debate = self.get_object()
        try:
            self.validate_debate_status(debate)
            return Response(
                {"detail": "El debate esta abierto."}, status=status.HTTP_200_OK
            )
        except ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

    def create(self, request, *args, **kwargs):
        group_id = str(self.kwargs.get("group_id"))
        if Debate.objects.filter(group_identity_id=group_id, is_closed=False).exists():
            raise ValidationError({"detail": "Este grupo ya tiene un debate activo."})

        data = request.data.copy()
        data["group_identity_id"] = group_id
        data["group_snapshot"] = _group_snapshot(group_id)
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        debate = serializer.save()

        user = request.user
        display_name = user.get_full_name() or user.username or str(user.id)
        message = f"{display_name} started a new discussion: <i>{debate.title}</i>"
        send_notification(
            user, group_id, "debate_created", message, {"debate_id": debate.id}
        )

        return Response(
            {
                "id": debate.id,
                "title": debate.title,
                "description": debate.description,
                "is_closed": debate.is_closed,
                "created_at": debate.created_at.isoformat(),
                "group_id": debate.group_identity_id,
            },
            status=status.HTTP_201_CREATED,
        )

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        debate = self.get_object()
        if not debate.is_closed and debate.is_time_exceeded():
            debate.is_closed = True
            debate.save()
        return Response(self.get_serializer(debate).data)

    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, *args, **kwargs):
        debate = self.get_object()
        if debate.is_closed:
            return Response(
                {"detail": "El debate ya esta cerrado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        debate.is_closed = True
        debate.save()

        user = request.user
        display_name = user.get_full_name() or user.username or str(user.id)
        message = f"{display_name} closed the debate: <i>{debate.title}</i>"
        send_notification(
            user,
            debate.group_identity_id,
            "debate_closed",
            message,
            {"debate_id": debate.id},
        )

        return Response(
            {"detail": f"El debate '{debate.title}' ha sido cerrado manualmente."},
            status=status.HTTP_200_OK,
        )

    def destroy(self, request, *args, **kwargs):
        debate = self.get_object()
        title = debate.title
        debate.delete()
        return Response(
            {"detail": f"El debate '{title}' ha sido eliminado."},
            status=status.HTTP_204_NO_CONTENT,
        )
