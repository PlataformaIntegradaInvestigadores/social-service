from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.concensus.domain.entities.debate_reaction import Reaction
from apps.concensus.infrastructure.api.v1.serializers.debate_reaction_serializer import (
    ReactionSerializer,
)
from apps.custom_auth.identity_principal import snapshot_from_principal


class ReactionViewSet(
    mixins.CreateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet
):
    queryset = Reaction.objects.all()
    serializer_class = ReactionSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        data["user_identity_id"] = str(request.user.id)
        data["user_snapshot"] = snapshot_from_principal(request.user)
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.user_identity_id == str(request.user.id):
            self.perform_destroy(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(
            {"detail": "No tienes permiso para eliminar esta reaccion."},
            status=status.HTTP_403_FORBIDDEN,
        )
