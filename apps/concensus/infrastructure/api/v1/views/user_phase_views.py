import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiRequest,
    OpenApiResponse,
    extend_schema,
)
from rest_framework import generics, permissions, status
from rest_framework.response import Response

from apps.concensus.domain.entities.user_phase import UserPhase
from apps.concensus.infrastructure.api.v1.serializers.user_phase_serializer import (
    UserPhaseSerializer,
)

logger = logging.getLogger(__name__)


class UserCurrentPhaseView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserPhaseSerializer

    def get(self, request, group_id):
        try:
            user_phase = UserPhase.objects.get(
                user_identity_id=str(request.user.id),
                group_identity_id=str(group_id),
            )
            serializer = self.get_serializer(user_phase)
            return Response(serializer.data)
        except UserPhase.DoesNotExist:
            return Response({"phase": 0})


class UpdateGroupPhaseView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserPhaseSerializer

    @extend_schema(
        summary="Update the phase of all users in a group.",
        description=(
            "Update the phase of all users in a group to the phase "
            "specified in the request."
        ),
        request=OpenApiRequest(
            examples=[OpenApiExample(name="Update phase", value={"phase": 1})]
        ),
        responses={
            200: OpenApiResponse(
                description="User phases updated successfully.", response=Response
            )
        },
    )
    def post(self, request, group_id):
        phase = request.data.get("phase")
        user_phases = UserPhase.objects.filter(group_identity_id=str(group_id))

        if not user_phases.exists():
            return Response(
                {"detail": "No user phases found for this group."},
                status=status.HTTP_404_NOT_FOUND,
            )

        user_phases.update(phase=phase, completed_at=timezone.now())

        updated_user_phases = UserPhase.objects.filter(group_identity_id=str(group_id))
        serializer = self.get_serializer(updated_user_phases, many=True)

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"phase3_group_{group_id}",
            {
                "type": "group_message",
                "message": {
                    "type": "phase_update",
                    "phase": phase,
                },
            },
        )

        logger.info(
            f"Websocket message sent to group {group_id} to update phase to {phase}"
        )
        return Response(serializer.data, status=status.HTTP_200_OK)
