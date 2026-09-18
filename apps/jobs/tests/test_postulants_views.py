"""Unitarias de las vistas de postulaciones: PostulantsView (CRUD),
ApplicationStatusView, CompanyApplicationsView y UserApplicationsView.
Se parchea el signal post_save de Jobs para evitar llamadas de red
reales."""

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


class BasePostulantsViewsTestCase(APITestCase):
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
        self.other_user = IdentityPrincipal(id="u2", username="beto")
        self.job = Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )


class TestPostulantsViewGet(BasePostulantsViewsTestCase):
    def test_usuario_ve_su_propia_postulacion(self):
        postulant = Postulants.objects.create(
            user_identity_id=self.user.id, job=self.job
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/applications/{postulant.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_usuario_no_puede_ver_postulacion_ajena(self):
        postulant = Postulants.objects.create(
            user_identity_id=self.other_user.id, job=self.job
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/applications/{postulant.id}/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_compania_ve_postulacion_a_su_trabajo(self):
        postulant = Postulants.objects.create(
            user_identity_id=self.user.id, job=self.job
        )
        self.client.force_authenticate(user=self.company)

        response = self.client.get(f"/api/v1/applications/{postulant.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_otra_compania_no_puede_ver_postulacion(self):
        postulant = Postulants.objects.create(
            user_identity_id=self.user.id, job=self.job
        )
        self.client.force_authenticate(user=self.other_company)

        response = self.client.get(f"/api/v1/applications/{postulant.id}/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_404_si_no_existe(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/applications/999999/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_listado_filtra_por_job_id_y_status(self):
        Postulants.objects.create(
            user_identity_id=self.user.id, job=self.job, status="pending"
        )
        other_job = Jobs.objects.create(
            company=self.company, title="Other", description="desc"
        )
        Postulants.objects.create(
            user_identity_id=self.user.id, job=other_job, status="accepted"
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/applications/?job_id={self.job.id}&status=pending"
        )

        self.assertEqual(len(response.data), 1)


class TestPostulantsViewPost(BasePostulantsViewsTestCase):
    def test_usuario_puede_postularse(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/applications/", {"job": self.job.id, "cover_letter": "Hola"}
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Postulants.objects.filter(job=self.job).count(), 1)

    def test_compania_no_puede_postularse(self):
        self.client.force_authenticate(user=self.company)

        response = self.client.post(
            "/api/v1/applications/", {"job": self.job.id}
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_sin_job_id_retorna_400(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post("/api/v1/applications/", {})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_job_inexistente_retorna_404(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/applications/", {"job": 999999}
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_postulacion_duplicada_retorna_400(self):
        Postulants.objects.create(user_identity_id=self.user.id, job=self.job)
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/applications/", {"job": self.job.id}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestPostulantsViewPut(BasePostulantsViewsTestCase):
    def test_compania_propietaria_actualiza_estado(self):
        postulant = Postulants.objects.create(
            user_identity_id=self.user.id, job=self.job
        )
        self.client.force_authenticate(user=self.company)

        response = self.client.put(
            f"/api/v1/applications/{postulant.id}/", {"status": "accepted"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        postulant.refresh_from_db()
        self.assertEqual(postulant.status, "accepted")

    def test_otra_compania_no_puede_actualizar(self):
        postulant = Postulants.objects.create(
            user_identity_id=self.user.id, job=self.job
        )
        self.client.force_authenticate(user=self.other_company)

        response = self.client.put(
            f"/api/v1/applications/{postulant.id}/", {"status": "accepted"}
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_usuario_propietario_puede_actualizar_cover_letter(self):
        postulant = Postulants.objects.create(
            user_identity_id=self.user.id, job=self.job
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.put(
            f"/api/v1/applications/{postulant.id}/",
            {"cover_letter": "Actualizada", "status": "accepted"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        postulant.refresh_from_db()
        self.assertEqual(postulant.cover_letter, "Actualizada")
        # El usuario no puede cambiar el status: solo cover_letter/resume_file
        # pasan el filtro de allowed_fields.
        self.assertEqual(postulant.status, "pending")

    def test_usuario_no_propietario_no_puede_actualizar(self):
        postulant = Postulants.objects.create(
            user_identity_id=self.other_user.id, job=self.job
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.put(
            f"/api/v1/applications/{postulant.id}/", {"cover_letter": "x"}
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_404_si_no_existe(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.put("/api/v1/applications/999999/", {})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TestPostulantsViewDelete(BasePostulantsViewsTestCase):
    def test_usuario_propietario_puede_eliminar(self):
        postulant = Postulants.objects.create(
            user_identity_id=self.user.id, job=self.job
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.delete(f"/api/v1/applications/{postulant.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_compania_no_puede_eliminar(self):
        postulant = Postulants.objects.create(
            user_identity_id=self.user.id, job=self.job
        )
        self.client.force_authenticate(user=self.company)

        response = self.client.delete(f"/api/v1/applications/{postulant.id}/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_otro_usuario_no_puede_eliminar(self):
        postulant = Postulants.objects.create(
            user_identity_id=self.other_user.id, job=self.job
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.delete(f"/api/v1/applications/{postulant.id}/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_404_si_no_existe(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.delete("/api/v1/applications/999999/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TestApplicationStatusView(BasePostulantsViewsTestCase):
    def test_compania_no_puede_consultar(self):
        self.client.force_authenticate(user=self.company)

        response = self.client.get(
            f"/api/v1/jobs/{self.job.id}/application-status/"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_job_inexistente_retorna_404(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/jobs/999999/application-status/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retorna_has_applied_true_con_datos(self):
        Postulants.objects.create(user_identity_id=self.user.id, job=self.job)
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/jobs/{self.job.id}/application-status/"
        )

        self.assertTrue(response.data["has_applied"])
        self.assertIsNotNone(response.data["application"])

    def test_retorna_has_applied_false_sin_postulacion(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/jobs/{self.job.id}/application-status/"
        )

        self.assertFalse(response.data["has_applied"])
        self.assertIsNone(response.data["application"])


class TestCompanyApplicationsView(BasePostulantsViewsTestCase):
    def test_usuario_regular_no_puede_acceder(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/company/applications/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_compania_ve_postulaciones_a_sus_trabajos(self):
        Postulants.objects.create(user_identity_id=self.user.id, job=self.job)
        self.client.force_authenticate(user=self.company)

        response = self.client.get("/api/v1/company/applications/")

        self.assertEqual(len(response.data), 1)

    def test_filtra_por_job_id_y_status(self):
        Postulants.objects.create(
            user_identity_id=self.user.id, job=self.job, status="pending"
        )
        self.client.force_authenticate(user=self.company)

        response = self.client.get(
            f"/api/v1/jobs/{self.job.id}/applications/?status=pending"
        )

        self.assertEqual(len(response.data), 1)

    def test_put_actualiza_status_y_notes(self):
        postulant = Postulants.objects.create(
            user_identity_id=self.user.id, job=self.job
        )
        self.client.force_authenticate(user=self.company)

        response = self.client.put(
            "/api/v1/company/applications/",
            {
                "application_id": postulant.id,
                "status": "reviewing",
                "notes": "En revision",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        postulant.refresh_from_db()
        self.assertEqual(postulant.status, "reviewing")
        self.assertEqual(postulant.notes, "En revision")

    def test_put_usuario_regular_prohibido(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.put("/api/v1/company/applications/", {})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_put_sin_application_id_o_status_retorna_400(self):
        self.client.force_authenticate(user=self.company)

        response = self.client.put("/api/v1/company/applications/", {})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_put_postulacion_no_encontrada_o_ajena_retorna_404(self):
        postulant = Postulants.objects.create(
            user_identity_id=self.user.id, job=self.job
        )
        self.client.force_authenticate(user=self.other_company)

        response = self.client.put(
            "/api/v1/company/applications/",
            {"application_id": postulant.id, "status": "accepted"},
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TestUserApplicationsView(BasePostulantsViewsTestCase):
    def test_compania_no_puede_acceder(self):
        self.client.force_authenticate(user=self.company)

        response = self.client.get("/api/v1/user/applications/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_usuario_ve_sus_propias_postulaciones(self):
        Postulants.objects.create(user_identity_id=self.user.id, job=self.job)
        Postulants.objects.create(user_identity_id=self.other_user.id, job=self.job)
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/user/applications/")

        self.assertEqual(len(response.data), 1)

    def test_filtra_por_status(self):
        Postulants.objects.create(
            user_identity_id=self.user.id, job=self.job, status="pending"
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/user/applications/?status=accepted")

        self.assertEqual(len(response.data), 0)
