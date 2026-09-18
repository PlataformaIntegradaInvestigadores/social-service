from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.concensus.domain.entities.debate_participant_posture import UserPosture
from apps.concensus.infrastructure.api.v1.serializers.user_posture_serializer import (
    UserPostureSerializer,
)
from apps.concensus.infrastructure.api.v1.views.debate_views import send_notification
from apps.custom_auth.identity_principal import snapshot_from_principal


class PostureViewSet(viewsets.ModelViewSet):
    queryset = UserPosture.objects.all()
    serializer_class = UserPostureSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        user = request.user
        data = request.data.copy()
        data["user_identity_id"] = str(user.id)
        data["user_snapshot"] = snapshot_from_principal(user)
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        posture = serializer.save()

        display_name = user.get_full_name() or user.username or str(user.id)
        message = (
            f'{display_name} has defined its position: "{posture.posture}" '
            f'in the debate "{posture.debate.title}".'
        )
        send_notification(
            user=user,
            group_id=posture.debate.group_identity_id,
            notification_type="posture_created",
            message=message,
            extra_data={"debate_id": posture.debate.id, "posture_id": posture.id},
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        if instance.debate.is_closed:
            return Response(
                {"detail": "El debate esta cerrado, no se puede cambiar la postura."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = request.data.copy()
        data["user_identity_id"] = str(request.user.id)
        data["user_snapshot"] = snapshot_from_principal(request.user)
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        posture = serializer.save()

        display_name = (
            request.user.get_full_name()
            or request.user.username
            or str(request.user.id)
        )
        message = (
            f'{display_name} has updated its position: "{posture.posture}" '
            f'in the discussion "{posture.debate.title}".'
        )
        send_notification(
            user=request.user,
            group_id=posture.debate.group_identity_id,
            notification_type="posture_updated",
            message=message,
            extra_data={"debate_id": posture.debate.id, "posture_id": posture.id},
        )

        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        user_id = kwargs.get("pk")
        queryset = self.queryset.filter(user_identity_id=str(user_id))
        if not queryset.exists():
            return Response(
                {"detail": "No se encontraron posturas para este usuario."}, status=404
            )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated],
        url_path="debate/(?P<debate_id>[^/.]+)",
    )
    def get_posture_by_debate(self, request, debate_id=None):
        try:
            posture = UserPosture.objects.get(
                user_identity_id=str(request.user.id), debate_id=debate_id
            )
            serializer = self.get_serializer(posture)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except UserPosture.DoesNotExist:
            return Response(
                {"detail": "El usuario no tiene postura registrada para este debate."},
                status=status.HTTP_404_NOT_FOUND,
            )
