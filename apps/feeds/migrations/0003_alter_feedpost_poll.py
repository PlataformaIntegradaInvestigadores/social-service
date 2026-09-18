# Historical no-op: FeedPost.poll already has the current definition in feeds.0001_initial.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("feeds", "0002_add_poll_field"),
    ]

    operations = []
