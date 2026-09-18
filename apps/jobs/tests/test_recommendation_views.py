"""Unitarias de JobRecommendationsView, JobTrendingView y
JobSemanticSearchView (vistas basadas en clases de
recommendations_views.py, las unicas realmente enrutadas via
jobs_urls.py). Se parchea el signal post_save de Jobs para evitar
llamadas de red reales."""

from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.custom_auth.identity_principal import IdentityPrincipal
from apps.jobs.domain.entities.company import Company
from apps.jobs.domain.entities.jobs import Jobs

SIGNAL_UPDATE_EMBEDDING = (
    "apps.jobs.infrastructure.signals.vector_service.update_job_embedding"
)


class BaseRecommendationViewsTestCase(APITestCase):
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
        self.user = IdentityPrincipal(id="u1", username="ana")
        self.job = Jobs.objects.create(
            company=self.company, title="Backend Dev", description="Python jobs"
        )


class TestJobRecommendationsView(BaseRecommendationViewsTestCase):
    def test_requiere_autenticacion(self):
        response = self.client.get("/api/v1/jobs/recommendations/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retorna_recomendaciones_basicas(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/jobs/recommendations/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_limit_se_acota_a_50(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/jobs/recommendations/?limit=1000")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_limit_invalido_usa_default(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/jobs/recommendations/?limit=abc")

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class TestJobTrendingView(BaseRecommendationViewsTestCase):
    def test_requiere_autenticacion(self):
        response = self.client.get("/api/v1/jobs/trending/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retorna_trabajos_trending(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/jobs/trending/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)


class TestJobSemanticSearchView(BaseRecommendationViewsTestCase):
    def test_requiere_autenticacion(self):
        response = self.client.post(
            "/api/v1/jobs/semantic-search/", {"query": "Python"}
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_query_vacia_retorna_400(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post("/api/v1/jobs/semantic-search/", {"query": ""})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_busqueda_textual_encuentra_resultados(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/jobs/semantic-search/",
            {"query": "Python"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_limit_invalido_usa_default(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/jobs/semantic-search/",
            {"query": "Python", "limit": "abc"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
