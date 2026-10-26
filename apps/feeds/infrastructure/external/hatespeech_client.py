"""
Cliente HTTP de hatespeech-service (red interna centinela-net).

hatespeech-service autentica servicio a servicio con ``X-Internal-Api-Key`` y
recibe la identidad del usuario que actúa en ``X-Acting-User-Id`` /
``X-Acting-User-Is-Staff``. El front nunca habla con él directamente: todo
pasa por social-service.
"""

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class HateSpeechUnavailable(Exception):
    """El servicio no responde o devuelve 5xx: se puede reintentar más tarde."""


class HateSpeechError(Exception):
    """Respuesta 4xx: la petición es inválida y reintentar no ayuda."""

    def __init__(self, status_code: int, detail):
        super().__init__(f"hatespeech-service {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class HateSpeechClient:
    def __init__(self, base_url=None, api_key=None, timeout=None):
        self.base_url = (
            base_url if base_url is not None else settings.HATESPEECH_SERVICE_URL
        ).rstrip("/")
        self.api_key = (
            api_key if api_key is not None else settings.HATESPEECH_INTERNAL_API_KEY
        )
        self.timeout = timeout if timeout is not None else settings.HATESPEECH_TIMEOUT

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    def _headers(self, acting_user_id=None, is_staff=False) -> dict:
        headers = {"X-Internal-Api-Key": self.api_key}
        if acting_user_id is not None:
            headers["X-Acting-User-Id"] = str(acting_user_id)
        if is_staff:
            headers["X-Acting-User-Is-Staff"] = "true"
        return headers

    def _request(self, method, path, *, acting_user_id=None, is_staff=False, **kwargs):
        if not self.enabled:
            raise HateSpeechUnavailable("HATESPEECH_SERVICE_URL no configurado")
        url = f"{self.base_url}{path}"
        try:
            response = requests.request(
                method,
                url,
                headers=self._headers(acting_user_id, is_staff),
                timeout=self.timeout,
                **kwargs,
            )
        except requests.RequestException as exc:
            logger.warning(
                "hatespeech-service no disponible (%s %s): %s", method, path, exc
            )
            raise HateSpeechUnavailable(str(exc)) from exc

        if response.status_code >= 500:
            raise HateSpeechUnavailable(
                f"hatespeech-service respondió {response.status_code}"
            )
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise HateSpeechError(response.status_code, detail)
        return response.json()

    def is_healthy(self) -> bool:
        if not self.enabled:
            return False
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
        except requests.RequestException:
            return False
        return response.status_code == 200

    def classify(self, *, content_type, content_id, text, author_id, explain=True):
        return self._request(
            "POST",
            "/api/v1/classify",
            json={
                "text": text,
                "content_type": content_type,
                "content_id": str(content_id),
                "author_id": author_id or None,
                "explain": explain,
            },
        )

    def report(self, *, content_type, content_id, reporter_id, reason, text, author_id):
        return self._request(
            "POST",
            "/api/v1/reports",
            acting_user_id=reporter_id,
            json={
                "content_type": content_type,
                "content_id": str(content_id),
                "reporter_id": str(reporter_id),
                "reason": reason or None,
                "text": text,
                "author_id": author_id or None,
            },
        )

    def review_queue(self, *, moderator_id, params=None):
        return self._request(
            "GET",
            "/api/v1/review-queue",
            acting_user_id=moderator_id,
            is_staff=True,
            params=params or {},
        )

    def review_case(self, *, moderator_id, case_id):
        return self._request(
            "GET",
            f"/api/v1/review-queue/{int(case_id)}",
            acting_user_id=moderator_id,
            is_staff=True,
        )

    def decide(self, *, moderator_id, case_id, decision, notes=None):
        return self._request(
            "POST",
            f"/api/v1/review-queue/{int(case_id)}/decision",
            acting_user_id=moderator_id,
            is_staff=True,
            json={"decision": decision, "notes": notes or None},
        )
