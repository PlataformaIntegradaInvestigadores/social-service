from django.db import models

from apps.custom_auth.identity_principal import (
    group_ref_from_snapshot,
    group_snapshot_from_principal,
    ref_from_snapshot,
    snapshot_from_principal,
)


class Topic(models.Model):
    name = models.CharField(max_length=100)
    group_identity_id = models.CharField(max_length=64, db_index=True)
    group_snapshot = models.JSONField(default=dict, blank=True)

    @property
    def group(self):
        return group_ref_from_snapshot(self.group_identity_id, self.group_snapshot)

    @group.setter
    def group(self, value):
        self.group_identity_id = str(value.id)
        self.group_snapshot = group_snapshot_from_principal(value)

    def __str__(self):
        return self.name


class RecommendedTopic(models.Model):
    topic_name = models.CharField(max_length=255)
    group_identity_id = models.CharField(
        max_length=64, db_index=True, null=True, blank=True
    )
    group_snapshot = models.JSONField(default=dict, blank=True)

    @property
    def group(self):
        if not self.group_identity_id:
            return None
        return group_ref_from_snapshot(self.group_identity_id, self.group_snapshot)

    @group.setter
    def group(self, value):
        if value is None:
            self.group_identity_id = None
            self.group_snapshot = {}
            return
        self.group_identity_id = str(value.id)
        self.group_snapshot = group_snapshot_from_principal(value)

    def __str__(self):
        return self.topic_name


class TopicAddedUser(models.Model):
    topic = models.ForeignKey(
        RecommendedTopic, related_name="added_by_users", on_delete=models.CASCADE
    )
    group_identity_id = models.CharField(max_length=64, db_index=True)
    group_snapshot = models.JSONField(default=dict, blank=True)
    user_identity_id = models.CharField(max_length=64, db_index=True)
    user_snapshot = models.JSONField(default=dict, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    @property
    def group(self):
        return group_ref_from_snapshot(self.group_identity_id, self.group_snapshot)

    @group.setter
    def group(self, value):
        self.group_identity_id = str(value.id)
        self.group_snapshot = group_snapshot_from_principal(value)

    @property
    def user(self):
        return ref_from_snapshot(self.user_identity_id, self.user_snapshot)

    @user.setter
    def user(self, value):
        self.user_identity_id = str(value.id)
        self.user_snapshot = snapshot_from_principal(value)

    def __str__(self):
        return (
            f"{self.user.username} added {self.topic.topic_name} to {self.group.name}"
        )


# select * from "concensus_recommendedtopic";
# select * from "concensus_topicaddeduser";

# TRUNCATE TABLE "concensus_recommendedtopic" CASCADE;
# TRUNCATE TABLE "concensus_topicaddeduser" CASCADE;
