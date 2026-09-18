from django.db import models
from django.utils.timezone import now

from apps.custom_auth.identity_principal import (
    group_ref_from_snapshot,
    group_snapshot_from_principal,
)


class Debate(models.Model):
    group_identity_id = models.CharField(max_length=64, db_index=True)
    group_snapshot = models.JSONField(default=dict, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    end_time = models.DurationField()
    is_closed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.title} - {self.group.title}"

    @property
    def group(self):
        return group_ref_from_snapshot(self.group_identity_id, self.group_snapshot)

    @group.setter
    def group(self, value):
        self.group_identity_id = str(value.id)
        self.group_snapshot = group_snapshot_from_principal(value)

    class Meta:
        db_table = "debates"

    def is_time_exceeded(self):
        """
        Comprueba si el tiempo del debate ha expirado.
        """
        return now() >= self.get_closing_time()

    def get_closing_time(self):
        """
        Calcula la fecha y hora exacta en que debe cerrarse el debate.
        """
        return self.created_at + self.end_time
