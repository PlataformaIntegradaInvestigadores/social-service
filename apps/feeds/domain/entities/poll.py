import uuid

from django.db import models

from apps.custom_auth.identity_principal import (
    ref_from_snapshot,
    snapshot_from_principal,
)


class Poll(models.Model):
    """
    Modelo para encuestas en posts del feed.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.TextField(max_length=500)
    is_multiple_choice = models.BooleanField(default=False)
    is_anonymous = models.BooleanField(default=False)
    allows_other = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "feed_polls"
        verbose_name = "Poll"
        verbose_name_plural = "Polls"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Poll: {self.question[:50]}..."

    @property
    def total_votes(self):
        return sum(option.votes_count for option in self.options.all())

    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        from django.utils import timezone

        return timezone.now() > self.expires_at


class PollOption(models.Model):
    """
    Modelo para opciones de encuestas.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    poll = models.ForeignKey(
        "feeds.Poll", on_delete=models.CASCADE, related_name="options"
    )
    text = models.CharField(max_length=200)
    votes_count = models.PositiveIntegerField(default=0)
    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "feed_poll_options"
        verbose_name = "Poll Option"
        verbose_name_plural = "Poll Options"
        ordering = ["order", "created_at"]
        unique_together = ["poll", "order"]

    def __str__(self):
        return f"{self.poll.question[:30]}... - {self.text}"


class PollVote(models.Model):
    """
    Modelo para votos en encuestas.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_identity_id = models.CharField(max_length=64, db_index=True)
    user_snapshot = models.JSONField(default=dict, blank=True)
    poll = models.ForeignKey(
        "feeds.Poll", on_delete=models.CASCADE, related_name="votes"
    )
    option = models.ForeignKey(
        "feeds.PollOption", on_delete=models.CASCADE, related_name="votes"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "feed_poll_votes"
        verbose_name = "Poll Vote"
        verbose_name_plural = "Poll Votes"
        unique_together = ["user_identity_id", "poll", "option"]
        ordering = ["-created_at"]

    @property
    def user(self):
        return ref_from_snapshot(self.user_identity_id, self.user_snapshot)

    @user.setter
    def user(self, value):
        self.user_identity_id = str(value.id)
        self.user_snapshot = snapshot_from_principal(value)

    def __str__(self):
        return f"{self.user.username} voted for {self.option.text}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)

        if is_new:
            self.option.votes_count = self.option.votes.count()
            self.option.save(update_fields=["votes_count"])

    def delete(self, *args, **kwargs):
        option = self.option
        super().delete(*args, **kwargs)

        option.votes_count = option.votes.count()
        option.save(update_fields=["votes_count"])
