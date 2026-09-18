from django.db import models

from apps.concensus.domain.entities.debate_message import Message
from apps.custom_auth.identity_principal import (
    ref_from_snapshot,
    snapshot_from_principal,
)


class Reaction(models.Model):
    """
    Registra las reacciones ("Me gusta") que hacen los usuarios a los mensajes.
    """

    user_identity_id = models.CharField(max_length=64, db_index=True)
    user_snapshot = models.JSONField(default=dict, blank=True)
    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="reactions"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user_identity_id", "message")

    @property
    def user(self):
        return ref_from_snapshot(self.user_identity_id, self.user_snapshot)

    @user.setter
    def user(self, value):
        self.user_identity_id = str(value.id)
        self.user_snapshot = snapshot_from_principal(value)

    def __str__(self):
        return f"Reaction by {self.user.username} to message {self.message.id}"
