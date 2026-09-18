import logging
import statistics
import time

from django.core.management.base import BaseCommand

from apps.feeds.domain.services.feed_service import feed_service

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Ejecuta pruebas de rendimiento contra el microservicio de embeddings"

    def add_arguments(self, parser):
        parser.add_argument(
            "--iterations",
            type=int,
            default=10,
            help="Número de iteraciones por prueba",
        )

    def handle(self, *args, **options):
        iterations = options["iterations"]
        self.stdout.write(
            self.style.SUCCESS(f"Iniciando benchmark con {iterations} iteraciones...")
        )

        # Definir datasets de prueba
        short_text = (
            "La democracia deliberativa busca el consenso a través del "
            "diálogo racional entre ciudadanos."
        )
        # Texto largo generado (~5000 chars)
        long_text = (
            "El cambio climático representa uno de los desafíos más "
            "significativos de nuestra era. " * 80
        )

        self.stdout.write(f"\nLongitud Texto Corto: {len(short_text)} caracteres")
        self.stdout.write(f"Longitud Texto Largo: {len(long_text)} caracteres")

        # 1. Prueba de Textos Cortos
        self.stdout.write(
            self.style.WARNING(
                "\n--- Iniciando Prueba de Textos Cortos (<1000 chars) ---"
            )
        )
        short_stats = self.run_benchmark(short_text, iterations)
        self.print_stats("Textos Cortos", short_stats)

        # 2. Prueba de Textos Largos
        self.stdout.write(
            self.style.WARNING(
                "\n--- Iniciando Prueba de Textos Largos (~5000 chars) ---"
            )
        )
        long_stats = self.run_benchmark(long_text, iterations)
        self.print_stats("Textos Largos", long_stats)

    def run_benchmark(self, text, iterations):
        times = []
        success_count = 0

        for i in range(iterations):
            self.stdout.write(f"  Iteración {i+1}/{iterations}...", ending="")

            start_time = time.time()
            # Llamamos directamente al servicio que encapsula la petición
            vector = feed_service.get_embedding_from_microservice(text)
            end_time = time.time()

            duration_ms = (end_time - start_time) * 1000

            if vector and len(vector) > 0:
                status = "OK"
                success_count += 1
                times.append(duration_ms)
                self.stdout.write(
                    self.style.SUCCESS(f" {status} ({duration_ms:.2f}ms)")
                )
            else:
                status = "FAIL"
                self.stdout.write(self.style.ERROR(f" {status}"))

            # Pequeña pausa para no saturar si es necesario,
            # aunque queremos probar carga
            time.sleep(0.5)

        return {
            "times": times,
            "success_count": success_count,
            "iterations": iterations,
        }

    def print_stats(self, test_name, stats):
        success_rate = (stats["success_count"] / stats["iterations"]) * 100

        if stats["times"]:
            avg_time = statistics.mean(stats["times"])
            min_time = min(stats["times"])
            max_time = max(stats["times"])
        else:
            avg_time = 0
            min_time = 0
            max_time = 0

        self.stdout.write(self.style.MIGRATE_HEADING(f"\nResultados para {test_name}:"))
        self.stdout.write(f"  Tasa de Éxito: {success_rate:.1f}%")
        self.stdout.write(f"  Tiempo Promedio: {avg_time:.2f}ms")
        self.stdout.write(f"  Tiempo Mínimo: {min_time:.2f}ms")
        self.stdout.write(f"  Tiempo Máximo: {max_time:.2f}ms")
