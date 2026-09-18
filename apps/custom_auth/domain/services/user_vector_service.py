"""
Adaptador retirado de vectores de usuario.

Los embeddings de investigador dejaron de pertenecer a la base social cuando
identidad se movio a `profile_identity_backend`. Este objeto conserva la
interfaz usada por feed/jobs para no romper flujos existentes, pero no consulta
ni escribe la tabla legacy `users`.
"""

import logging

logger = logging.getLogger(__name__)


class RetiredUserVectorService:
    def update_user_job_embedding(self, user_id: str) -> bool:
        logger.info(
            "Embedding de jobs para usuario %s omitido: identidad vive en "
            "profile_identity_backend",
            user_id,
        )
        return False

    def update_user_feed_embedding(self, user_id: str) -> bool:
        logger.info(
            "Embedding de feed para usuario %s omitido: identidad vive en "
            "profile_identity_backend",
            user_id,
        )
        return False

    def update_user_vectors_on_interaction(
        self, user_id: str, interaction_type: str, content: str = None
    ):
        logger.debug(
            "Actualizacion de vector omitida para usuario %s tras %s: "
            "servicio legacy retirado",
            user_id,
            interaction_type,
        )

    def get_users_for_job_recommendations(
        self, job_embedding: list[float], limit: int = 10
    ) -> list:
        logger.info(
            "Consulta de usuarios recomendados omitida: no existe tabla "
            "social de identidad"
        )
        return []


user_vector_service = RetiredUserVectorService()
