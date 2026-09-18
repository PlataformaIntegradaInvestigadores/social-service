import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def fetch_grs_topics(scopus_ids, k=5):
    """Consulta al GRS (predictive_model_backend) los tópicos recomendados
    para el grupo persistente al que pertenezcan los scopus_id dados.

    Retorna una lista de nombres de tópico, o None si no hay vínculo con
    ningún grupo persistente del GRS o si el servicio no está disponible.
    """
    # scopus_ids = [sid for sid in scopus_ids if sid]
    scopus_ids = [str(sid) for sid in scopus_ids if sid]
    if not scopus_ids:
        return None

    try:
        response = requests.post(
            f"{settings.GRS_SERVICE_URL}/by-members",
            json={"scopus_ids": scopus_ids},
            params={"k": k},
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        logger.warning("No se pudo consultar el GRS: %s", exc)
        return None

    if not data.get("linked"):
        return None

    return [
        recommendation["topic"] for recommendation in data.get("recommendations", [])
    ]
