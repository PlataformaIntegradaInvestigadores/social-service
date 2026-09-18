from django.db import models

from apps.custom_auth.identity_principal import (
    group_ref_from_snapshot,
    group_snapshot_from_principal,
    ref_from_snapshot,
    snapshot_from_principal,
)


class UserSatisfaction(models.Model):
    SATISFACTION_CHOICES = [
        ("Unsatisfied", "Unsatisfied"),
        ("Slightly Unsatisfied", "Slightly Unsatisfied"),
        ("Neutral", "Neutral"),
        ("Slightly Satisfied", "Slightly Satisfied"),
        ("Satisfied", "Satisfied"),
    ]

    user_identity_id = models.CharField(max_length=64, db_index=True)
    user_snapshot = models.JSONField(default=dict, blank=True)
    group_identity_id = models.CharField(max_length=64, db_index=True)
    group_snapshot = models.JSONField(default=dict, blank=True)
    satisfaction_level = models.CharField(max_length=20, choices=SATISFACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    message = models.TextField()

    class Meta:
        unique_together = ("user_identity_id", "group_identity_id")

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


# select * from concensus_usersatisfaction;
# truncate table concensus_usersatisfaction;
