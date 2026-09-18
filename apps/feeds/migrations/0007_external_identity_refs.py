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
    FeedPost = apps.get_model("feeds", "FeedPost")
    Comment = apps.get_model("feeds", "Comment")
    Like = apps.get_model("feeds", "Like")
    PollVote = apps.get_model("feeds", "PollVote")

    for post in FeedPost.objects.select_related("author").iterator():
        post.author_identity_id = str(post.author_id)
        post.author_snapshot = _snapshot(post.author)
        post.save(update_fields=["author_identity_id", "author_snapshot"])

    for comment in Comment.objects.select_related("author").iterator():
        comment.author_identity_id = str(comment.author_id)
        comment.author_snapshot = _snapshot(comment.author)
        comment.save(update_fields=["author_identity_id", "author_snapshot"])

    for like in Like.objects.select_related("user").iterator():
        like.user_identity_id = str(like.user_id)
        like.user_snapshot = _snapshot(like.user)
        like.save(update_fields=["user_identity_id", "user_snapshot"])

    for vote in PollVote.objects.select_related("user").iterator():
        vote.user_identity_id = str(vote.user_id)
        vote.user_snapshot = _snapshot(vote.user)
        vote.save(update_fields=["user_identity_id", "user_snapshot"])


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0006_merge_pgvector_and_trending"),
    ]

    operations = [
        migrations.AddField(
            model_name="feedpost",
            name="author_identity_id",
            field=models.CharField(
                db_index=True,
                max_length=64,
                null=True,
                verbose_name="ID externo del autor",
            ),
        ),
        migrations.AddField(
            model_name="feedpost",
            name="author_snapshot",
            field=models.JSONField(
                blank=True, default=dict, verbose_name="Snapshot del autor"
            ),
        ),
        migrations.AddField(
            model_name="comment",
            name="author_identity_id",
            field=models.CharField(
                db_index=True,
                max_length=64,
                null=True,
                verbose_name="ID externo del autor",
            ),
        ),
        migrations.AddField(
            model_name="comment",
            name="author_snapshot",
            field=models.JSONField(
                blank=True, default=dict, verbose_name="Snapshot del autor"
            ),
        ),
        migrations.AddField(
            model_name="like",
            name="user_identity_id",
            field=models.CharField(
                db_index=True,
                max_length=64,
                null=True,
                verbose_name="ID externo del usuario",
            ),
        ),
        migrations.AddField(
            model_name="like",
            name="user_snapshot",
            field=models.JSONField(
                blank=True, default=dict, verbose_name="Snapshot del usuario"
            ),
        ),
        migrations.AddField(
            model_name="pollvote",
            name="user_identity_id",
            field=models.CharField(db_index=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="pollvote",
            name="user_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(copy_identity_refs, migrations.RunPython.noop),
        migrations.RemoveIndex(
            model_name="feedpost",
            name="feeds_feedp_author__d5088f_idx",
        ),
        migrations.RemoveIndex(
            model_name="comment",
            name="feeds_comme_author__e3556e_idx",
        ),
        migrations.RemoveIndex(
            model_name="like",
            name="feeds_like_user_id_066e8a_idx",
        ),
        migrations.AlterUniqueTogether(
            name="like",
            unique_together={("user_identity_id", "content_type", "object_id")},
        ),
        migrations.AlterUniqueTogether(
            name="pollvote",
            unique_together={("user_identity_id", "poll", "option")},
        ),
        migrations.RemoveField(
            model_name="feedpost",
            name="author",
        ),
        migrations.RemoveField(
            model_name="comment",
            name="author",
        ),
        migrations.RemoveField(
            model_name="like",
            name="user",
        ),
        migrations.RemoveField(
            model_name="pollvote",
            name="user",
        ),
        migrations.AlterField(
            model_name="feedpost",
            name="author_identity_id",
            field=models.CharField(
                db_index=True, max_length=64, verbose_name="ID externo del autor"
            ),
        ),
        migrations.AlterField(
            model_name="comment",
            name="author_identity_id",
            field=models.CharField(
                db_index=True, max_length=64, verbose_name="ID externo del autor"
            ),
        ),
        migrations.AlterField(
            model_name="like",
            name="user_identity_id",
            field=models.CharField(
                db_index=True, max_length=64, verbose_name="ID externo del usuario"
            ),
        ),
        migrations.AlterField(
            model_name="pollvote",
            name="user_identity_id",
            field=models.CharField(db_index=True, max_length=64),
        ),
        migrations.AddIndex(
            model_name="feedpost",
            index=models.Index(
                fields=["author_identity_id", "-created_at"],
                name="feeds_feedp_auth_ident_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="comment",
            index=models.Index(
                fields=["author_identity_id", "-created_at"],
                name="feeds_comme_auth_ident_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="like",
            index=models.Index(
                fields=["user_identity_id", "-created_at"],
                name="feeds_like_user_identity_idx",
            ),
        ),
    ]
