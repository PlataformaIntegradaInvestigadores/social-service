from rest_framework import serializers

from apps.concensus.domain.entities.final_topic_order import FinalTopicOrder


class FinalTopicOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinalTopicOrder
        fields = "__all__"


# select * from "concensus_finaltopicorder";
