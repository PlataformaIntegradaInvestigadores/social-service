from django.db import models
from pgvector.django import VectorField

from apps.jobs.domain.entities.company import Company


class Jobs(models.Model):
    EXPERIENCE_CHOICES = [
        ("entry", "Sin experiencia"),
        ("junior", "Junior (1-2 años)"),
        ("mid", "Intermedio (3-5 años)"),
        ("senior", "Senior (5+ años)"),
        ("lead", "Líder técnico (7+ años)"),
    ]

    JOB_TYPE_CHOICES = [
        ("full_time", "Tiempo completo"),
        ("part_time", "Tiempo parcial"),
        ("contract", "Contrato"),
        ("internship", "Prácticas"),
        ("freelance", "Freelance"),
    ]

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="jobs", verbose_name="Empresa"
    )
    title = models.CharField(max_length=255, verbose_name="Título del puesto")
    description = models.TextField(verbose_name="Descripción")
    requirements = models.TextField(null=True, blank=True, verbose_name="Requisitos")
    benefits = models.TextField(null=True, blank=True, verbose_name="Beneficios")
    location = models.CharField(
        max_length=255, null=True, blank=True, verbose_name="Ubicación"
    )
    job_type = models.CharField(
        max_length=20,
        choices=JOB_TYPE_CHOICES,
        default="full_time",
        verbose_name="Tipo de trabajo",
    )
    experience_level = models.CharField(
        max_length=20,
        choices=EXPERIENCE_CHOICES,
        default="entry",
        verbose_name="Nivel de experiencia",
    )
    salary_min = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Salario mínimo",
    )
    salary_max = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Salario máximo",
    )
    is_remote = models.BooleanField(default=False, verbose_name="Trabajo remoto")
    application_deadline = models.DateTimeField(
        null=True, blank=True, verbose_name="Fecha límite de aplicación"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Fecha de creación"
    )
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name="Fecha de actualización"
    )
    # Campo para el vector de embeddings (768 dimensiones según el microservicio)
    embedding = VectorField(
        dimensions=768,
        null=True,
        blank=True,
        verbose_name="Vector de embedding para recomendaciones",
    )

    # Campos para métricas de recomendación
    interactions_score = models.FloatField(
        default=0.0, verbose_name="Score de interacciones"
    )
    view_count = models.IntegerField(
        default=0, verbose_name="Número de visualizaciones"
    )
    application_count = models.IntegerField(
        default=0, verbose_name="Número de aplicaciones"
    )

    def __str__(self):
        return f"{self.title} - {self.company.company_name}"

    def get_experience_display_name(self):
        """Retorna el nombre del nivel de experiencia en español."""
        return dict(self.EXPERIENCE_CHOICES).get(
            self.experience_level, "Sin experiencia"
        )

    def get_job_type_display_name(self):
        """Retorna el nombre del tipo de trabajo en español."""
        return dict(self.JOB_TYPE_CHOICES).get(self.job_type, "Tiempo completo")

    class Meta:
        db_table = "jobs"
        verbose_name = "Trabajo"
        verbose_name_plural = "Trabajos"
        ordering = ["-created_at"]
