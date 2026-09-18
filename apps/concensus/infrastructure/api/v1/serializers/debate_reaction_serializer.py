from rest_framework import serializers

from apps.concensus.domain.entities.debate_reaction import Reaction


class ReactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reaction
        fields = ["id", "user_identity_id", "user_snapshot", "message", "created_at"]
        read_only_fields = ["id", "created_at"]
