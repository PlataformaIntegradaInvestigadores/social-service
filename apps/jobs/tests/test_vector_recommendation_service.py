"""Unitarias de VectorRecommendationService: obtencion de embeddings,
jobs similares (con fallback), trending, actualizacion de interacciones
y jobs de fallback. El signal post_save de Jobs se parchea para evitar
llamadas de red reales."""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.jobs.domain.entities.company import Company
from apps.jobs.domain.entities.jobs import Jobs
from apps.jobs.domain.services.vector_recommendation_service import (
    VectorRecommendationService,
)

SIGNAL_UPDATE_EMBEDDING = (
    "apps.jobs.infrastructure.signals.vector_service.update_job_embedding"
)


class BaseVectorServiceTestCase(TestCase):
    def setUp(self):
        patcher = patch(SIGNAL_UPDATE_EMBEDDING, return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.company = Company.objects.create_user(
            username="empresa@example.com",
            password="secret123",
            company_name="Empresa Uno",
        )
        self.service = VectorRecommendationService(
            embedding_service_url="http://embeddings.test"
        )


class TestGetEmbeddingFromMicroservice(BaseVectorServiceTestCase):
    @patch(
        "apps.jobs.domain.services.vector_recommendation_service.requests.post"
    )
    def test_retorna_vector_en_respuesta_exitosa(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200, json=lambda: {"vector": [0.1, 0.2], "dimension": 2}
        )

        result = self.service.get_embedding_from_microservice(
            {"title": "Backend Dev", "description": "desc"}
        )

        self.assertEqual(result, [0.1, 0.2])

    @patch(
        "apps.jobs.domain.services.vector_recommendation_service.requests.post"
    )
    def test_retorna_none_si_no_hay_vector(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200, json=lambda: {"vector": None}
        )

        self.assertIsNone(self.service.get_embedding_from_microservice({}))

    @patch(
        "apps.jobs.domain.services.vector_recommendation_service.requests.post"
    )
    def test_retorna_none_si_status_no_es_200(self, mock_post):
        mock_post.return_value = MagicMock(status_code=500, text="error")

        self.assertIsNone(self.service.get_embedding_from_microservice({}))

    @patch(
        "apps.jobs.domain.services.vector_recommendation_service.requests.post"
    )
    def test_retorna_none_si_hay_excepcion_de_conexion(self, mock_post):
        import requests

        mock_post.side_effect = requests.ConnectionError("no disponible")

        self.assertIsNone(self.service.get_embedding_from_microservice({}))

    @patch(
        "apps.jobs.domain.services.vector_recommendation_service.requests.post"
    )
    def test_retorna_none_si_hay_excepcion_inesperada(self, mock_post):
        mock_post.side_effect = ValueError("boom")

        self.assertIsNone(self.service.get_embedding_from_microservice({}))


class TestUpdateJobEmbedding(BaseVectorServiceTestCase):
    def test_actualiza_embedding_si_hay_vector(self):
        job = Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )
        with patch.object(
            self.service, "get_embedding_from_microservice", return_value=[0.1] * 768
        ):
            result = self.service.update_job_embedding(job)

        self.assertTrue(result)
        job.refresh_from_db()
        self.assertIsNotNone(job.embedding)

    def test_retorna_false_si_no_hay_vector(self):
        job = Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )
        with patch.object(
            self.service, "get_embedding_from_microservice", return_value=None
        ):
            result = self.service.update_job_embedding(job)

        self.assertFalse(result)


class TestGetSimilarJobs(BaseVectorServiceTestCase):
    def test_sin_embedding_de_usuario_usa_fallback(self):
        Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )

        result = self.service.get_similar_jobs(user_embedding=None, limit=5)

        self.assertEqual(len(list(result)), 1)

    def test_con_embedding_pero_sin_jobs_con_embedding_usa_fallback(self):
        Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )

        result = self.service.get_similar_jobs(
            user_embedding=[0.1] * 768, limit=5, similarity_threshold=0.0
        )

        self.assertEqual(len(list(result)), 1)

    def test_excluye_ids_especificados(self):
        job1 = Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )
        Jobs.objects.create(
            company=self.company, title="Frontend Dev", description="desc"
        )

        result = self.service.get_similar_jobs(
            user_embedding=None, limit=5, exclude_job_ids=[job1.id]
        )

        ids = [job.id for job in result]
        self.assertNotIn(job1.id, ids)

    def test_combina_resultados_con_embedding_y_fallback_si_faltan(self):
        job = Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )
        with patch.object(
            self.service, "get_embedding_from_microservice", return_value=[0.1] * 768
        ):
            self.service.update_job_embedding(job)

        result = self.service.get_similar_jobs(
            user_embedding=[0.1] * 768, limit=5, similarity_threshold=0.0
        )

        self.assertGreaterEqual(len(list(result)), 1)


class TestGetTrendingJobs(BaseVectorServiceTestCase):
    def test_retorna_jobs_ordenados_por_trending_score(self):
        Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )

        result = self.service.get_trending_jobs(limit=5)

        self.assertEqual(len(list(result)), 1)


class TestUpdateJobInteractions(BaseVectorServiceTestCase):
    def test_actualiza_view_count_e_interactions_score(self):
        job = Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )

        self.service.update_job_interactions(job.id, "view")

        job.refresh_from_db()
        self.assertEqual(job.view_count, 1)
        self.assertAlmostEqual(job.interactions_score, 0.1)

    def test_actualiza_application_count_e_interactions_score(self):
        job = Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )

        self.service.update_job_interactions(job.id, "application")

        job.refresh_from_db()
        self.assertEqual(job.application_count, 1)
        self.assertAlmostEqual(job.interactions_score, 1.0)

    def test_no_lanza_si_job_no_existe(self):
        self.service.update_job_interactions(999999, "view")


class TestGetFallbackJobs(BaseVectorServiceTestCase):
    def test_retorna_jobs_ordenados_por_score_de_fallback(self):
        Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )

        result = self.service.get_fallback_jobs(limit=5)

        self.assertEqual(len(list(result)), 1)

    def test_excluye_ids_especificados(self):
        job1 = Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )

        result = self.service.get_fallback_jobs(limit=5, exclude_job_ids=[job1.id])

        self.assertEqual(list(result), [])
