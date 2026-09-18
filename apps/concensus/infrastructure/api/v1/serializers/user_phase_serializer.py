from rest_framework import serializers

from apps.concensus.domain.entities.user_phase import UserPhase


class UserPhaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPhase
        fields = [
            "user_identity_id",
            "user_snapshot",
            "group_identity_id",
            "group_snapshot",
            "phase",
            "completed_at",
        ]
