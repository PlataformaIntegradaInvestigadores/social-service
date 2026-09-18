"""
Management command para actualizar embeddings de posts existentes
"""

import logging

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.feeds.domain.entities.feed_post import FeedPost
from apps.feeds.domain.services.feed_service import FeedService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Actualiza los embeddings de posts existentes que no los tienen "
        "o fuerza la actualización"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Fuerza la actualización de embeddings incluso si ya existen",
        )
        parser.add_argument(
            "--post-id",
            type=str,
            help="Actualiza solo el post con el ID especificado",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Número de posts a procesar por lote (default: 50)",
        )

    def handle(self, *args, **options):
        force = options["force"]
        post_id = options["post_id"]
        batch_size = options["batch_size"]

        filters = Q()
        if post_id:
            filters &= Q(id=post_id)
        elif not force:
            filters &= Q(embedding__isnull=True)

        posts_to_process = FeedPost.objects.filter(filters)
        total_posts = posts_to_process.count()

        if total_posts == 0:
            self.stdout.write(
                self.style.WARNING(
                    "No hay posts para procesar con los criterios especificados."
                )
            )
            return

        self.stdout.write(self.style.SUCCESS(f"Procesando {total_posts} posts..."))

        processed = 0
        updated = 0
        errors = 0
        feed_service = FeedService()

        for i in range(0, total_posts, batch_size):
            batch = posts_to_process[i : i + batch_size]
            self.stdout.write(
                f"Procesando lote {i//batch_size + 1}/"
                f"{(total_posts-1)//batch_size + 1}..."
            )
            for post in batch:
                try:
                    success = feed_service.update_post_embedding(str(post.id))
                    if success:
                        updated += 1
                        self.stdout.write(f"  ✓ Post {post.id}: {post.content[:40]}")
                    else:
                        errors += 1
                        self.stdout.write(
                            self.style.ERROR(
                                f"  ✗ Error en post {post.id}: {post.content[:40]}"
                            )
                        )
                    processed += 1
                except Exception as e:
                    errors += 1
                    self.stdout.write(
                        self.style.ERROR(f"  ✗ Excepción en post {post.id}: {str(e)}")
                    )
                    logger.error(f"Error procesando post {post.id}: {str(e)}")

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
            self.stdout.write(self.style.ERROR(f"✗ {errors} posts tuvieron errores"))
