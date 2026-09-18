import logging
import math

from django.core.management.base import BaseCommand

from apps.feeds.domain.services.feed_service import feed_service

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Valida la calidad semántica de los embeddings comparando pares de textos"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Iniciando Validación Semántica..."))

        # Pares de prueba definidos según el requerimiento
        test_cases = [
            # 1. Textos Equivalentes (deberían ser > 0.90)
            {
                "type": "EQUIVALENTE (Multilingüe)",
                "text1": (
                    "La inteligencia artificial transformará la medicina "
                    "diagnóstica en la próxima década."
                ),
                "text2": (
                    "Artificial intelligence will transform diagnostic "
                    "medicine in the next decade."
                ),
                "threshold": 0.90,
            },
            {
                "type": "EQUIVALENTE (Parafraseo)",
                "text1": (
                    "El cambio climático es causado principalmente por "
                    "emisiones de gases de efecto invernadero."
                ),
                "text2": (
                    "Las emisiones de gases de efecto invernadero son la "
                    "causa principal del calentamiento global."
                ),
                "threshold": 0.90,
            },
            # 2. Textos Relacionados Conceptualmente (deberían ser > 0.75)
            {
                "type": "RELACIONADO",
                "text1": (
                    "Algoritmos genéticos para optimización de funciones complejas."
                ),
                "text2": (
                    "Computación evolutiva aplicada a problemas de búsqueda heurística."
                ),
                "threshold": 0.75,
            },
            {
                "type": "RELACIONADO",
                "text1": "Impacto de la política fiscal en la inflación.",
                "text2": "Efectos macroeconómicos del gasto público y los impuestos.",
                "threshold": 0.75,
            },
            # 3. Textos NO Relacionados (Control, deberían ser bajos)
            {
                "type": "NO RELACIONADO",
                "text1": "Técnicas avanzadas de cultivo de tejidos vegetales.",
                "text2": "Análisis de la arquitectura gótica en el siglo XII.",
                "threshold": 0.0,  # Solo informativo
            },
        ]

        results = []

        for case in test_cases:
            self.stdout.write(f"\nProcesando par: {case['type']}...")

            # Obtener embeddings
            vec1 = feed_service.get_embedding_from_microservice(case["text1"])
            vec2 = feed_service.get_embedding_from_microservice(case["text2"])

            if vec1 and vec2:
                similarity = self.cosine_similarity(vec1, vec2)

                passed = similarity >= case["threshold"]
                status_color = self.style.SUCCESS if passed else self.style.ERROR
                status_text = "PASSED" if passed else "FAILED"

                self.stdout.write(
                    f"  Similitud: {similarity:.4f} (Meta: >{case['threshold']}) -> "
                    + status_color(status_text)
                )

                results.append(
                    {
                        "type": case["type"],
                        "similarity": similarity,
                        "passed": passed,
                        "threshold": case["threshold"],
                    }
                )
            else:
                self.stdout.write(self.style.ERROR("  Error al generar embeddings."))

        # Resumen Final
        self.print_summary(results)

    def cosine_similarity(self, v1, v2):
        """Calcula similitud coseno entre dos vectores"""
        if len(v1) != len(v2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(v1, v2, strict=False))
        norm_a = math.sqrt(sum(a * a for a in v1))
        norm_b = math.sqrt(sum(b * b for b in v2))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def print_summary(self, results):
        self.stdout.write(
            self.style.MIGRATE_HEADING("\n=== RESUMEN DE VALIDACIÓN SEMÁNTICA ===\n")
        )

        total = len(results)
        passed = sum(1 for r in results if r["passed"])

        self.stdout.write(f"Total Pruebas: {total}")
        self.stdout.write(f"Aprobadas: {passed}")
        self.stdout.write(f"Fallidas: {total - passed}")

        self.stdout.write("\nDetalle:")
        self.stdout.write(f"{'TIPO':<30} {'SIMILITUD':<10} {'UMBRAL':<10} {'ESTADO'}")
        self.stdout.write("-" * 60)

        for r in results:
            status = "✅" if r["passed"] else "❌"
            self.stdout.write(
                f"{r['type']:<30} {r['similarity']:.4f}     "
                f"{r['threshold']:<10} {status}"
            )
