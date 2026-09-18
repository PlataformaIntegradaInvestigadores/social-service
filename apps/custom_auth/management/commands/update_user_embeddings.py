from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Comando retirado: los embeddings de investigador ya no pertenecen "
        "a la base social."
    )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING(
                "update_user_embeddings fue retirado. "
                "La identidad canonica vive en profile_identity_backend."
            )
        )
