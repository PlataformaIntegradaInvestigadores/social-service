from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Comando retirado: la semilla de investigadores pertenece a "
        "profile_identity_backend."
    )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING(
                "seed_presentation_data fue retirado para identidad local. "
                "Use profile_identity_backend para investigadores/perfiles/grupos."
            )
        )
