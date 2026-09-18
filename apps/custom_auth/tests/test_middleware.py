"""Unitarias de apps/custom_auth/middleware.py: JwtAuthMiddleware resuelve
scope['user'] para conexiones websocket a partir del token en el query string."""

from datetime import UTC, datetime, timedelta

import jwt as pyjwt
from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.custom_auth.identity_principal import IdentityPrincipal
from apps.custom_auth.middleware import JwtAuthMiddleware
from apps.jobs.domain.entities.company import Company


class _InnerApp:
    """Stub de la app ASGI interna: solo registra el scope recibido."""

    def __init__(self):
        self.received_scope = None

    async def __call__(self, scope, receive, send):
        self.received_scope = scope
        return scope


def _run_middleware(query_string: str):
    inner = _InnerApp()
    middleware = JwtAuthMiddleware(inner)
    scope = {"query_string": query_string.encode()}
    # async_to_sync (no asyncio.run): el middleware resuelve Company via
    # sync_to_async, que necesita el puente de asgiref para reutilizar el
    # hilo/conexion de TestCase en vez de abrir uno nuevo sin la transaccion.
    async_to_sync(middleware)(scope, None, None)
    return scope


class TestJwtAuthMiddleware(TestCase):
    def test_sin_query_string_es_anonimo(self):
        scope = _run_middleware("")
        self.assertIsInstance(scope["user"], AnonymousUser)

    def test_sin_token_en_query_string_es_anonimo(self):
        scope = _run_middleware("foo=bar")
        self.assertIsInstance(scope["user"], AnonymousUser)

    def test_token_invalido_es_anonimo(self):
        scope = _run_middleware("token=not-a-real-token")
        self.assertIsInstance(scope["user"], AnonymousUser)

    def test_token_de_investigador_resuelve_identity_principal(self):
        token = AccessToken()
        token["user_id"] = "1"
        token["email"] = "ana@example.com"

        scope = _run_middleware(f"token={token}")

        self.assertIsInstance(scope["user"], IdentityPrincipal)
        self.assertEqual(scope["user"].id, "1")

    def test_token_de_empresa_resuelve_company(self):
        company = Company.objects.create_user(
            username="empresa@example.com", password="x", company_name="Empresa"
        )
        token = AccessToken()
        token["company_id"] = company.id

        scope = _run_middleware(f"token={token}")

        self.assertEqual(scope["user"], company)

    def test_token_expirado_es_anonimo(self):
        expired = pyjwt.encode(
            {
                "user_id": "1",
                "exp": datetime.now(UTC) - timedelta(minutes=5),
            },
            settings.JWT_SIGNING_KEY,
            algorithm="HS256",
        )
        scope = _run_middleware(f"token={expired}")
        self.assertIsInstance(scope["user"], AnonymousUser)
