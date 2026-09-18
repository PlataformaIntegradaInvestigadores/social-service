# Generated manually to enable pgvector extension

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("custom_auth", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            "CREATE EXTENSION IF NOT EXISTS vector;",
            reverse_sql="DROP EXTENSION IF EXISTS vector;",
        ),
    ]
