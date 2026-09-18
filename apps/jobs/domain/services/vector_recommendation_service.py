"""
Utilidades para manejo de vectores y recomendaciones con pgvector
"""

import logging
from typing import Any

import requests
from django.conf import settings
from django.db.models import F, Q, QuerySet
from django.db.models.expressions import RawSQL

from apps.jobs.domain.entities.jobs import Jobs

logger = logging.getLogger(__name__)


class VectorRecommendationService:
    """
    Servicio para manejar recomendaciones basadas en vectores usando pgvector
    """

    def __init__(self, embedding_service_url: str = None):
        """
        Inicializa el servicio de recomendaciones

        Args:
            embedding_service_url: URL del microservicio de embeddings
        """
        self.embedding_service_url = (
            embedding_service_url or settings.EMBEDDING_SERVICE_URL
        )

    def get_embedding_from_microservice(
        self, job_data: dict[str, Any]
    ) -> list[float] | None:
        """
        Obtiene el embedding de un job desde el microservicio externo

        Args:
            job_data: Diccionario con los datos del job

        Returns:
            Lista de floats representando el vector embedding o None si hay error
        """
        try:
            # Combinar toda la información del job en un texto coherente
            job_text_parts = []

            if job_data.get("title"):
                job_text_parts.append(f"Puesto: {job_data['title']}")

            if job_data.get("description"):
                job_text_parts.append(f"Descripción: {job_data['description']}")

            if job_data.get("requirements"):
                job_text_parts.append(f"Requisitos: {job_data['requirements']}")

            if job_data.get("location"):
                job_text_parts.append(f"Ubicación: {job_data['location']}")

            if job_data.get("job_type"):
                job_text_parts.append(f"Tipo de trabajo: {job_data['job_type']}")

            if job_data.get("experience_level"):
                job_text_parts.append(
                    f"Nivel de experiencia: {job_data['experience_level']}"
                )

            # Unir todo el texto
            job_text = ". ".join(job_text_parts)

            # Preparar el payload según la API del microservicio
            payload = {
                "text": job_text,
                "translate_to_english": True,  # Para mejor precisión en embeddings
                "clean_text": True,
            }

            # Llamar al endpoint correcto
            response = requests.post(
                f"{self.embedding_service_url}/text-processing/vectorize/",
                json=payload,
                timeout=30,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                result = response.json()
                vector = result.get("vector")

                if vector:
                    logger.info(
                        f"Embedding generado exitosamente. "
                        f"Dimensiones: {result.get('dimension', len(vector))}"
                    )
                    return vector
                else:
                    logger.error("El microservicio no devolvió un vector válido")
                    return None
            else:
                logger.error(
                    f"Error al obtener embedding: {response.status_code} - "
                    f"{response.text}"
                )
                return None

        except requests.RequestException as e:
            logger.error(
                f"Error de conexión con el microservicio de embeddings: {str(e)}"
            )
            return None
        except Exception as e:
            logger.error(f"Error inesperado al obtener embedding: {str(e)}")
            return None

    def update_job_embedding(self, job: Jobs) -> bool:
        """
        Actualiza el embedding de un job específico

        Args:
            job: Instancia del modelo Jobs

        Returns:
            True si se actualizó correctamente, False en caso contrario
        """
        job_data = {
            "title": job.title,
            "description": job.description,
            "requirements": job.requirements or "",
            "location": job.location or "",
            "job_type": job.job_type,
            "experience_level": job.experience_level,
        }

        embedding = self.get_embedding_from_microservice(job_data)

        if embedding:
            job.embedding = embedding
            job.save(update_fields=["embedding"])
            logger.info(f"Embedding actualizado para job {job.id}: {job.title}")
            return True
        else:
            logger.warning(
                f"No se pudo actualizar el embedding para job {job.id}: {job.title}"
            )
            return False

    def get_similar_jobs(
        self,
        user_embedding: list[float],
        limit: int = 10,
        exclude_job_ids: list[int] = None,
        similarity_threshold: float = 0.5,  # Reducido el threshold para más resultados
    ) -> QuerySet:
        """
        Obtiene jobs similares basados en el embedding del usuario usando pgvector
        Si no hay suficientes con embeddings, usa fallback

        Args:
            user_embedding: Vector embedding del usuario
            limit: Número máximo de resultados
            exclude_job_ids: IDs de jobs a excluir
            similarity_threshold: Umbral mínimo de similitud

        Returns:
            QuerySet con los jobs recomendados ordenados por score
        """
        if not user_embedding:
            return self.get_fallback_jobs(limit=limit, exclude_job_ids=exclude_job_ids)

        # Convertir el embedding a string para la consulta SQL
        embedding_str = "[" + ",".join(map(str, user_embedding)) + "]"

        # Construir filtros básicos
        filters = Q(embedding__isnull=False)

        if exclude_job_ids:
            filters &= ~Q(id__in=exclude_job_ids)

        # Usar pgvector para calcular similitud coseno y crear score compuesto
        similarity_sql = f"(1 - (embedding <#> '{embedding_str}'))"
        hours_old_sql = "EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600"

        # Score compuesto: 60% similitud, 30% interactions, 10% penalización tiempo
        composite_score_sql = f"""
            (
                0.6 * {similarity_sql} +
                0.3 * COALESCE(interactions_score, 0) -
                0.1 * ({hours_old_sql})
            )
        """

        # Intentar obtener jobs con embeddings
        queryset = (
            Jobs.objects.filter(filters)
            .annotate(
                similarity=RawSQL(similarity_sql, []),
                hours_old=RawSQL(hours_old_sql, []),
                recommendation_score=RawSQL(composite_score_sql, []),
            )
            .filter(similarity__gte=similarity_threshold)
            .order_by("-recommendation_score")[:limit]
        )

        # Si no hay suficientes resultados, usar fallback
        if len(queryset) < limit:
            remaining_limit = limit - len(queryset)
            used_ids = [job.id for job in queryset]
            if exclude_job_ids:
                used_ids.extend(exclude_job_ids)

            fallback_jobs = self.get_fallback_jobs(
                limit=remaining_limit, exclude_job_ids=used_ids
            )

            # Combinar resultados
            combined_ids = [job.id for job in queryset] + [
                job.id for job in fallback_jobs
            ]

            return (
                Jobs.objects.filter(id__in=combined_ids)
                .annotate(
                    similarity=RawSQL(
                        f"CASE WHEN embedding IS NOT NULL THEN {similarity_sql} ELSE 0.5 END",
                        [],
                    ),
                    hours_old=RawSQL(hours_old_sql, []),
                    recommendation_score=RawSQL(
                        f"CASE WHEN embedding IS NOT NULL THEN {composite_score_sql} ELSE COALESCE(interactions_score, 0) * 0.5 END",
                        [],
                    ),
                )
                .order_by("-recommendation_score", "-created_at")[:limit]
            )

        return queryset

    def get_trending_jobs(self, limit: int = 10) -> QuerySet:
        """
        Obtiene jobs en tendencia basados en interacciones recientes
        Si no hay suficientes jobs con interacciones, incluye los más recientes

        Args:
            limit: Número máximo de resultados

        Returns:
            QuerySet con jobs en tendencia (siempre devuelve al menos algunos jobs)
        """
        hours_old_sql = "EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600"

        # Score basado en interacciones recientes
        trending_score_sql = f"""
            (
                COALESCE(interactions_score, 0) / (1 + ({hours_old_sql} / 24))
            )
        """

        # Obtener todos los jobs disponibles
        all_jobs = (
            Jobs.objects.all()
            .annotate(
                hours_old=RawSQL(hours_old_sql, []),
                trending_score=RawSQL(trending_score_sql, []),
            )
            .order_by("-trending_score", "-created_at")[:limit]
        )

        return all_jobs

    def update_job_interactions(self, job_id: int, interaction_type: str = "view"):
        """
        Actualiza las métricas de interacción de un job

        Args:
            job_id: ID del job
            interaction_type: Tipo de interacción ('view', 'application')
        """
        try:
            job = Jobs.objects.get(id=job_id)

            if interaction_type == "view":
                job.view_count = F("view_count") + 1
                # Aumentar score de interacciones basado en views
                job.interactions_score = F("interactions_score") + 0.1
            elif interaction_type == "application":
                job.application_count = F("application_count") + 1
                # Las aplicaciones tienen más peso que las views
                job.interactions_score = F("interactions_score") + 1.0

            job.save(
                update_fields=["view_count", "application_count", "interactions_score"]
            )

        except Jobs.DoesNotExist:
            logger.error(f"Job con ID {job_id} no encontrado")
        except Exception as e:
            logger.error(
                f"Error al actualizar interacciones del job {job_id}: {str(e)}"
            )

    def get_fallback_jobs(
        self, limit: int = 10, exclude_job_ids: list[int] = None
    ) -> QuerySet:
        """
        Obtiene jobs de fallback cuando no hay embeddings o recomendaciones suficientes.
        Devuelve jobs trending y, si faltan, los más recientes.
        """
        hours_old_sql = "EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600"
        fallback_score_sql = f"""
            (
                COALESCE(interactions_score, 0) * 0.7 + 
                (1.0 / (1 + ({hours_old_sql} / 24))) * 0.3
            )
        """
        filters = Q()
        if exclude_job_ids:
            filters &= ~Q(id__in=exclude_job_ids)
        return (
            Jobs.objects.filter(filters)
            .annotate(
                hours_old=RawSQL(hours_old_sql, []),
                recommendation_score=RawSQL(fallback_score_sql, []),
                similarity=RawSQL("0.5", []),
            )
            .order_by("-recommendation_score", "-created_at")[:limit]
        )


# Instancia global del servicio
vector_service = VectorRecommendationService()
