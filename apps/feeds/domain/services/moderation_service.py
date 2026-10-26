"""
Reglas de moderación del lado de social-service.

hatespeech-service es la fuente de verdad de cada caso (clasificación,
reportes, decisiones humanas); aquí solo se refleja su estado en los posts y
comentarios para poder ordenar, ocultar y serializar sin llamarle en cada
lectura.
"""

from django.conf import settings
from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone

from apps.feeds.domain.entities.comment import Comment
from apps.feeds.domain.entities.feed_post import FeedPost
from apps.feeds.domain.entities.moderation import (
    ModerationStatus,
    ReviewStatus,
    Visibility,
)

POST = "post"
COMMENT = "comment"
CONTENT_MODELS = {POST: FeedPost, COMMENT: Comment}

BLOCKED_PLACEHOLDER = "Contenido bloqueado por moderación."

_VISIBILITIES = set(Visibility.values)
_REVIEW_STATUSES = set(ReviewStatus.values)


def content_type_of(obj) -> str:
    return COMMENT if isinstance(obj, Comment) else POST


def get_content(content_type, content_id):
    model = CONTENT_MODELS.get(content_type)
    if model is None:
        return None
    return model.objects.filter(pk=content_id).first()


def is_moderator(user) -> bool:
    """Moderador = is_staff. identity-service todavía no emite is_staff en el
    JWT, así que también se acepta el claim crudo y la lista
    MODERATOR_USER_IDS del entorno."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_staff", False):
        return True
    extra = getattr(user, "extra", None) or {}
    if extra.get("is_staff") is True:
        return True
    return str(getattr(user, "id", "")) in settings.MODERATOR_USER_IDS


def _common_fields(data) -> dict:
    fields = {"moderated_at": timezone.now()}
    if data.get("visibility") in _VISIBILITIES:
        fields["visibility"] = data["visibility"]
    if data.get("review_status") in _REVIEW_STATUSES:
        fields["review_status"] = data["review_status"]
    if "reasons" in data:
        fields["moderation_reasons"] = list(data.get("reasons") or [])
    if data.get("report_count") is not None:
        fields["report_count"] = int(data["report_count"])
    case_id = data.get("case_id", data.get("id"))
    if case_id is not None:
        fields["moderation_case_id"] = int(case_id)
    return fields


def _update(obj, fields) -> None:
    # update() evita disparar post_save (que volvería a encolar la
    # clasificación) y no toca updated_at del contenido.
    type(obj).objects.filter(pk=obj.pk).update(**fields)
    for name, value in fields.items():
        setattr(obj, name, value)


def apply_classification(obj, data) -> None:
    fields = _common_fields(data)
    fields["moderation_status"] = ModerationStatus.CLASSIFIED
    if data.get("p_hate") is not None:
        fields["p_hate"] = float(data["p_hate"])
    fields["hate_label"] = data.get("label") or ""
    _update(obj, fields)


def apply_case_state(obj, data) -> None:
    """Refleja un reporte o una decisión humana (solo cambian visibilidad,
    revisión, motivos y reportes)."""
    fields = _common_fields(data)
    if data.get("p_hate") is not None:
        fields["p_hate"] = float(data["p_hate"])
    _update(obj, fields)


def mark_pending(obj) -> None:
    _update(obj, {"moderation_status": ModerationStatus.PENDING})


def mark_failed(obj) -> None:
    _update(obj, {"moderation_status": ModerationStatus.FAILED})


def hidden_last(queryset, *ordering):
    """Ordena con el contenido oculto/bloqueado al final del hilo."""
    return queryset.annotate(
        _moderation_rank=Case(
            When(visibility=Visibility.VISIBLE, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        )
    ).order_by("_moderation_rank", *ordering)


def moderation_payload(obj, viewer=None) -> dict:
    moderator = is_moderator(viewer)
    viewer_id = str(getattr(viewer, "id", "")) if viewer else ""
    authenticated = bool(viewer and getattr(viewer, "is_authenticated", False))
    return {
        "status": obj.moderation_status,
        "visibility": obj.visibility,
        "show_warning": obj.show_warning,
        "is_blocked": obj.is_blocked,
        "sort_last": obj.sort_last,
        "review_status": obj.review_status,
        "reasons": list(obj.moderation_reasons or []),
        "report_count": obj.report_count,
        "can_report": authenticated and viewer_id != str(obj.author_identity_id),
        # p(odio) solo para moderadores: al resto le basta la advertencia.
        "p_hate": obj.p_hate if moderator else None,
        "label": (obj.hate_label or None) if moderator else None,
        "case_id": obj.moderation_case_id if moderator else None,
    }


def redact_if_blocked(obj, data, viewer=None) -> dict:
    if obj.is_blocked and not is_moderator(viewer):
        data["content"] = BLOCKED_PLACEHOLDER
    return data
