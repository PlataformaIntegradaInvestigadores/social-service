from rest_framework import serializers

from apps.concensus.domain.entities.debate import Debate
from apps.concensus.domain.entities.debate_participant import DebateParticipant


class DebateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Debate
        fields = [
            "id",
            "group_identity_id",
            "group_snapshot",
            "title",
            "description",
            "created_at",
            "end_time",
            "is_closed",
        ]
        read_only_fields = ["id", "created_at", "is_closed"]

    def create(self, validated_data):
        group_identity_id = validated_data["group_identity_id"]
        if Debate.objects.filter(
            group_identity_id=str(group_identity_id), is_closed=False
        ).exists():
            raise serializers.ValidationError(
                "This group already has an active debate."
            )
        return super().create(validated_data)

    def validate(self, data):
        group_identity_id = data.get("group_identity_id") or self.context.get(
            "group_id"
        )
        if not group_identity_id:
            raise serializers.ValidationError("El grupo especificado no existe.")
        data["group_identity_id"] = str(group_identity_id)
        return data


class DebateParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = DebateParticipant
        fields = [
            "id",
            "debate",
            "participant_identity_id",
            "participant_snapshot",
            "joined_at",
            "is_collaborator",
        ]
