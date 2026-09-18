from django.db import models

from apps.concensus.domain.entities.topic import RecommendedTopic
from apps.custom_auth.identity_principal import (
    group_ref_from_snapshot,
    group_snapshot_from_principal,
)


class ConsensusResult(models.Model):
    idGroup_identity_id = models.CharField(max_length=64, db_index=True)
    idGroup_snapshot = models.JSONField(default=dict, blank=True)
    idTopic = models.ForeignKey(RecommendedTopic, on_delete=models.CASCADE)
    final_value = models.FloatField()

    @property
    def idGroup(self):
        return group_ref_from_snapshot(self.idGroup_identity_id, self.idGroup_snapshot)

    @idGroup.setter
    def idGroup(self, value):
        self.idGroup_identity_id = str(value.id)
        self.idGroup_snapshot = group_snapshot_from_principal(value)


# select * from concensus_consensusresult;
