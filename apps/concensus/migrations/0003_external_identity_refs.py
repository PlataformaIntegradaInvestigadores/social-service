from django.db import migrations, models


def _user_snapshot(user):
    if not user:
        return {}
    return {
        "id": str(user.pk),
        "username": getattr(user, "username", "") or "",
        "first_name": getattr(user, "first_name", "") or "",
        "last_name": getattr(user, "last_name", "") or "",
        "profile_picture": str(getattr(user, "profile_picture", "") or ""),
    }


def _group_snapshot(group):
    if not group:
        return {}
    return {
        "id": str(group.pk),
        "name": getattr(group, "name", "") or "",
        "title": getattr(group, "title", "") or "",
    }


def copy_identity_refs(apps, schema_editor):
    raw_id_models = {"Topic"}
    model_specs = [
        (
            "RecommendedTopic",
            [("group", "group_identity_id", "group_snapshot", _group_snapshot)],
        ),
        (
            "ConsensusResult",
            [("idGroup", "idGroup_identity_id", "idGroup_snapshot", _group_snapshot)],
        ),
        ("Debate", [("group", "group_identity_id", "group_snapshot", _group_snapshot)]),
        (
            "DebateParticipant",
            [
                (
                    "participant",
                    "participant_identity_id",
                    "participant_snapshot",
                    _user_snapshot,
                )
            ],
        ),
        (
            "FinalTopicOrder",
            [
                ("idGroup", "idGroup_identity_id", "idGroup_snapshot", _group_snapshot),
                ("idUser", "idUser_identity_id", "idUser_snapshot", _user_snapshot),
            ],
        ),
        (
            "Message",
            [
                ("user", "user_identity_id", "user_snapshot", _user_snapshot),
                ("group", "group_identity_id", "group_snapshot", _group_snapshot),
            ],
        ),
        (
            "NotificationPhaseOne",
            [
                ("user", "user_identity_id", "user_snapshot", _user_snapshot),
                ("group", "group_identity_id", "group_snapshot", _group_snapshot),
            ],
        ),
        (
            "NotificationPhaseTwo",
            [
                ("user", "user_identity_id", "user_snapshot", _user_snapshot),
                ("group", "group_identity_id", "group_snapshot", _group_snapshot),
            ],
        ),
        ("Reaction", [("user", "user_identity_id", "user_snapshot", _user_snapshot)]),
        ("Topic", [("group", "group_identity_id", "group_snapshot", _group_snapshot)]),
        (
            "TopicAddedUser",
            [
                ("user", "user_identity_id", "user_snapshot", _user_snapshot),
                ("group", "group_identity_id", "group_snapshot", _group_snapshot),
            ],
        ),
        (
            "UserExpertise",
            [
                ("user", "user_identity_id", "user_snapshot", _user_snapshot),
                ("group", "group_identity_id", "group_snapshot", _group_snapshot),
            ],
        ),
        (
            "UserPhase",
            [
                ("user", "user_identity_id", "user_snapshot", _user_snapshot),
                ("group", "group_identity_id", "group_snapshot", _group_snapshot),
            ],
        ),
        (
            "UserPosture",
            [("user", "user_identity_id", "user_snapshot", _user_snapshot)],
        ),
        (
            "UserSatisfaction",
            [
                ("user", "user_identity_id", "user_snapshot", _user_snapshot),
                ("group", "group_identity_id", "group_snapshot", _group_snapshot),
            ],
        ),
    ]

    for model_name, refs in model_specs:
        model = apps.get_model("concensus", model_name)
        queryset = model.objects.all()
        if model_name not in raw_id_models:
            related = [old for old, _identity, _snapshot, _fn in refs]
            queryset = queryset.select_related(*related)
        for obj in queryset.iterator():
            update_fields = []
            for old, identity_field, snapshot_field, snapshot_fn in refs:
                old_id = getattr(obj, f"{old}_id", None)
                setattr(obj, identity_field, None if old_id is None else str(old_id))
                old_obj = (
                    None if model_name in raw_id_models else getattr(obj, old, None)
                )
                setattr(obj, snapshot_field, snapshot_fn(old_obj))
                update_fields.extend([identity_field, snapshot_field])
            obj.save(update_fields=update_fields)


def add_identity_fields(model_name, user_fields=(), group_fields=()):
    operations = []
    for name, nullable in user_fields:
        operations.extend(
            [
                migrations.AddField(
                    model_name=model_name,
                    name=f"{name}_identity_id",
                    field=models.CharField(
                        db_index=True, max_length=64, null=True, blank=nullable
                    ),
                ),
                migrations.AddField(
                    model_name=model_name,
                    name=f"{name}_snapshot",
                    field=models.JSONField(blank=True, default=dict),
                ),
            ]
        )
    for name, nullable in group_fields:
        operations.extend(
            [
                migrations.AddField(
                    model_name=model_name,
                    name=f"{name}_identity_id",
                    field=models.CharField(
                        db_index=True, max_length=64, null=True, blank=nullable
                    ),
                ),
                migrations.AddField(
                    model_name=model_name,
                    name=f"{name}_snapshot",
                    field=models.JSONField(blank=True, default=dict),
                ),
            ]
        )
    return operations


