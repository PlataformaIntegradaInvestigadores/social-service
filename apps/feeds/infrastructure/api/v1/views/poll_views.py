import logging

from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.feeds.domain.entities.poll import Poll, PollOption, PollVote
from apps.feeds.infrastructure.api.v1.serializers.poll_serializers import PollSerializer

logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def vote_poll(request, poll_id):
    """
    Vota en una encuesta
    """
    try:
        poll = get_object_or_404(Poll, id=poll_id)

        # Verificar si la encuesta está activa
        if not poll.is_active:
            return Response(
                {"error": "Esta encuesta ya no está activa"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verificar si la encuesta ha expirado
        if poll.expires_at and poll.expires_at < timezone.now():
            return Response(
                {"error": "Esta encuesta ha expirado"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        option_ids = request.data.get("option_ids", [])
        if not option_ids:
            return Response(
                {"error": "Debe seleccionar al menos una opción"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Si no es múltiple choice, solo permitir una opción
        if not poll.is_multiple_choice and len(option_ids) > 1:
            return Response(
                {"error": "Solo puede seleccionar una opción en esta encuesta"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verificar si el usuario ya votó
        existing_votes = PollVote.objects.filter(
            poll=poll, user_identity_id=str(request.user.id)
        )
        if existing_votes.exists() and not poll.is_multiple_choice:
            return Response(
                {"error": "Ya has votado en esta encuesta"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verificar que todas las opciones pertenecen a esta encuesta
        options = PollOption.objects.filter(id__in=option_ids, poll=poll)
        if len(options) != len(option_ids):
            return Response(
                {"error": "Una o más opciones no son válidas"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # Si es múltiple choice, eliminar votos anteriores del usuario
            if poll.is_multiple_choice:
                existing_votes.delete()

            # Crear nuevos votos
            votes_created = []
            for option in options:
                vote, created = PollVote.objects.get_or_create(
                    poll=poll,
                    option=option,
                    user_identity_id=str(request.user.id),
                    defaults={
                        "user_snapshot": {
                            "id": str(request.user.id),
                            "username": getattr(request.user, "username", ""),
                            "first_name": getattr(request.user, "first_name", ""),
                            "last_name": getattr(request.user, "last_name", ""),
                            "profile_picture": getattr(
                                request.user, "profile_picture", ""
                            ),
                        }
                    },
                )
                if created:
                    votes_created.append(vote)

            # Actualizar contadores de votos
            for option in poll.options.all():
                option.votes_count = PollVote.objects.filter(option=option).count()
                option.save(update_fields=["votes_count"])

        # Retornar la encuesta actualizada con información del usuario
        serializer = PollSerializer(poll, context={"request": request})

        return Response(
            {"message": "Voto registrado exitosamente", "poll": serializer.data},
            status=status.HTTP_200_OK,
        )

    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error al votar en encuesta {poll_id}: {str(e)}")
        return Response(
            {"error": "Error interno del servidor"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def remove_vote(request, poll_id):
    """
    Elimina el voto del usuario en una encuesta
    """
    try:
        poll = get_object_or_404(Poll, id=poll_id)

        # Verificar si la encuesta permite cambiar votos
        if not poll.is_active:
            return Response(
                {"error": "No se pueden modificar votos en esta encuesta"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Eliminar votos del usuario
        votes = PollVote.objects.filter(
            poll=poll, user_identity_id=str(request.user.id)
        )
        if not votes.exists():
            return Response(
                {"error": "No tienes votos en esta encuesta"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # Eliminar votos
            votes.delete()

            # Actualizar contadores
            for option in poll.options.all():
                option.votes_count = PollVote.objects.filter(option=option).count()
                option.save(update_fields=["votes_count"])

        # Retornar la encuesta actualizada
        serializer = PollSerializer(poll, context={"request": request})

        return Response(
            {"message": "Voto eliminado exitosamente", "poll": serializer.data},
            status=status.HTTP_200_OK,
        )

    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error al eliminar voto en encuesta {poll_id}: {str(e)}")
        return Response(
            {"error": "Error interno del servidor"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_poll_details(request, poll_id):
    """
    Obtiene los detalles de una encuesta incluyendo si el usuario ya votó
    """
    try:
        poll = get_object_or_404(Poll, id=poll_id)
        serializer = PollSerializer(poll, context={"request": request})

        return Response(serializer.data, status=status.HTTP_200_OK)

    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error al obtener encuesta {poll_id}: {str(e)}")
        return Response(
            {"error": "Error interno del servidor"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
