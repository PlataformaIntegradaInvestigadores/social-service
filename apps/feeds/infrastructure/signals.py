"""
Encola la clasificación de discurso de odio al crear o editar contenido.

Se guarda el texto original en ``post_init`` para reclasificar solo cuando el
contenido cambia (un like también hace ``save()`` del post y no debe
reclasificarlo). El encolado ocurre tras el commit para que el worker lea la
fila ya persistida, y un fallo del broker nunca impide publicar: el barrido
periódico recoge lo que quede pendiente.
"""

import logging

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_init, post_save
from django.dispatch import receiver

from apps.feeds.domain.entities.comment import Comment
from apps.feeds.domain.entities.feed_post import FeedPost
from apps.feeds.domain.services import moderation_service as moderation

logger = logging.getLogger(__name__)


def _enqueue(content_type, content_id):
    from apps.feeds.tasks import classify_content

    try:
        classify_content.delay(content_type, str(content_id))
    except Exception as exc:  # broker caído: lo recoge sweep_pending_moderation
        logger.warning(
            "No se pudo encolar moderación de %s %s: %s", content_type, content_id, exc
        )


@receiver(post_init, sender=FeedPost)
@receiver(post_init, sender=Comment)
def remember_moderated_text(sender, instance, **kwargs):
    instance._moderation_original_content = instance.content


@receiver(post_save, sender=FeedPost)
@receiver(post_save, sender=Comment)
def enqueue_moderation(sender, instance, created, raw=False, **kwargs):
    if raw or not settings.HATESPEECH_SERVICE_URL:
        return
    if getattr(instance, "is_deleted", False):
        return
    changed = instance.content != getattr(
        instance, "_moderation_original_content", None
    )
    instance._moderation_original_content = instance.content
    if not created and not changed:
        return
    if not created:
        moderation.mark_pending(instance)
    content_type = moderation.content_type_of(instance)
    pk = instance.pk
    transaction.on_commit(lambda: _enqueue(content_type, pk))
