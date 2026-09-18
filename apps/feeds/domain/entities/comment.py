"""
Modelo para comentarios recursivos en posts del feed
"""

import uuid

from django.db import models

from apps.custom_auth.identity_principal import (
    ref_from_snapshot,
    snapshot_from_principal,
)


class Comment(models.Model):
    """
    Modelo para comentarios en posts del feed con soporte recursivo
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Referencias
    post = models.ForeignKey(
        "FeedPost",
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="Post",
    )
    author_identity_id = models.CharField(
        max_length=64, db_index=True, verbose_name="ID externo del autor"
    )
    author_snapshot = models.JSONField(
        default=dict, blank=True, verbose_name="Snapshot del autor"
    )

    # Comentario padre para recursividad (None si es comentario de primer nivel)
    parent_comment = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
        verbose_name="Comentario padre",
    )

    # Contenido del comentario
    content = models.TextField(verbose_name="Contenido del comentario")

    # Métricas
    likes_count = models.IntegerField(default=0, verbose_name="Número de likes")
    replies_count = models.IntegerField(default=0, verbose_name="Número de respuestas")

    # Estado
    is_edited = models.BooleanField(default=False, verbose_name="Comentario editado")
    is_deleted = models.BooleanField(default=False, verbose_name="Comentario eliminado")

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Fecha de creación"
    )
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name="Fecha de actualización"
    )

    # Metadatos
    metadata = models.JSONField(
        default=dict, blank=True, verbose_name="Metadatos adicionales"
    )

    class Meta:
        verbose_name = "Comentario"
        verbose_name_plural = "Comentarios"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["post", "created_at"]),
            models.Index(fields=["parent_comment", "created_at"]),
            models.Index(
                fields=["author_identity_id", "-created_at"],
                name="feeds_comme_auth_ident_idx",
            ),
        ]

    @property
    def author(self):
        return ref_from_snapshot(self.author_identity_id, self.author_snapshot)

    @author.setter
    def author(self, value):
        self.author_identity_id = str(value.id)
        self.author_snapshot = snapshot_from_principal(value)

    def __str__(self):
        content_preview = (
            self.content[:50] + "..." if len(self.content) > 50 else self.content
        )
        if self.parent_comment:
            return f"Respuesta de {self.author.username}: {content_preview}"
        else:
            return f"Comentario de {self.author.username}: {content_preview}"

    def get_level(self):
        """
        Retorna el nivel de anidación del comentario
        0 = comentario principal, 1 = primera respuesta, etc.
        """
        level = 0
        current = self.parent_comment
        while current:
            level += 1
            current = current.parent_comment
        return level

    def get_thread_root(self):
        """
        Retorna el comentario raíz del hilo
        """
        current = self
        while current.parent_comment:
            current = current.parent_comment
        return current

    def get_all_descendants(self):
        """
        Retorna todos los comentarios descendientes (respuestas y sub-respuestas)
        """
        descendants = []

        def collect_descendants(comment):
            for reply in comment.replies.filter(is_deleted=False):
                descendants.append(reply)
                collect_descendants(reply)

        collect_descendants(self)
        return descendants

    def can_reply(self, max_depth=5):
        """
        Verifica si se puede responder a este comentario
        """
        return self.get_level() < max_depth

    def update_replies_count(self):
        """
        Actualiza el contador de respuestas directas
        """
        self.replies_count = self.replies.filter(is_deleted=False).count()
        self.save(update_fields=["replies_count"])

    def soft_delete(self):
        """
        Eliminación suave del comentario
        """
        self.is_deleted = True
        self.content = "[Comentario eliminado]"
        self.save(update_fields=["is_deleted", "content"])

        # Actualizar contador del comentario padre
        if self.parent_comment:
            self.parent_comment.update_replies_count()

        # Actualizar contador del post
        self.post.comments_count = self.post.comments.filter(is_deleted=False).count()
        self.post.save(update_fields=["comments_count"])

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)

        if is_new:
            # Actualizar contador del comentario padre
            if self.parent_comment:
                self.parent_comment.update_replies_count()

            # Actualizar contador del post
            self.post.comments_count = self.post.comments.filter(
                is_deleted=False
            ).count()
            self.post.save(update_fields=["comments_count"])

    def get_display_content(self):
        """
        Retorna el contenido a mostrar (considerando si está eliminado)
        """
        if self.is_deleted:
            return "[Comentario eliminado]"
        return self.content
