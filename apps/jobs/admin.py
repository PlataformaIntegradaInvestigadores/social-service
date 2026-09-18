from django.contrib import admin

from apps.jobs.domain.entities.jobs import Jobs
from apps.jobs.domain.entities.postulants import Postulants


@admin.register(Jobs)
class JobsAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "company",
        "job_type",
        "experience_level",
        "location",
        "is_remote",
        "created_at",
    )
    list_filter = ("job_type", "experience_level", "is_remote", "company", "created_at")
    search_fields = ("title", "description", "company__company_name", "location")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Informacion basica", {"fields": ("company", "title", "description")}),
        (
            "Detalles del puesto",
            {
                "fields": (
                    "job_type",
                    "experience_level",
                    "location",
                    "is_remote",
                    "requirements",
                    "benefits",
                )
            },
        ),
        (
            "Informacion salarial",
            {"fields": ("salary_min", "salary_max"), "classes": ("collapse",)},
        ),
        (
            "Fechas",
            {
                "fields": ("application_deadline", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(Postulants)
class PostulantsAdmin(admin.ModelAdmin):
    list_display = ("user_identity_id", "job", "status", "applied_at")
    list_filter = ("status", "applied_at", "job__company")
    search_fields = (
        "user_identity_id",
        "user_snapshot",
        "job__title",
        "job__company__company_name",
    )
    readonly_fields = ("applied_at", "updated_at")
    raw_id_fields = ("job",)
    fieldsets = (
        (
            "Informacion de la aplicacion",
            {"fields": ("user_identity_id", "user_snapshot", "job", "status")},
        ),
        ("Documentos", {"fields": ("cover_letter", "resume_file")}),
        ("Notas del reclutador", {"fields": ("notes",)}),
        ("Fechas", {"fields": ("applied_at", "updated_at"), "classes": ("collapse",)}),
    )
