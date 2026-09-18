from django.db import models

from apps.custom_auth.identity_principal import (
    ref_from_snapshot,
    snapshot_from_principal,
)
from apps.jobs.domain.entities.jobs import Jobs


class Postulants(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pendiente"),
        ("reviewing", "En revisión"),
        ("interviewed", "Entrevistado"),
        ("accepted", "Aceptado"),
        ("rejected", "Cancelado"),
        ("withdrawn", "Retirado"),
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
        related_name="applications",
        verbose_name="Trabajo",
    )
    cover_letter = models.TextField(
        null=True, blank=True, verbose_name="Carta de presentación"
    )
    resume_file = models.FileField(
        upload_to="resumes/", null=True, blank=True, verbose_name="Archivo de CV"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", verbose_name="Estado"
    )
    notes = models.TextField(null=True, blank=True, verbose_name="Notas del reclutador")
    applied_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Fecha de aplicación"
    )
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name="Fecha de actualización"
    )

    @property
    def user(self):
        return ref_from_snapshot(self.user_identity_id, self.user_snapshot)

    @user.setter
    def user(self, value):
        self.user_identity_id = str(value.id)
        self.user_snapshot = snapshot_from_principal(value)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.job.title}"

    def get_status_display_name(self):
        """Retorna el nombre del estado en español."""
        return dict(self.STATUS_CHOICES).get(self.status, "Pendiente")

    class Meta:
        db_table = "postulants"
        verbose_name = "Postulante"
        verbose_name_plural = "Postulantes"
        unique_together = (
            "user_identity_id",
            "job",
        )  # Un usuario solo puede aplicar una vez a un trabajo
        ordering = ["-applied_at"]
