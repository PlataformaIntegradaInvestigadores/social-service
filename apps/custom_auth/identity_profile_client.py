import logging
from urllib.parse import urljoin

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def normalize_profile_picture(value):
    if not value:
        return ""
    value = str(value)
    if value.startswith(("http://", "https://", "/")):
        return value
    if value.startswith("media/"):
        return f"/{value}"
    return f"/media/{value}"


def merge_identity_snapshot(base_snapshot, identity_payload):
    snapshot = dict(base_snapshot or {})
    if not identity_payload:
        snapshot["profile_picture"] = normalize_profile_picture(
            snapshot.get("profile_picture")
        )
        return snapshot

    for field in (
        "id",
        "username",
        "first_name",
        "last_name",
        "scopus_id",
        "institution",
        "investigation_camp",
        "email_institution",
        "website",
    ):
        value = identity_payload.get(field)
        if value not in (None, ""):
            snapshot[field] = str(value)

    snapshot["profile_picture"] = normalize_profile_picture(
        identity_payload.get("profile_picture") or snapshot.get("profile_picture")
    )
    return snapshot


def get_identity_user_snapshot(user_id, authorization_header="", cache=None):
    if not user_id:
        return None

    cache_key = str(user_id)
    if cache is not None and cache_key in cache:
        return cache[cache_key]

    base_url = getattr(
        settings, "PROFILE_IDENTITY_BASE_URL", "http://identity-service:8002"
    )
    url = urljoin(base_url.rstrip("/") + "/", f"api/users/{user_id}/")
    headers = {}
    if authorization_header:
        headers["Authorization"] = authorization_header

    try:
        response = requests.get(url, headers=headers, timeout=2)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        logger.warning("No se pudo resolver perfil de identidad %s: %s", user_id, exc)
        data = None

    if cache is not None:
        cache[cache_key] = data
    return data


def get_identity_group_detail(group_id, authorization_header=""):
    """Obtiene el detalle de un grupo (incluye sus miembros con scopus_id)
    desde profile_identity_backend, fuente canonica de grupos."""
    if not group_id:
        return None

    base_url = getattr(
        settings, "PROFILE_IDENTITY_BASE_URL", "http://identity-service:8002"
    )
    url = urljoin(base_url.rstrip("/") + "/", f"api/groups/{group_id}/")
    headers = {}
    if authorization_header:
        headers["Authorization"] = authorization_header

    try:
        response = requests.get(url, headers=headers, timeout=3)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        logger.warning("No se pudo resolver grupo de identidad %s: %s", group_id, exc)
        return None
