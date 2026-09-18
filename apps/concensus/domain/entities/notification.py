from django.db import models

from apps.custom_auth.identity_principal import (
    group_ref_from_snapshot,
    group_snapshot_from_principal,
    ref_from_snapshot,
    snapshot_from_principal,
)


class NotificationPhaseOne(models.Model):
    NOTIFICATION_TYPES = (
        ("new_topic", "New Topic"),
        ("topic_visited", "Topic Visited"),
        ("phase_one_completed", "Phase One Completed"),
        ("combined_search", "Combined Search"),
        ("user_expertise", "User Expertise"),
    )

    user_identity_id = models.CharField(max_length=64, db_index=True)
    user_snapshot = models.JSONField(default=dict, blank=True)
    group_identity_id = models.CharField(max_length=64, db_index=True)
    group_snapshot = models.JSONField(default=dict, blank=True)
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

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
        return f"{self.user.username} - {self.notification_type}"


class NotificationPhaseTwo(models.Model):
    NOTIFICATION_TYPES = (
        ("topic_reorder", "Topic Reorder"),
        ("topic_tag", "Topic Tag"),
        ("consensus_finalized", "Consensus Finalized"),
    )
    user_identity_id = models.CharField(max_length=64, db_index=True)
    user_snapshot = models.JSONField(default=dict, blank=True)
    group_identity_id = models.CharField(max_length=64, db_index=True)
    group_snapshot = models.JSONField(default=dict, blank=True)
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

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
        return f"{self.user.username} - {self.notification_type}"


""" 

TABLA NOTIFICATION_PHASE_ONE

id	|user_id |group_id	|notification_type	|message	                     |created_at	        
----------------------------------------------------------------------------------------------------
1	12345	 67890	    new_topic	        Ricardo Díaz 📥 added Topic 6	 2024-07-01 10:00:00	
2	67891	 12345	    topic_visited	    Carlos Gómez 👀 visited Topic 1	 2024-07-01 10:05:00	

 """

# concensus_notificationphaseone
# select * from "concensus_notificationphaseone";
# select * from "concensus_notificationphasetwo";

# TRUNCATE TABLE "concensus_notificationphasetwo" CASCADE;
