"""
Modelo para los posts del feed social
"""

import math
import uuid

from django.db import models
from django.utils import timezone
from pgvector.django import VectorField

from apps.custom_auth.identity_principal import (
    ref_from_snapshot,
    snapshot_from_principal,
)


class FeedPost(models.Model):
    """
    Modelo para posts del feed social
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author_identity_id = models.CharField(
        max_length=64, db_index=True, verbose_name="ID externo del autor"
    )
    author_snapshot = models.JSONField(
        default=dict, blank=True, verbose_name="Snapshot del autor"
    )
    content = models.TextField(verbose_name="Contenido del post")

    # Vector embedding para recomendaciones (768 dimensiones)
    embedding = VectorField(
        dimensions=768,
        null=True,
        blank=True,
        verbose_name="Vector de embedding para recomendaciones",
    )

    # Métricas de interacción
    likes_count = models.IntegerField(default=0, verbose_name="Número de likes")
    comments_count = models.IntegerField(
        default=0, verbose_name="Número de comentarios"
    )
    views_count = models.IntegerField(
        default=0, verbose_name="Número de visualizaciones"
    )
    shares_count = models.IntegerField(default=0, verbose_name="Número de compartidos")

    # Score compuesto para trending
    engagement_score = models.FloatField(
        default=0.0, verbose_name="Score de engagement"
    )

    # Configuración de privacidad
    is_public = models.BooleanField(default=True, verbose_name="Post público")
    is_pinned = models.BooleanField(default=False, verbose_name="Post fijado")

    # Relación con encuesta (opcional)
    poll = models.OneToOneField(
        "feeds.Poll",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="post",
        verbose_name="Encuesta del post",
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Fecha de creación"
    )
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name="Fecha de actualización"
    )

    # Metadatos
    tags = models.JSONField(default=list, blank=True, verbose_name="Tags del post")
    metadata = models.JSONField(
        default=dict, blank=True, verbose_name="Metadatos adicionales"
    )

    class Meta:
        verbose_name = "Post del Feed"
        verbose_name_plural = "Posts del Feed"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["-engagement_score"]),
            models.Index(
                fields=["author_identity_id", "-created_at"],
                name="feeds_feedp_auth_ident_idx",
            ),
            models.Index(
                fields=["-engagement_score", "-created_at"], name="trending_idx"
            ),
        ]

    def __str__(self):
        content_preview = (
            self.content[:50] + "..." if len(self.content) > 50 else self.content
        )
        return f"{self.author.username or self.author_identity_id} - {content_preview}"

    @property
    def author(self):
        return ref_from_snapshot(self.author_identity_id, self.author_snapshot)

    @author.setter
    def author(self, value):
        self.author_identity_id = str(value.id)
        self.author_snapshot = snapshot_from_principal(value)

    def update_engagement_score(self):
        """
        Actualiza el score de engagement basado en interacciones
        """
        # Algoritmo de scoring: likes*1 + comments*2 + shares*3 + views*0.1
        hours_old = (timezone.now() - self.created_at).total_seconds() / 3600

        raw_score = (
            self.likes_count * 1.0
            + self.comments_count * 2.0
            + self.shares_count * 3.0
            + self.views_count * 0.1
        )

        # Evitar división por cero si el post es muy reciente
        if hours_old < 1:
            hours_old = 1

        # Puntuación de engagement ponderada para el decaimiento
        engagement_weight = min(raw_score / 10, 5)  # Limitar a máximo 5x

        # Decaimiento logarítmico ajustado por engagement
        # - Posts con más engagement decaen más lentamente
        # - Uso de logaritmo para un decaimiento más gradual
        # - El factor base 1.5 determina la velocidad de decaimiento
        time_decay = 1 / (
            1 + math.log(hours_old / 24 + 1, 1.5 + (engagement_weight / 10))
        )

        self.engagement_score = raw_score * time_decay
        self.save(update_fields=["engagement_score"])

    def get_files(self):
        """Retorna todos los archivos asociados al post"""
        return self.post_files.all()

    def explain_trending_score(self):
        """
        Explica detalladamente cómo se calcula el score de trending para este post
        """
        hours_old = (timezone.now() - self.created_at).total_seconds() / 3600

        # Calcular raw_score
        raw_score = (
            self.likes_count * 1.0
            + self.comments_count * 2.0
            + self.shares_count * 3.0
            + self.views_count * 0.1
        )

        # Recalcular todos los factores
        engagement_weight = min(raw_score / 10, 5)
        time_decay = 1 / (
            1 + math.log(max(1, hours_old) / 24 + 1, 1.5 + (engagement_weight / 10))
        )
        engagement_score = raw_score * time_decay

        # Calcular trending_score
        velocity_boost = engagement_score / max(1, math.sqrt(max(1, hours_old)))
        trending_score = engagement_score * 0.8 + velocity_boost * 0.2

        return {
            "post_id": str(self.id),
            "created_hours_ago": round(hours_old, 2),
            "likes": self.likes_count,
            "comments": self.comments_count,
            "shares": self.shares_count,
            "views": self.views_count,
            "raw_engagement_score": round(raw_score, 2),
            "engagement_weight": round(engagement_weight, 2),
            "time_decay_factor": round(time_decay, 4),
            "engagement_score": round(engagement_score, 2),
            "velocity_boost": round(velocity_boost, 2),
            "trending_score": round(trending_score, 2),
        }

    def get_images(self):
        """Retorna solo las imágenes del post"""
        return self.post_files.filter(file_type="image")

    def get_documents(self):
        """Retorna solo los documentos del post"""
        return self.post_files.filter(file_type="document")
