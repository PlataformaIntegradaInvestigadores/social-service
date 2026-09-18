# models.py
from django.db import models

from apps.custom_auth.identity_principal import (
    group_ref_from_snapshot,
    group_snapshot_from_principal,
    ref_from_snapshot,
    snapshot_from_principal,
)


class FinalTopicOrder(models.Model):
    id = models.AutoField(primary_key=True)
    idGroup_identity_id = models.CharField(max_length=64, db_index=True)
    idGroup_snapshot = models.JSONField(default=dict, blank=True)
    idUser_identity_id = models.CharField(max_length=64, db_index=True)
    idUser_snapshot = models.JSONField(default=dict, blank=True)
    idTopic = models.ForeignKey("concensus.RecommendedTopic", on_delete=models.CASCADE)
    posFinal = models.IntegerField()
    label = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        unique_together = ("idGroup_identity_id", "idUser_identity_id", "idTopic")

    @property
    def idGroup(self):
        return group_ref_from_snapshot(self.idGroup_identity_id, self.idGroup_snapshot)

    @idGroup.setter
    def idGroup(self, value):
        self.idGroup_identity_id = str(value.id)
        self.idGroup_snapshot = group_snapshot_from_principal(value)

    @property
    def idUser(self):
        return ref_from_snapshot(self.idUser_identity_id, self.idUser_snapshot)

    @idUser.setter
    def idUser(self, value):
        self.idUser_identity_id = str(value.id)
        self.idUser_snapshot = snapshot_from_principal(value)

    def __str__(self):
        return (
            f"Group {self.idGroup}, User {self.idUser}, "
            f"Topic {self.idTopic}, Position {self.posFinal}"
        )
