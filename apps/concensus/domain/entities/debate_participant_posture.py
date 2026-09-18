from django.db import models

from apps.concensus.domain.entities.debate import Debate
from apps.custom_auth.identity_principal import (
    ref_from_snapshot,
    snapshot_from_principal,
)


class UserPosture(models.Model):
    """
    Registra la postura de un usuario respecto a un debate.
    """

    POSTURES = (
        ("agree", "De acuerdo"),
        ("disagree", "No de acuerdo"),
        ("neutral", "Neutral"),
    )

    user_identity_id = models.CharField(max_length=64, db_index=True)
    user_snapshot = models.JSONField(default=dict, blank=True)
    debate = models.ForeignKey(
        Debate, on_delete=models.CASCADE, related_name="postures"
    )
    posture = models.CharField(max_length=10, choices=POSTURES)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user_identity_id", "debate")

    @property
    def user(self):
        return ref_from_snapshot(self.user_identity_id, self.user_snapshot)

    @user.setter
    def user(self, value):
        self.user_identity_id = str(value.id)
        self.user_snapshot = snapshot_from_principal(value)

    def __str__(self):
        return f"{self.user.username} - {self.posture} - {self.debate.title}"
