"""Keeps the pgvector embedding of every job offer up to date."""

import logging

from apps.jobs.domain.entities.jobs import Jobs
from apps.shared.embedding_client import EmbeddingClient

logger = logging.getLogger(__name__)


def job_embedding_text(job: Jobs) -> str:
    """The text a job offer is embedded from: only the fields that describe it."""
    parts = []

    if job.title:
        parts.append(f"Puesto: {job.title}")

    if job.description:
        parts.append(f"Descripción: {job.description}")

    if job.requirements:
        parts.append(f"Requisitos: {job.requirements}")

    if job.location:
        parts.append(f"Ubicación: {job.location}")

    if job.job_type:
        parts.append(f"Tipo de trabajo: {job.job_type}")

    if job.experience_level:
        parts.append(f"Nivel de experiencia: {job.experience_level}")

    return ". ".join(parts)


class JobEmbeddingService:
    def __init__(self, embedding_service_url: str = None, embeddings=None):
        self.embeddings = embeddings or EmbeddingClient(embedding_service_url)

    def update_job_embedding(self, job: Jobs) -> bool:
        """Embed `job` and store the vector; True when it was stored."""
        embedding = self.embeddings.embed(job_embedding_text(job))

        if embedding:
            job.embedding = embedding
            job.save(update_fields=["embedding"])
            logger.info(f"Embedding actualizado para job {job.id}: {job.title}")
            return True

        logger.warning(
            f"No se pudo actualizar el embedding para job {job.id}: {job.title}"
        )
        return False


job_embedding_service = JobEmbeddingService()
