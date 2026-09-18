from rest_framework import serializers

from apps.concensus.domain.entities.user_satisfaction import UserSatisfaction


class UserSatisfactionSerializer(serializers.ModelSerializer):
    profile_picture_url = serializers.SerializerMethodField()

    class Meta:
        model = UserSatisfaction
        fields = [
            "user_identity_id",
            "user_snapshot",
            "group_identity_id",
            "group_snapshot",
            "satisfaction_level",
            "created_at",
            "message",
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
