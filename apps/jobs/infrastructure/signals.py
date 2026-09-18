"""
Signals para el módulo de Jobs - Manejo automático de embeddings
"""

import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.jobs.domain.entities.jobs import Jobs
from apps.jobs.domain.services.vector_recommendation_service import vector_service

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Jobs)
def handle_job_save(sender, instance, created, **kwargs):
    """
    Signal que se ejecuta después de guardar un Job.
    Genera automáticamente el embedding para el job.
    """
    try:
        # Solo generar embedding si es un job nuevo o si no tiene embedding
        if created or not instance.embedding:
            logger.info(
                f"Generando embedding para job "
                f"{'nuevo' if created else 'sin embedding'}: "
                f"{instance.id} - {instance.title}"
            )
            success = vector_service.update_job_embedding(instance)

            if success:
                logger.info(f"Embedding generado exitosamente para job {instance.id}")
            else:
                logger.error(f"Error al generar embedding para job {instance.id}")

        # Si el job fue actualizado y ya tenía embedding, verificar si
        # necesita actualización
        elif not created and instance.embedding:
            # Podrías agregar lógica aquí para detectar si el contenido
            # cambió significativamente
            # Por ejemplo, verificar si title, description, requirements cambiaron
            logger.info(f"Job {instance.id} actualizado - embedding ya existe")

    except Exception as e:
        logger.error(f"Error en signal de job {instance.id}: {str(e)}")


@receiver(post_delete, sender=Jobs)
def handle_job_delete(sender, instance, **kwargs):
    """
    Signal que se ejecuta después de eliminar un Job.
    Aquí podrías agregar lógica para limpiar datos relacionados si es necesario.
    """
    logger.info(f"Job eliminado: {instance.id} - {instance.title}")
