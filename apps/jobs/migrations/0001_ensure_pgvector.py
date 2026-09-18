# Generated manually to ensure pgvector is available for jobs

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("custom_auth", "0002_enable_pgvector"),
    ]

    operations = [
        # This migration ensures pgvector is available before creating vector fields
        # The actual extension creation is handled in custom_auth.0002_enable_pgvector
        migrations.RunSQL(
            "SELECT 1;",  # No-op SQL, just to ensure dependency order
            reverse_sql="SELECT 1;",
        ),
    ]
