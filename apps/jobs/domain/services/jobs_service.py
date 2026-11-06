"""
Servicio principal para manejo de trabajos con embeddings y recomendaciones
"""

import logging
from datetime import timedelta
from typing import Any

from django.db.models import F, Q, QuerySet
from django.db.models.expressions import RawSQL
from django.utils import timezone

# Importar modelos de jobs
from apps.jobs.domain.entities.jobs import Jobs
from apps.shared.embedding_client import EmbeddingClient

logger = logging.getLogger(__name__)


class JobsService:
    """
    Servicio principal para manejo de trabajos con recomendaciones y búsqueda semántica
    """

    def __init__(self, embedding_service_url: str = None, embeddings=None):
        self.embeddings = embeddings or EmbeddingClient(embedding_service_url)

    def get_personalized_job_recommendations(
        self, user=None, user_id: str = None, limit: int = 20
    ) -> QuerySet:
        """
        Obtiene recomendaciones personalizadas de trabajos basadas en
        el perfil del usuario
        """
        try:
            if user:
                user_id = str(user.id)
            logger.info(
                f"Obteniendo recomendaciones de trabajos para usuario {user_id}"
            )
            logger.info(
                "Usando recomendaciones basicas sin consultar custom_auth.User local"
            )
            return self._get_basic_recommendations(None, limit)
        except Exception as e:
            logger.error(f"Error obteniendo recomendaciones: {str(e)}")
            return self._get_basic_recommendations(None, limit)

    def _get_basic_recommendations(self, user, limit: int) -> QuerySet:
        """
        Obtiene recomendaciones básicas cuando no hay embeddings disponibles
        """
        base_queryset = Jobs.objects.all()

        # Combinar trabajos populares y recientes
        popular_weight = 0.6

        popular_limit = int(limit * popular_weight)
        recent_limit = limit - popular_limit

        # Trabajos populares
        popular_jobs = base_queryset.order_by(
            "-view_count", "-application_count", "-created_at"
        )[:popular_limit]

        # Trabajos recientes
        recent_jobs = base_queryset.order_by("-created_at")[:recent_limit]

        # Combinar y eliminar duplicados manteniendo el orden
        job_ids = []
        for job in popular_jobs:
            if job.id not in job_ids:
                job_ids.append(job.id)

        for job in recent_jobs:
            if job.id not in job_ids and len(job_ids) < limit:
                job_ids.append(job.id)

        # Retornar queryset ordenado
        return Jobs.objects.filter(id__in=job_ids).order_by(
            "-view_count", "-created_at"
        )

    def get_trending_jobs(self, limit: int = 20) -> QuerySet:
        """
        Obtiene trabajos trending basados en interacciones recientes
        """
        try:
            # Trabajos de los últimos 30 días
            recent_date = timezone.now() - timedelta(days=30)

            # Score de trending basado en interacciones recientes
            trending_score_sql = """
                (
                    (view_count * 1.0) +
                    (application_count * 3.0) +
                    (EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400.0) * -0.1
                )
            """

            # DEBUG: Verificar cuántos jobs hay en total
            total_jobs = Jobs.objects.count()
            logger.info(f"DEBUG: Total jobs en DB: {total_jobs}")

            queryset = (
                Jobs.objects.filter(created_at__gte=recent_date)
                .annotate(trending_score=RawSQL(trending_score_sql, []))
                .order_by("-trending_score")[:limit]
            )

            logger.info(f"DEBUG: Jobs trending query count: {queryset.count()}")

            # Si no hay jobs recientes, mostrar todos los disponibles
            if not queryset.exists():
                logger.info("DEBUG: No hay jobs recientes, obteniendo todos")
                queryset = (
                    Jobs.objects.all()
                    .annotate(trending_score=RawSQL(trending_score_sql, []))
                    .order_by("-trending_score")[:limit]
                )
                logger.info(f"DEBUG: Jobs todos query count: {queryset.count()}")

            logger.info(f"Trabajos trending generados: {queryset.count()}")
            return queryset

        except Exception as e:
            logger.error(f"Error obteniendo trabajos trending: {str(e)}")
            return Jobs.objects.all().order_by("-view_count", "-created_at")[:limit]

    def semantic_search_jobs(
        self, query: str, filters: dict[str, Any] = None, limit: int = 20, user=None
    ) -> QuerySet:
        """
        Búsqueda semántica de trabajos usando embeddings
        """
        try:
            # Obtener embedding de la consulta
            query_embedding = self.embeddings.embed(query)

            if not query_embedding:
                # Fallback a búsqueda textual
                logger.warning("No se pudo obtener embedding, usando búsqueda textual")
                return self._text_search_jobs(query, filters, limit)

            # Búsqueda por similitud de vectores
            embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
            similarity_sql = f"(1 - (embedding <#> '{embedding_str}'))"

            queryset = Jobs.objects.filter(embedding__isnull=False)

            # Aplicar filtros
            if filters:
                queryset = self._apply_filters(queryset, filters)

            # Ordenar por similitud
            queryset = queryset.annotate(
                similarity=RawSQL(similarity_sql, [])
            ).order_by("-similarity")[:limit]

            logger.info(f"Búsqueda semántica completada: {queryset.count()} resultados")

            return queryset

        except Exception as e:
            logger.error(f"Error en búsqueda semántica: {str(e)}")
            return self._text_search_jobs(query, filters, limit)

    def _text_search_jobs(
        self, query: str, filters: dict[str, Any] = None, limit: int = 20
    ) -> QuerySet:
        """
        Búsqueda textual fallback cuando no hay embeddings disponibles
        """
        queryset = Jobs.objects.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(requirements__icontains=query)
            | Q(company__company_name__icontains=query)
        )

        # Aplicar filtros
        if filters:
            queryset = self._apply_filters(queryset, filters)

        return queryset.order_by("-created_at")[:limit]

    def _apply_filters(self, queryset: QuerySet, filters: dict[str, Any]) -> QuerySet:
        """
        Aplica filtros al queryset de trabajos
        """
        if filters.get("is_remote") is not None:
            queryset = queryset.filter(is_remote=filters["is_remote"])

        if filters.get("job_type"):
            if isinstance(filters["job_type"], list):
                queryset = queryset.filter(job_type__in=filters["job_type"])
            else:
                queryset = queryset.filter(job_type=filters["job_type"])

        if filters.get("experience_level"):
            if isinstance(filters["experience_level"], list):
                queryset = queryset.filter(
                    experience_level__in=filters["experience_level"]
                )
            else:
                queryset = queryset.filter(experience_level=filters["experience_level"])

        if filters.get("salary_min"):
            queryset = queryset.filter(salary_min__gte=filters["salary_min"])

        if filters.get("salary_max"):
            queryset = queryset.filter(salary_max__lte=filters["salary_max"])

        if filters.get("location"):
            queryset = queryset.filter(location__icontains=filters["location"])

        if filters.get("company"):
            queryset = queryset.filter(
                company__company_name__icontains=filters["company"]
            )

        return queryset

    def handle_job_interaction(self, user, job: Jobs, interaction_type: str = "view"):
        """
        Maneja las interacciones del usuario con trabajos
        """
        try:
            # Incrementar contadores
            if interaction_type == "view":
                Jobs.objects.filter(id=job.id).update(view_count=F("view_count") + 1)
            elif interaction_type == "application":
                Jobs.objects.filter(id=job.id).update(
                    application_count=F("application_count") + 1
                )

            logger.info(
                f"Interacción registrada: {interaction_type} en job "
                f"{job.id} por usuario {user.id}"
            )

        except Exception as e:
            logger.error(f"Error registrando interacción: {str(e)}")
