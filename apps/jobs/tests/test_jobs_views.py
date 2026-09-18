"""Unitarias de JobsView: listado con filtros, detalle, creacion,
edicion y borrado, con las reglas de permisos empresa-vs-usuario. Se
parchea el signal post_save de Jobs para evitar llamadas de red reales."""

from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.custom_auth.identity_principal import IdentityPrincipal
from apps.jobs.domain.entities.company import Company
from apps.jobs.domain.entities.jobs import Jobs
from apps.jobs.domain.entities.postulants import Postulants

SIGNAL_UPDATE_EMBEDDING = (
    "apps.jobs.infrastructure.signals.vector_service.update_job_embedding"
)


class BaseJobsViewsTestCase(APITestCase):
    def setUp(self):
        patcher = patch(SIGNAL_UPDATE_EMBEDDING, return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.client = APIClient()
        self.company = Company.objects.create_user(
            username="empresa@example.com",
            password="secret123",
            company_name="Empresa Uno",
        )
        self.other_company = Company.objects.create_user(
            username="empresa2@example.com",
            password="secret123",
            company_name="Empresa Dos",
        )
        self.user = IdentityPrincipal(id="u1", username="ana")
        self.job = Jobs.objects.create(
            company=self.company, title="Backend Dev", description="Python jobs"
        )


class TestJobsViewGet(BaseJobsViewsTestCase):
    def test_detalle_visible_para_usuario_regular(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/jobs/{self.job.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Backend Dev")

    def test_detalle_404_si_no_existe(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/jobs/999999/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_detalle_prohibido_para_otra_compania(self):
        self.client.force_authenticate(user=self.other_company)

        response = self.client.get(f"/api/v1/jobs/{self.job.id}/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_listado_filtra_por_query(self):
        Jobs.objects.create(
            company=self.company, title="Frontend Dev", description="React jobs"
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/jobs/?q=Python")

        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["title"], "Backend Dev")

    def test_listado_filtra_por_location_type_experience_remote(self):
        Jobs.objects.create(
            company=self.company,
            title="Remote Job",
            description="desc",
            location="Bogota",
            job_type="contract",
            experience_level="senior",
            is_remote=True,
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            "/api/v1/jobs/?location=Bogota&type=contract&experience=senior&remote=true"
        )

        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["title"], "Remote Job")

    def test_listado_usa_serializer_de_compania_para_companias(self):
        self.client.force_authenticate(user=self.company)

        response = self.client.get("/api/v1/jobs/")

        self.assertEqual(len(response.data), 1)
        self.assertIn("applications_count", response.data[0])
        self.assertIn("recent_applications", response.data[0])

    def test_listado_usa_serializer_simplificado_para_usuarios(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/jobs/")

        self.assertNotIn("description", response.data[0])
        self.assertIn("has_applied", response.data[0])


class TestJobsViewPost(BaseJobsViewsTestCase):
    def test_compania_puede_crear_trabajo(self):
        self.client.force_authenticate(user=self.company)

        response = self.client.post(
            "/api/v1/jobs/",
            {"title": "Data Engineer", "description": "desc"},
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Jobs.objects.filter(title="Data Engineer").count(), 1)

    def test_usuario_regular_no_puede_crear_trabajo(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/jobs/",
            {"title": "Data Engineer", "description": "desc"},
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_ignora_campo_company_recibido_en_payload(self):
        self.client.force_authenticate(user=self.company)

        response = self.client.post(
            "/api/v1/jobs/",
            {
                "title": "Data Engineer",
                "description": "desc",
                "company": self.other_company.id,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = Jobs.objects.get(title="Data Engineer")
        self.assertEqual(created.company_id, self.company.id)


class TestJobsViewPut(BaseJobsViewsTestCase):
    def test_compania_propietaria_puede_editar(self):
        self.client.force_authenticate(user=self.company)

        response = self.client.put(
            f"/api/v1/jobs/{self.job.id}/", {"title": "Backend Dev Senior"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.job.refresh_from_db()
        self.assertEqual(self.job.title, "Backend Dev Senior")

    def test_otra_compania_no_puede_editar(self):
        self.client.force_authenticate(user=self.other_company)

        response = self.client.put(
            f"/api/v1/jobs/{self.job.id}/", {"title": "Hackeado"}
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_usuario_regular_no_puede_editar(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.put(
            f"/api/v1/jobs/{self.job.id}/", {"title": "Hackeado"}
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_404_si_no_existe(self):
        self.client.force_authenticate(user=self.company)

        response = self.client.put("/api/v1/jobs/999999/", {"title": "x"})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TestJobsViewDelete(BaseJobsViewsTestCase):
    def test_compania_propietaria_puede_eliminar(self):
        self.client.force_authenticate(user=self.company)

        response = self.client.delete(f"/api/v1/jobs/{self.job.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Jobs.objects.filter(id=self.job.id).exists())

    def test_otra_compania_no_puede_eliminar(self):
        self.client.force_authenticate(user=self.other_company)

        response = self.client.delete(f"/api/v1/jobs/{self.job.id}/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_404_si_no_existe(self):
        self.client.force_authenticate(user=self.company)

        response = self.client.delete("/api/v1/jobs/999999/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TestJobsSerializerHasAppliedAndUserApplication(BaseJobsViewsTestCase):
    def test_has_applied_true_si_ya_postulo(self):
        Postulants.objects.create(user_identity_id=self.user.id, job=self.job)
        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/jobs/{self.job.id}/")

        self.assertTrue(response.data["has_applied"])
        self.assertIsNotNone(response.data["user_application"])

    def test_has_applied_false_si_no_postulo(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/jobs/{self.job.id}/")

        self.assertFalse(response.data["has_applied"])
        self.assertIsNone(response.data["user_application"])
