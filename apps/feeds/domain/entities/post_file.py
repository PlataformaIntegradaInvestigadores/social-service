"""
Modelo para archivos adjuntos en posts (imágenes, documentos, etc.)
"""

import os
import uuid

from django.db import models


def get_post_file_path(instance, filename):
    """Genera ruta para archivos de posts"""
    ext = filename.split(".")[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return f"feed_posts/{instance.post.id}/{filename}"


class PostFile(models.Model):
    """
    Modelo para archivos adjuntos en posts del feed
    """

    FILE_TYPE_CHOICES = [
        ("image", "Imagen"),
        ("document", "Documento"),
        ("video", "Video"),
        ("audio", "Audio"),
        ("other", "Otro"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(
        "FeedPost",
        on_delete=models.CASCADE,
        related_name="post_files",
        verbose_name="Post",
    )

    file = models.FileField(upload_to=get_post_file_path, verbose_name="Archivo")
    file_type = models.CharField(
        max_length=20, choices=FILE_TYPE_CHOICES, verbose_name="Tipo de archivo"
    )
    file_size = models.BigIntegerField(verbose_name="Tamaño del archivo en bytes")
    original_filename = models.CharField(
        max_length=255, verbose_name="Nombre original del archivo"
    )

    # Metadatos específicos para imágenes
    width = models.IntegerField(
        null=True, blank=True, verbose_name="Ancho (para imágenes)"
    )
    height = models.IntegerField(
        null=True, blank=True, verbose_name="Alto (para imágenes)"
    )

    # Descripción alternativa para accesibilidad
    alt_text = models.CharField(
        max_length=255, blank=True, verbose_name="Texto alternativo"
    )

    # Timestamps
    uploaded_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Fecha de subida"
    )

    class Meta:
        verbose_name = "Archivo de Post"
        verbose_name_plural = "Archivos de Posts"
        ordering = ["uploaded_at"]

    def __str__(self):
        return f"{self.original_filename} ({self.file_type})"

    def get_file_extension(self):
        """Retorna la extensión del archivo"""
        return os.path.splitext(self.original_filename)[1].lower()

    def is_image(self):
        """Verifica si es una imagen"""
        return self.file_type == "image"

    def is_document(self):
        """Verifica si es un documento"""
        return self.file_type == "document"

    def get_file_size_mb(self):
        """Retorna el tamaño en MB"""
        return round(self.file_size / (1024 * 1024), 2)

    def save(self, *args, **kwargs):
        # Guardar tamaño del archivo
        if self.file and not self.file_size:
            self.file_size = self.file.size

        # Guardar nombre original
        if self.file and not self.original_filename:
            self.original_filename = self.file.name

        # Auto-detectar tipo de archivo si no se especifica
        # (debe ir despues de fijar original_filename, de la que depende
        # get_file_extension())
        if not self.file_type and self.file:
            ext = self.get_file_extension()
            if ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"]:
                self.file_type = "image"
            elif ext in [".pdf", ".doc", ".docx", ".txt", ".rtf"]:
                self.file_type = "document"
            elif ext in [".mp4", ".avi", ".mov", ".webm"]:
                self.file_type = "video"
            elif ext in [".mp3", ".wav", ".ogg"]:
                self.file_type = "audio"
            else:
                self.file_type = "other"

        super().save(*args, **kwargs)
