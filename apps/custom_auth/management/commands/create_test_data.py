from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Comando retirado: no se crean investigadores locales en "
        "social_consensus_backend."
    )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING(
                "create_test_data fue retirado para identidad local. "
                "Cree investigadores desde profile_identity_backend."
            )
        )
