import logging
import time
import uuid

from django.core.management.base import BaseCommand

from apps.custom_auth.identity_principal import IdentityPrincipal
from apps.feeds.domain.entities.feed_post import FeedPost
from apps.feeds.domain.services.feed_service import feed_service

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Valida metricas funcionales y de rendimiento (CRUD < 1.2s, Feed < 1.8s)"

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("Iniciando validacion funcional y de rendimiento...")
        )

        user = IdentityPrincipal(
            id=f"test_perf_{uuid.uuid4().hex[:8]}",
            username="test.performance@example.com",
            first_name="Test",
            last_name="Performance",
            extra={"investigation_camp": "Artificial Intelligence"},
        )
        self.stdout.write(f"Principal temporal creado: {user.username}")

        metrics = {"CRUD": [], "FEED": []}
        created_posts = []

        try:
            self.stdout.write("\n--- Ejecutando pruebas CRUD (25 casos) ---")
            for i in range(25):
                start_time = time.perf_counter()

                content = (
                    f"Benchmark post iteracion {i}: Analisis de rendimiento "
                    f"en sistemas distribuidos."
                )
                post = feed_service.create_post(
                    author=user, content=content, is_public=True
                )
                feed_service.toggle_like(user, post)
                feed_service.create_comment(
                    user.id, post.id, "Interesante punto de vista."
                )

                duration = time.perf_counter() - start_time
                metrics["CRUD"].append(duration)
                if post:
                    created_posts.append(post)

                self.stdout.write(f"  Iteracion {i + 1}: {duration:.4f}s")

            self.stdout.write(
                "\n--- Ejecutando pruebas feed personalizado (25 casos) ---"
            )
            for i in range(25):
                start_time = time.perf_counter()
                feed, _, _ = feed_service.get_personalized_feed(user=user, limit=10)
                duration = time.perf_counter() - start_time

                metrics["FEED"].append(duration)
                self.stdout.write(
                    f"  Iteracion {i + 1}: {duration:.4f}s (Items: {len(feed)})"
                )

            self.print_report(metrics)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error durante las pruebas: {str(e)}"))

        finally:
            self.stdout.write("\nLimpiando datos de prueba...")
            for post in created_posts:
                if FeedPost.objects.filter(id=post.id).exists():
                    post.delete()
            self.stdout.write("Limpieza completada.")

    def print_report(self, metrics):
        report_path = "apps/feeds/docs/functional_validation_results_2026_01_11.md"

        crud_avg = sum(metrics["CRUD"]) / len(metrics["CRUD"])
        crud_target = 1.2
        crud_passed = crud_avg < crud_target
        crud_status = "PASSED" if crud_passed else "FAILED"

        feed_avg = sum(metrics["FEED"]) / len(metrics["FEED"])
        feed_target = 1.8
        feed_passed = feed_avg < feed_target
        feed_status = "PASSED" if feed_passed else "FAILED"

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("# Validacion Funcional y de Rendimiento\n\n")
            f.write("**Fecha:** 11 de Enero de 2026\n")
            f.write(
                "**Objetivo**: Validar tiempos de respuesta de "
                "operaciones criticas.\n\n"
            )

            f.write("## 1. Operaciones CRUD (Create + Like + Comment)\n")
            f.write(f"- **Promedio**: {crud_avg:.4f}s\n")
            f.write(f"- **Meta**: < {crud_target}s\n")
            f.write(f"- **Estado**: {crud_status}\n\n")

            f.write("## 2. Generacion de Feed Personalizado\n")
            f.write(f"- **Promedio**: {feed_avg:.4f}s\n")
            f.write(f"- **Meta**: < {feed_target}s\n")
            f.write(f"- **Estado**: {feed_status}\n\n")

            if crud_passed and feed_passed:
                f.write(
                    "## Conclusion\n**EL SISTEMA CUMPLE LOS REQUISITOS "
                    "DE RENDIMIENTO.**\n"
                )
            else:
                f.write("## Conclusion\n**ALGUNOS REQUISITOS NO SE CUMPLIERON.**\n")

        self.stdout.write(self.style.SUCCESS(f"Reporte generado en: {report_path}"))
