from django.db import models

from apps.concensus.domain.entities.debate import Debate
from apps.custom_auth.identity_principal import (
    group_ref_from_snapshot,
    group_snapshot_from_principal,
    ref_from_snapshot,
    snapshot_from_principal,
)


class Message(models.Model):
    """
    Representa un mensaje dentro del chat grupal de un debate.
    """

    POSTURES = (
        ("agree", "De acuerdo"),
        ("disagree", "No de acuerdo"),
        ("neutral", "Neutral"),
    )

    user_identity_id = models.CharField(max_length=64, db_index=True)
    user_snapshot = models.JSONField(default=dict, blank=True)
    group_identity_id = models.CharField(
        max_length=64, db_index=True, null=True, blank=True
    )
    group_snapshot = models.JSONField(default=dict, blank=True)
    debate = models.ForeignKey(
        Debate, on_delete=models.CASCADE, related_name="messages"
    )
    text = models.TextField()
    posture = models.CharField(max_length=10, choices=POSTURES, default="neutral")
    parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="replies"
    )
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
        return f"Message by {self.user.username} in {self.debate.title}"
