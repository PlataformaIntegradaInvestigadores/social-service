from rest_framework import serializers

from apps.concensus.domain.entities.notification import (
    NotificationPhaseOne,
    NotificationPhaseTwo,
)


class NotificationSerializer(serializers.ModelSerializer):
    profile_picture_url = serializers.SerializerMethodField()

    class Meta:
        model = NotificationPhaseOne
        fields = [
            "id",
            "user_identity_id",
            "user_snapshot",
            "group_identity_id",
            "group_snapshot",
            "notification_type",
            "message",
            "created_at",
            "profile_picture_url",
        ]

    def get_profile_picture_url(self, obj):
        request = self.context.get("request")
        profile_picture_url = obj.user_snapshot.get("profile_picture")
        return (
            request.build_absolute_uri(profile_picture_url)
            if request and profile_picture_url
            else profile_picture_url
        )


class NotificationPhaseTwoSerializer(serializers.ModelSerializer):
    profile_picture_url = serializers.SerializerMethodField()

    class Meta:
        model = NotificationPhaseTwo
        fields = [
            "id",
            "user_identity_id",
            "user_snapshot",
            "group_identity_id",
            "group_snapshot",
            "notification_type",
            "message",
            "created_at",
            "profile_picture_url",
        ]

    def get_profile_picture_url(self, obj):
        request = self.context.get("request")
        profile_picture_url = obj.user_snapshot.get("profile_picture")
        return (
            request.build_absolute_uri(profile_picture_url)
            if request and profile_picture_url
            else profile_picture_url
        )
