from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("custom_auth", "0004_merge_0002_magiclink_0003_magiclink"),
        ("feeds", "0007_external_identity_refs"),
        ("jobs", "0005_external_identity_jobinteraction"),
        ("concensus", "0003_external_identity_refs"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    "DROP TABLE IF EXISTS custom_auth_magiclink CASCADE;",
                    migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    "DROP TABLE IF EXISTS profiles_information CASCADE;",
                    migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    "DROP TABLE IF EXISTS group_users CASCADE;", migrations.RunSQL.noop
                ),
                migrations.RunSQL(
                    "DROP TABLE IF EXISTS groups CASCADE;", migrations.RunSQL.noop
                ),
                migrations.RunSQL(
                    "DROP TABLE IF EXISTS users_groups CASCADE;", migrations.RunSQL.noop
                ),
                migrations.RunSQL(
                    "DROP TABLE IF EXISTS users_user_permissions CASCADE;",
                    migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    "DROP TABLE IF EXISTS users CASCADE;", migrations.RunSQL.noop
                ),
            ],
            state_operations=[
                migrations.RemoveField(
                    model_name="profileinformation",
                    name="user",
                ),
                migrations.DeleteModel(
                    name="MagicLink",
                ),
                migrations.DeleteModel(
                    name="ProfileInformation",
                ),
                migrations.DeleteModel(
                    name="GroupUser",
                ),
                migrations.DeleteModel(
                    name="Group",
                ),
                migrations.DeleteModel(
                    name="User",
                ),
            ],
        ),
    ]
