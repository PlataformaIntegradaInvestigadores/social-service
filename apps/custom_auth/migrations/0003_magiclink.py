# Kept as a no-op to preserve the historical migration graph.
# MagicLink is defined by 0002_magiclink.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("custom_auth", "0002_enable_pgvector"),
    ]

    operations = []
