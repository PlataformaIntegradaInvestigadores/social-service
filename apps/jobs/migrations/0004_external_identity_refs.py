from django.db import migrations, models


def _snapshot(user):
    if not user:
        return {}
    return {
        "id": str(user.pk),
        "username": getattr(user, "username", "") or "",
        "first_name": getattr(user, "first_name", "") or "",
        "last_name": getattr(user, "last_name", "") or "",
        "profile_picture": str(getattr(user, "profile_picture", "") or ""),
    }


def copy_identity_refs(apps, schema_editor):
    Postulants = apps.get_model("jobs", "Postulants")
    for postulant in Postulants.objects.select_related("user").iterator():
        postulant.user_identity_id = str(postulant.user_id)
        postulant.user_snapshot = _snapshot(postulant.user)
        postulant.save(update_fields=["user_identity_id", "user_snapshot"])


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0003_merge_pgvector_and_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="postulants",
            name="user_identity_id",
            field=models.CharField(
                db_index=True,
                max_length=64,
                null=True,
                verbose_name="ID externo del usuario",
            ),
        ),
        migrations.AddField(
            model_name="postulants",
            name="user_snapshot",
            field=models.JSONField(
                blank=True, default=dict, verbose_name="Snapshot del usuario"
            ),
        ),
        migrations.RunPython(copy_identity_refs, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name="postulants",
            unique_together={("user_identity_id", "job")},
        ),
        migrations.RemoveField(
            model_name="postulants",
            name="user",
        ),
        migrations.AlterField(
            model_name="postulants",
            name="user_identity_id",
            field=models.CharField(
                db_index=True, max_length=64, verbose_name="ID externo del usuario"
            ),
        ),
    ]
