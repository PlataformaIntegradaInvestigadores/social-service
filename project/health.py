import logging
import socket

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
import redis

logger = logging.getLogger(__name__)


def _local_ip() -> str:
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return "unknown"


def health_check(request):
    try:
        connection.ensure_connection()
        db_status = "ok"
    except Exception:
        logger.exception("Health check DB failure")
        db_status = "error"

    try:
        redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            socket_connect_timeout=3,
        ).ping()
        redis_status = "ok"
    except Exception:
        logger.exception("Health check Redis failure")
        redis_status = "error"

    statuses = {db_status, redis_status}
    if statuses == {"ok"}:
        group_status, global_status, http_status = "Operativo", "Online", 200
    elif "ok" in statuses:
        group_status, global_status, http_status = "Degradado", "Degraded", 503
    else:
        group_status, global_status, http_status = "Caído", "Offline", 503

    payload = {
        "server_name": "social-service",
        "ip_address": _local_ip(),
        "global_status": global_status,
        "groups": [
            {
                "group_name": "Database Cluster",
                "group_status": group_status,
                "services": [
                    {"name": "postgres", "status": db_status},
                    {"name": "redis-cache", "status": redis_status},
                ],
            }
        ],
    }
    return JsonResponse(payload, status=http_status)
