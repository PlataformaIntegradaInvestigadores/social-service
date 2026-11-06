"""Client for the embeddings microservice (`/text-processing/vectorize/`).

Feed posts, job offers and every search turn text into a vector through this one
class, so the request, the timeout and the failure handling live in one place.
"""

import logging
from dataclasses import dataclass

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

VECTORIZE_PATH = "/text-processing/vectorize/"


@dataclass(frozen=True)
class TextVector:
    vector: list[float]
    # The text after cleaning/translation, when the service reports it.
    processed_text: str | None = None


class EmbeddingClient:
    def __init__(self, base_url: str | None = None, timeout: int = 30):
        self.base_url = base_url or settings.EMBEDDING_SERVICE_URL
        self.timeout = timeout

    def vectorize(self, text: str) -> TextVector | None:
        """Vector of `text`, or None if the service is down or answers badly."""
        payload = {"text": text, "translate_to_english": True, "clean_text": True}
        try:
            response = requests.post(
                f"{self.base_url}{VECTORIZE_PATH}",
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
            if response.status_code != 200:
                logger.error(
                    f"Error al obtener embedding: {response.status_code} - "
                    f"{response.text}"
                )
                return None

            result = response.json()
            vector = result.get("vector")
            if not vector:
                logger.error("El microservicio no devolvió un vector válido")
                return None

            logger.info(
                f"Embedding generado. Dimensiones: "
                f"{result.get('dimension', len(vector))}"
            )
            return TextVector(vector, result.get("processed_text"))
        except requests.RequestException as e:
            logger.error(f"Error de conexión con microservicio: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado: {str(e)}")
            return None

    def embed(self, text: str) -> list[float] | None:
        """Just the vector of `text`, or None on any failure."""
        result = self.vectorize(text)
        return result.vector if result else None
