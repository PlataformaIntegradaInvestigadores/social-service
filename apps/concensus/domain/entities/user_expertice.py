from django.db import models

from apps.concensus.domain.entities.topic import RecommendedTopic
from apps.custom_auth.identity_principal import (
    group_ref_from_snapshot,
    group_snapshot_from_principal,
    ref_from_snapshot,
    snapshot_from_principal,
)


class UserExpertise(models.Model):
    user_identity_id = models.CharField(max_length=64, db_index=True)
    user_snapshot = models.JSONField(default=dict, blank=True)
    group_identity_id = models.CharField(max_length=64, db_index=True)
    group_snapshot = models.JSONField(default=dict, blank=True)
    topic = models.ForeignKey(RecommendedTopic, on_delete=models.CASCADE)
    expertise_level = models.IntegerField(default=1)
    has_provided_expertise = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user_identity_id", "group_identity_id", "topic")

    @property
    def user(self):
        return ref_from_snapshot(self.user_identity_id, self.user_snapshot)

    @user.setter
    def user(self, value):
        self.user_identity_id = str(value.id)
        self.user_snapshot = snapshot_from_principal(value)

    @property
    def group(self):
        return group_ref_from_snapshot(self.group_identity_id, self.group_snapshot)

    @group.setter
    def group(self, value):
        self.group_identity_id = str(value.id)
        self.group_snapshot = group_snapshot_from_principal(value)

    def __str__(self):
        return (
            f"{self.user.username} - {self.topic.topic_name} - {self.expertise_level}"
        )


# select * from "concensus_userexpertise";
