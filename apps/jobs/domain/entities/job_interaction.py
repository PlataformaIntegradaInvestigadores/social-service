from django.db import models

from apps.custom_auth.identity_principal import (
    ref_from_snapshot,
    snapshot_from_principal,
)
from apps.jobs.domain.entities.jobs import Jobs


class JobInteraction(models.Model):
    INTERACTION_TYPES = [
        ("view", "Vista"),
        ("application", "Aplicacion"),
        ("save", "Guardado"),
        ("share", "Compartido"),
        ("click", "Click en detalles"),
    ]

    user_identity_id = models.CharField(
        max_length=64, db_index=True, verbose_name="ID externo del usuario"
    )
    user_snapshot = models.JSONField(
        default=dict, blank=True, verbose_name="Snapshot del usuario"
    )
    job = models.ForeignKey(
        Jobs,
        on_delete=models.CASCADE,
        related_name="user_interactions",
        verbose_name="Job",
    )
    interaction_type = models.CharField(
        max_length=20, choices=INTERACTION_TYPES, verbose_name="Tipo de interaccion"
    )
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Fecha y hora")
    metadata = models.JSONField(
        default=dict, blank=True, verbose_name="Metadatos adicionales"
    )

    @property
    def user(self):
        return ref_from_snapshot(self.user_identity_id, self.user_snapshot)

    @user.setter
    def user(self, value):
        self.user_identity_id = str(value.id)
        self.user_snapshot = snapshot_from_principal(value)

    class Meta:
        unique_together = ["user_identity_id", "job", "interaction_type"]
        indexes = [
            models.Index(
                fields=["user_identity_id", "timestamp"],
                name="jobs_jobint_user_ident_idx",
            ),
            models.Index(
                fields=["job", "interaction_type"], name="jobs_jobint_job_type_idx"
            ),
            models.Index(fields=["timestamp"], name="jobs_jobint_ts_idx"),
        ]
        verbose_name = "Interaccion con Job"
        verbose_name_plural = "Interacciones con Jobs"

    def __str__(self):
        return f"{self.user.username} - {self.job.title} - {self.interaction_type}"
