from rest_framework import serializers

from apps.concensus.domain.entities.debate_message import Message


class MessageSerializer(serializers.ModelSerializer):
    user = serializers.CharField(source="user.username", read_only=True)
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id",
            "user",
            "user_identity_id",
            "user_snapshot",
            "group_identity_id",
            "group_snapshot",
            "text",
            "posture",
            "created_at",
            "parent",
            "replies",
        ]

    def get_replies(self, obj):
        replies = obj.replies.all()
        return MessageSerializer(replies, many=True).data
