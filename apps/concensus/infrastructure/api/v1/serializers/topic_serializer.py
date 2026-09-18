from rest_framework import serializers

from apps.concensus.domain.entities.topic import RecommendedTopic, Topic, TopicAddedUser


class TopicSerializer(serializers.ModelSerializer):
    group_name = serializers.SerializerMethodField()

    class Meta:
        model = Topic
        fields = ["id", "name", "group_identity_id", "group_snapshot", "group_name"]

    def get_group_name(self, obj):
        return obj.group.name or obj.group.title


class RecommendedTopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecommendedTopic
        fields = ["id", "topic_name", "group_identity_id", "group_snapshot"]


class TopicAddedUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = TopicAddedUser
        fields = [
            "id",
            "topic",
            "group_identity_id",
            "group_snapshot",
            "user_identity_id",
            "user_snapshot",
            "added_at",
        ]
