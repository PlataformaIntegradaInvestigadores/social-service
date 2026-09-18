import logging

from celery import shared_task
from django.core.management import call_command

logger = logging.getLogger(__name__)


@shared_task
def update_missing_job_embeddings():
    """
    Tarea periódica para actualizar los embeddings de los jobs que no los tienen.
    Esto es útil si el servicio de embeddings estaba caído cuando se creó el job.
    """
    logger.info("Iniciando tarea periódica: update_missing_job_embeddings")
    try:
        # Llama al comando de management existente
        call_command("update_job_embeddings", batch_size=50)
        logger.info("Tarea update_missing_job_embeddings completada exitosamente")
    except Exception as e:
        logger.error(f"Error en tarea update_missing_job_embeddings: {str(e)}")
