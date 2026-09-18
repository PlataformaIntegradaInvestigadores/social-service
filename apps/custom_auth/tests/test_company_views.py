"""Unitarias de las vistas de empresa que siguen vivas en el backend social
(el resto de la identidad/perfil/registro de empresa es responsabilidad de
profile_identity_backend, ver custom_auth/tests.py para esas rutas retiradas)."""

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.jobs.domain.entities.company import Company


class TestCompanyChoicesView(APITestCase):
    def test_retorna_industrias_y_rangos_de_empleados(self):
        response = self.client.get("/api/companies/choices/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("industries", response.data)
        self.assertIn("employee_counts", response.data)
        self.assertTrue(len(response.data["industries"]) > 0)


class TestCompanyListView(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.company = Company.objects.create_user(
            username="empresa1@example.com", password="x", company_name="Uno"
        )

    def test_requiere_autenticacion(self):
        response = self.client.get("/api/companies/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_lista_empresas_activas(self):
        self.client.force_authenticate(user=self.company)
        response = self.client.get("/api/companies/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_filtra_solo_verificadas_con_verified_only(self):
        Company.objects.create_user(
            username="empresa2@example.com",
            password="x",
            company_name="Dos",
            is_verified=True,
        )
        self.client.force_authenticate(user=self.company)

        response = self.client.get("/api/companies/", {"verified_only": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["company_name"], "Dos")


class TestCompanyUpdateView(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.company = Company.objects.create_user(
            username="empresa1@example.com", password="x", company_name="Uno"
        )
        self.other = Company.objects.create_user(
            username="empresa2@example.com", password="x", company_name="Dos"
        )

    def test_no_puede_editar_el_perfil_de_otra_empresa(self):
        self.client.force_authenticate(user=self.company)

        response = self.client.patch(
            f"/api/companies/{self.other.id}/update/",
            {"company_name": "Hackeado"},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_puede_editar_su_propio_perfil(self):
        self.client.force_authenticate(user=self.company)

        response = self.client.patch(
            f"/api/companies/{self.company.id}/update/",
            {"company_name": "Nuevo Nombre"},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.company.refresh_from_db()
        self.assertEqual(self.company.company_name, "Nuevo Nombre")


class TestCompanyDetailAndProfileViews(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.company = Company.objects.create_user(
            username="empresa1@example.com", password="x", company_name="Uno"
        )

    def test_detail_requiere_autenticacion(self):
        response = self.client.get(f"/api/companies/{self.company.id}/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_detail_retorna_la_empresa(self):
        self.client.force_authenticate(user=self.company)
        response = self.client.get(f"/api/companies/{self.company.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.company.id)

    def test_profile_retorna_la_empresa_autenticada(self):
        self.client.force_authenticate(user=self.company)
        response = self.client.get("/api/companies/profile/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.company.id)
