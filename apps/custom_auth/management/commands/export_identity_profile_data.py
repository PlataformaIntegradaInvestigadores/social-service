from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Comando retirado: la identidad canonica vive en profile_identity_backend."

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING(
                "export_identity_profile_data fue retirado. "
                "La base social ya no contiene usuarios, perfiles, grupos "
                "ni membresias legacy."
            )
        )
