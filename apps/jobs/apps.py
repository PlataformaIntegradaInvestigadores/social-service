from django.apps import AppConfig


class JobsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.jobs"

    def ready(self):
        """
        Importa los signals cuando la app está lista
        """
        import apps.jobs.infrastructure.signals  # noqa: F401
