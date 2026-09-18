from django.db import models

from apps.concensus.domain.entities.debate import Debate
from apps.custom_auth.identity_principal import (
    ref_from_snapshot,
    snapshot_from_principal,
)


class DebateParticipant(models.Model):
    debate = models.ForeignKey(
        Debate, on_delete=models.CASCADE, related_name="participants"
    )
    participant_identity_id = models.CharField(max_length=64, db_index=True)
    participant_snapshot = models.JSONField(default=dict, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    is_collaborator = models.BooleanField(default=False)

    @property
    def participant(self):
        return ref_from_snapshot(
            self.participant_identity_id, self.participant_snapshot
        )

    @participant.setter
    def participant(self, value):
        self.participant_identity_id = str(value.id)
        self.participant_snapshot = snapshot_from_principal(value)

    def __str__(self):
        return f"{self.participant.username} in debate {self.debate.title}"

    class Meta:
        db_table = "debate_participants"
