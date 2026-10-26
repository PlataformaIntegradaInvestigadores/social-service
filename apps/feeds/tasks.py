"""
Tareas de Celery de moderación.

El contenido se publica sin esperar al modelo; ``classify_content`` lo envía a
hatespeech-service en segundo plano. Si el servicio está caído se reintenta
con backoff exponencial y, si se agotan los reintentos, queda ``failed`` para
que ``sweep_pending_moderation`` lo vuelva a encolar cuando el servicio
responda.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.feeds.domain.entities.comment import Comment
from apps.feeds.domain.entities.moderation import ModerationStatus
from apps.feeds.domain.services import moderation_service as moderation
from apps.feeds.infrastructure.external.hatespeech_client import (
    HateSpeechClient,
    HateSpeechError,
    HateSpeechUnavailable,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 12
BACKOFF_BASE_SECONDS = 15
BACKOFF_MAX_SECONDS = 600
STALE_PENDING_AFTER = timedelta(minutes=30)
SWEEP_BATCH_SIZE = 100


def backoff_seconds(retries: int) -> int:
    return min(BACKOFF_MAX_SECONDS, BACKOFF_BASE_SECONDS * (2**retries))


@shared_task(bind=True, max_retries=MAX_RETRIES, acks_late=True)
def classify_content(self, content_type, content_id):
    obj = moderation.get_content(content_type, content_id)
    if obj is None or getattr(obj, "is_deleted", False):
        return "skipped"

    client = HateSpeechClient()
    if not client.enabled:
        return "disabled"

    try:
        data = client.classify(
            content_type=content_type,
            content_id=obj.pk,
            text=obj.content,
            author_id=obj.author_identity_id,
            explain=settings.HATESPEECH_EXPLAIN,
        )
    except HateSpeechUnavailable as exc:
        if self.request.retries >= self.max_retries:
            logger.error(
                "Moderación de %s %s agotó reintentos: %s",
                content_type,
                content_id,
                exc,
            )
            moderation.mark_failed(obj)
            return "failed"
        raise self.retry(
            exc=exc, countdown=backoff_seconds(self.request.retries)
        ) from exc
    except HateSpeechError as exc:
        logger.error(
            "hatespeech-service rechazó %s %s: %s", content_type, content_id, exc
        )
        moderation.mark_failed(obj)
        return "rejected"

    moderation.apply_classification(obj, data)
    return obj.visibility


@shared_task
def sweep_pending_moderation():
    """Re-encola lo que quedó sin clasificar (servicio caído, broker perdido o
    contenido anterior a la integración)."""
    client = HateSpeechClient()
    if not client.enabled or not client.is_healthy():
        return 0

    cutoff = timezone.now() - STALE_PENDING_AFTER
    queued = 0
    for content_type, model in moderation.CONTENT_MODELS.items():
        stale = model.objects.filter(
            moderation_status__in=[ModerationStatus.PENDING, ModerationStatus.FAILED],
            updated_at__lt=cutoff,
        )
        if model is Comment:
            stale = stale.filter(is_deleted=False)
        for pk in stale.values_list("pk", flat=True)[:SWEEP_BATCH_SIZE]:
            classify_content.delay(content_type, str(pk))
            queued += 1
    return queued
