"""
Campos de moderación (hatespeech-service) compartidos por posts y comentarios.

El contenido se publica de inmediato con ``moderation_status=pending``; una
tarea de Celery lo clasifica en segundo plano y copia aquí el resultado
(visibilidad, p_hate, motivos) para que los serializers no dependan de que
hatespeech-service esté disponible al leer.
"""

from django.db import models


class ModerationStatus(models.TextChoices):
    PENDING = "pending", "Pendiente de clasificar"
    CLASSIFIED = "classified", "Clasificado"
    FAILED = "failed", "Clasificación fallida"


class Visibility(models.TextChoices):
    VISIBLE = "visible", "Visible"
    HIDDEN = "hidden", "Oculto con advertencia"
    BLOCKED = "blocked", "Bloqueado"


class ReviewStatus(models.TextChoices):
    NONE = "none", "Sin revisión"
    PENDING = "pending", "Pendiente de revisión"
    RESOLVED = "resolved", "Resuelto"


class ModeratedContent(models.Model):
    moderation_status = models.CharField(
        max_length=16,
        choices=ModerationStatus.choices,
        default=ModerationStatus.PENDING,
        db_index=True,
        verbose_name="Estado de clasificación",
    )
    visibility = models.CharField(
        max_length=16,
        choices=Visibility.choices,
        default=Visibility.VISIBLE,
        db_index=True,
        verbose_name="Visibilidad",
    )
    p_hate = models.FloatField(null=True, blank=True, verbose_name="P(odio)")
    hate_label = models.CharField(
        max_length=16, blank=True, default="", verbose_name="Etiqueta del modelo"
    )
    review_status = models.CharField(
        max_length=16,
        choices=ReviewStatus.choices,
        default=ReviewStatus.NONE,
        verbose_name="Estado de revisión",
    )
    moderation_reasons = models.JSONField(
        default=list, blank=True, verbose_name="Motivos de moderación"
    )
    report_count = models.PositiveIntegerField(
        default=0, verbose_name="Reportes recibidos"
    )
    moderation_case_id = models.BigIntegerField(
        null=True, blank=True, verbose_name="Caso en hatespeech-service"
    )
    moderated_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Última sincronización de moderación"
    )

    class Meta:
        abstract = True

    @property
    def show_warning(self) -> bool:
        return self.visibility == Visibility.HIDDEN

    @property
    def is_blocked(self) -> bool:
        return self.visibility == Visibility.BLOCKED

    @property
    def sort_last(self) -> bool:
        return self.visibility != Visibility.VISIBLE
