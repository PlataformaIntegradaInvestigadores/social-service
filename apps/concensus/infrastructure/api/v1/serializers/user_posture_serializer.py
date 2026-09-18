from rest_framework import serializers

from apps.concensus.domain.entities.debate_participant_posture import UserPosture


class UserPostureSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPosture
        fields = [
            "id",
            "user_identity_id",
            "user_snapshot",
            "debate",
            "posture",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]
