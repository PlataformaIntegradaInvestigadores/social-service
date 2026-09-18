"""Unitarias de apps/custom_auth/authentication.py: DualUserJWTAuthentication
resuelve el usuario autenticado como Company o IdentityPrincipal segun el
contenido del token, sin fallar en tokens invalidos (permite acceso anonimo)."""

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase

from apps.custom_auth.authentication import DualUserJWTAuthentication
from apps.custom_auth.identity_principal import IdentityPrincipal
from apps.jobs.domain.entities.company import Company


class TestGetUser(TestCase):
    def setUp(self):
        self.auth = DualUserJWTAuthentication()

    def test_token_con_company_id_retorna_la_empresa(self):
        company = Company.objects.create_user(
            username="empresa@example.com",
            password="x",
            company_name="Empresa",
        )
        user = self.auth.get_user({"company_id": company.id})
        self.assertEqual(user, company)

    def test_token_con_company_id_inactiva_retorna_anonymous(self):
        company = Company.objects.create_user(
            username="empresa2@example.com",
            password="x",
            company_name="Empresa",
            is_active=False,
        )
        user = self.auth.get_user({"company_id": company.id})
        self.assertIsInstance(user, AnonymousUser)

    def test_token_con_company_id_inexistente_retorna_anonymous(self):
        user = self.auth.get_user({"company_id": "no-existe"})
        self.assertIsInstance(user, AnonymousUser)

    def test_token_con_user_id_retorna_identity_principal(self):
        user = self.auth.get_user({"user_id": "1", "email": "ana@example.com"})
        self.assertIsInstance(user, IdentityPrincipal)
        self.assertEqual(user.id, "1")

    def test_token_sin_company_id_ni_user_id_retorna_anonymous(self):
        user = self.auth.get_user({})
        self.assertIsInstance(user, AnonymousUser)

    def test_token_malformado_retorna_anonymous(self):
        class BadToken(dict):
            def __contains__(self, key):
                raise KeyError("boom")

        user = self.auth.get_user(BadToken())
        self.assertIsInstance(user, AnonymousUser)


class TestAuthenticate(TestCase):
    def test_token_invalido_retorna_none_en_vez_de_lanzar(self):
        auth = DualUserJWTAuthentication()
        request = RequestFactory().get(
            "/", HTTP_AUTHORIZATION="Bearer not-a-real-token"
        )
        self.assertIsNone(auth.authenticate(request))

    def test_sin_header_authorization_retorna_none(self):
        auth = DualUserJWTAuthentication()
        request = RequestFactory().get("/")
        self.assertIsNone(auth.authenticate(request))