class Migration(migrations.Migration):
    dependencies = [
        ("concensus", "0002_initial"),
    ]

    operations = [
        *add_identity_fields("recommendedtopic", group_fields=[("group", True)]),
        *add_identity_fields("consensusresult", group_fields=[("idGroup", False)]),
        *add_identity_fields("debate", group_fields=[("group", False)]),
        *add_identity_fields("debateparticipant", user_fields=[("participant", False)]),
        *add_identity_fields(
            "finaltopicorder",
            user_fields=[("idUser", False)],
            group_fields=[("idGroup", False)],
        ),
        *add_identity_fields(
            "message", user_fields=[("user", False)], group_fields=[("group", True)]
        ),
        *add_identity_fields(
            "notificationphaseone",
            user_fields=[("user", False)],
            group_fields=[("group", False)],
        ),
        *add_identity_fields(
            "notificationphasetwo",
            user_fields=[("user", False)],
            group_fields=[("group", False)],
        ),
        *add_identity_fields("reaction", user_fields=[("user", False)]),
        *add_identity_fields("topic", group_fields=[("group", False)]),
        *add_identity_fields(
            "topicaddeduser",
            user_fields=[("user", False)],
            group_fields=[("group", False)],
        ),
        *add_identity_fields(
            "userexpertise",
            user_fields=[("user", False)],
            group_fields=[("group", False)],
        ),
        *add_identity_fields(
            "userphase", user_fields=[("user", False)], group_fields=[("group", False)]
        ),
        *add_identity_fields("userposture", user_fields=[("user", False)]),
        *add_identity_fields(
            "usersatisfaction",
            user_fields=[("user", False)],
            group_fields=[("group", False)],
        ),
        migrations.RunPython(copy_identity_refs, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name="finaltopicorder",
            unique_together={("idGroup_identity_id", "idUser_identity_id", "idTopic")},
        ),
        migrations.AlterUniqueTogether(
            name="reaction",
            unique_together={("user_identity_id", "message")},
        ),
        migrations.AlterUniqueTogether(
            name="userexpertise",
            unique_together={("user_identity_id", "group_identity_id", "topic")},
        ),
        migrations.AlterUniqueTogether(
            name="userposture",
            unique_together={("user_identity_id", "debate")},
        ),
        migrations.AlterUniqueTogether(
            name="usersatisfaction",
            unique_together={("user_identity_id", "group_identity_id")},
        ),
        migrations.RemoveField("recommendedtopic", "group"),
        migrations.RemoveField("consensusresult", "idGroup"),
        migrations.RemoveField("debate", "group"),
        migrations.RemoveField("debateparticipant", "participant"),
        migrations.RemoveField("finaltopicorder", "idGroup"),
        migrations.RemoveField("finaltopicorder", "idUser"),
        migrations.RemoveField("message", "group"),
        migrations.RemoveField("message", "user"),
        migrations.RemoveField("notificationphaseone", "group"),
        migrations.RemoveField("notificationphaseone", "user"),
        migrations.RemoveField("notificationphasetwo", "group"),
        migrations.RemoveField("notificationphasetwo", "user"),
        migrations.RemoveField("reaction", "user"),
        migrations.RemoveField("topic", "group"),
        migrations.RemoveField("topicaddeduser", "group"),
        migrations.RemoveField("topicaddeduser", "user"),
        migrations.RemoveField("userexpertise", "group"),
        migrations.RemoveField("userexpertise", "user"),
        migrations.RemoveField("userphase", "group"),
        migrations.RemoveField("userphase", "user"),
        migrations.RemoveField("userposture", "user"),
        migrations.RemoveField("usersatisfaction", "group"),
        migrations.RemoveField("usersatisfaction", "user"),
        migrations.AlterField(
            "consensusresult",
            "idGroup_identity_id",
            models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterField(
            "debate",
            "group_identity_id",
            models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterField(
            "debateparticipant",
            "participant_identity_id",
            models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterField(
            "finaltopicorder",
            "idGroup_identity_id",
            models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterField(
            "finaltopicorder",
            "idUser_identity_id",
            models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterField(
            "message",
            "user_identity_id",
            models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterField(
            "notificationphaseone",
            "group_identity_id",
            models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterField(
            "notificationphaseone",
            "user_identity_id",
            models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterField(
            "notificationphasetwo",
            "group_identity_id",
            models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterField(
            "notificationphasetwo",
            "user_identity_id",
            models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterField(
            "reaction",
            "user_identity_id",
            models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterField(
            "topic", "group_identity_id", models.CharField(db_index=True, max_length=64)
        ),
        migrations.AlterField(
            "topicaddeduser",
            "group_identity_id",
            models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterField(
            "topicaddeduser",
            "user_identity_id",
            models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterField(
            "userexpertise",
            "group_identity_id",
            models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterField(
            "userexpertise",
            "user_identity_id",
            models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterField(
            "userphase",
            "group_identity_id",
            models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterField(
            "userphase",
            "user_identity_id",
            models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterField(
            "userposture",
            "user_identity_id",
            models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterField(
            "usersatisfaction",
            "group_identity_id",
            models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterField(
            "usersatisfaction",
            "user_identity_id",
            models.CharField(db_index=True, max_length=64),
        ),
    ]
