"""
Management command para actualizar embeddings de jobs existentes
"""

import logging

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.jobs.domain.entities.jobs import Jobs
from apps.jobs.domain.services.vector_recommendation_service import vector_service

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Actualiza los embeddings de jobs existentes que no los tienen "
        "o fuerza la actualización"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Fuerza la actualización de embeddings incluso si ya existen",
        )
        parser.add_argument(
            "--job-id",
            type=int,
            help="Actualiza solo el job con el ID especificado",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Número de jobs a procesar por lote (default: 50)",
        )

    def handle(self, *args, **options):
        force = options["force"]
        job_id = options["job_id"]
        batch_size = options["batch_size"]

        # Filtros base
        filters = Q()

        if job_id:
            filters &= Q(id=job_id)
        elif not force:
            # Solo jobs sin embedding si no se fuerza la actualización
            filters &= Q(embedding__isnull=True)

        # Obtener jobs a procesar
        jobs_to_process = Jobs.objects.filter(filters)
        total_jobs = jobs_to_process.count()

        if total_jobs == 0:
            self.stdout.write(
                self.style.WARNING(
                    "No hay jobs para procesar con los criterios especificados."
                )
            )
            return

        self.stdout.write(self.style.SUCCESS(f"Procesando {total_jobs} jobs..."))

        # Procesar en lotes
        processed = 0
        updated = 0
        errors = 0

        for i in range(0, total_jobs, batch_size):
            batch = jobs_to_process[i : i + batch_size]

            self.stdout.write(
                f"Procesando lote {i//batch_size + 1}/"
                f"{(total_jobs-1)//batch_size + 1}..."
            )

            for job in batch:
                try:
                    success = vector_service.update_job_embedding(job)
                    if success:
                        updated += 1
                        self.stdout.write(f"  ✓ Job {job.id}: {job.title}")
                    else:
                        errors += 1
                        self.stdout.write(
                            self.style.ERROR(f"  ✗ Error en job {job.id}: {job.title}")
                        )
                    processed += 1

                except Exception as e:
                    errors += 1
                    self.stdout.write(
                        self.style.ERROR(f"  ✗ Excepción en job {job.id}: {str(e)}")
                    )
                    logger.error(f"Error procesando job {job.id}: {str(e)}")

        # Resumen final
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS("Procesamiento completado:"))
        self.stdout.write(f"  • Total procesados: {processed}")
        self.stdout.write(f"  • Exitosamente actualizados: {updated}")
        self.stdout.write(f"  • Errores: {errors}")

        if updated > 0:
            self.stdout.write(
                self.style.SUCCESS(f"✓ {updated} embeddings actualizados correctamente")
            )

        if errors > 0:
            self.stdout.write(self.style.ERROR(f"✗ {errors} jobs tuvieron errores"))
