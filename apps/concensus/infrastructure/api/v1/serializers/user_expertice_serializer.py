from rest_framework import serializers

from apps.concensus.domain.entities.user_expertice import UserExpertise


class UserExpertiseSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserExpertise
        fields = "__all__"


# select * from "concensus_userexpertise ";
