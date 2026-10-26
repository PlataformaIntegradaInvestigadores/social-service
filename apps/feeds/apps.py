from django.apps import AppConfig


class FeedsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.feeds"

    def ready(self):
        # Poll se registra antes que las señales: FeedPost.poll es una
        # referencia lazy a "feeds.Poll" y el chequeo de modelos la exige.
        import apps.feeds.domain.entities.poll  # noqa: F401
        import apps.feeds.infrastructure.signals  # noqa: F401
