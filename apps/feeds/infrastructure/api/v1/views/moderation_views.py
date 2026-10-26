"""
Endpoints de moderación expuestos al front.

El front nunca llama a hatespeech-service: los reportes y la cola de revisión
pasan por aquí, que añade la API key interna, el usuario que actúa y refleja
el resultado en el post/comentario local.
"""

import logging
import uuid

from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.feeds.domain.services import moderation_service as moderation
from apps.feeds.infrastructure.api.v1.serializers.moderation_serializers import (
    DecisionSerializer,
    ReportSerializer,
    ReviewQueueQuerySerializer,
)
from apps.feeds.infrastructure.external.hatespeech_client import (
    HateSpeechClient,
    HateSpeechError,
    HateSpeechUnavailable,
)

logger = logging.getLogger(__name__)

UNAVAILABLE_DETAIL = "El servicio de moderación no está disponible. Intenta más tarde."


class IsModerator(permissions.BasePermission):
    message = "Solo moderadores pueden acceder a la cola de revisión."

    def has_permission(self, request, view):
        return moderation.is_moderator(request.user)


def _service_error(exc):
    if isinstance(exc, HateSpeechUnavailable):
        return Response(
            {"detail": UNAVAILABLE_DETAIL}, status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return Response({"detail": detail}, status=exc.status_code)


def _uuid_or_none(value):
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _local_context(content_type, content_id):
    obj = moderation.get_content(content_type, _uuid_or_none(content_id))
    if obj is None:
        return {"exists": False}
    snapshot = obj.author_snapshot or {}
    context = {
        "exists": True,
        "author": {
            "id": obj.author_identity_id,
            "username": snapshot.get("username", ""),
            "first_name": snapshot.get("first_name", ""),
            "last_name": snapshot.get("last_name", ""),
        },
        "post_id": str(obj.post_id if content_type == moderation.COMMENT else obj.pk),
        "created_at": obj.created_at.isoformat() if obj.created_at else None,
    }
    return context


class ReportContentView(APIView):
    """POST posts/<id>/report/ y comments/<id>/report/ con motivo opcional.

    Un usuario cuenta una sola vez por contenido; al llegar al umbral
    (5 reportes distintos) hatespeech-service lo oculta y lo manda a revisión."""

    permission_classes = [permissions.IsAuthenticated]
    content_type = moderation.POST

    def post(self, request, pk):
        model = moderation.CONTENT_MODELS[self.content_type]
        obj = get_object_or_404(model, pk=pk)
        if getattr(obj, "is_deleted", False):
            return Response(status=status.HTTP_404_NOT_FOUND)
        if str(request.user.id) == str(obj.author_identity_id):
            return Response(
                {"detail": "No puedes reportar tu propio contenido."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = ReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        client = HateSpeechClient()
        try:
            data = client.report(
                content_type=self.content_type,
                content_id=obj.pk,
                reporter_id=request.user.id,
                reason=(serializer.validated_data.get("reason") or "").strip() or None,
                text=obj.content,
                author_id=obj.author_identity_id,
            )
        except (HateSpeechUnavailable, HateSpeechError) as exc:
            return _service_error(exc)

        moderation.apply_case_state(obj, data)
        created = bool(data.get("created"))
        return Response(
            {
                "created": created,
                "report_count": data.get("report_count", obj.report_count),
                "threshold_reached": bool(data.get("threshold_reached")),
                "moderation": moderation.moderation_payload(obj, request.user),
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class ModerationMeView(APIView):
    """Indica al front si el usuario actual es moderador (para guard y menú)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({"is_moderator": moderation.is_moderator(request.user)})


class ReviewQueueView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsModerator]

    def get(self, request):
        query = ReviewQueueQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = {k: v for k, v in query.validated_data.items() if v not in (None, "")}
        try:
            page = HateSpeechClient().review_queue(
                moderator_id=request.user.id, params=params
            )
        except (HateSpeechUnavailable, HateSpeechError) as exc:
            return _service_error(exc)
        for item in page.get("items", []):
            item["context"] = _local_context(
                item.get("content_type"), item.get("content_id")
            )
        return Response(page)


class ReviewCaseView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsModerator]

    def get(self, request, case_id):
        try:
            case = HateSpeechClient().review_case(
                moderator_id=request.user.id, case_id=case_id
            )
        except (HateSpeechUnavailable, HateSpeechError) as exc:
            return _service_error(exc)
        case["context"] = _local_context(
            case.get("content_type"), case.get("content_id")
        )
        return Response(case)


class ReviewDecisionView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsModerator]

    def post(self, request, case_id):
        serializer = DecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = HateSpeechClient().decide(
                moderator_id=request.user.id,
                case_id=case_id,
                decision=serializer.validated_data["decision"],
                notes=serializer.validated_data.get("notes"),
            )
        except (HateSpeechUnavailable, HateSpeechError) as exc:
            return _service_error(exc)

        case = result.get("case", {})
        obj = moderation.get_content(
            case.get("content_type"), _uuid_or_none(case.get("content_id"))
        )
        if obj is not None:
            moderation.apply_case_state(obj, case)
        else:
            logger.warning("Decisión sobre contenido inexistente en social: %s", case)
        case["context"] = _local_context(
            case.get("content_type"), case.get("content_id")
        )
        return Response(result)
