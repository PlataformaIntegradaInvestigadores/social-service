"""Unitarias de JobsService: obtencion de embeddings desde el
microservicio, recomendaciones basicas/trending/busqueda semantica y
aplicacion de filtros. Los signals post_save de Jobs (que tambien llaman
al microservicio de embeddings) se parchean para evitar llamadas de red
reales y mantener los tests deterministas."""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.jobs.domain.entities.company import Company
from apps.jobs.domain.entities.jobs import Jobs
from apps.jobs.domain.services.jobs_service import JobsService

SIGNAL_UPDATE_EMBEDDING = (
    "apps.jobs.infrastructure.signals.vector_service.update_job_embedding"
)


class BaseJobsServiceTestCase(TestCase):
    def setUp(self):
        patcher = patch(SIGNAL_UPDATE_EMBEDDING, return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.company = Company.objects.create_user(
            username="empresa@example.com",
            password="secret123",
            company_name="Empresa Uno",
        )
        self.service = JobsService(embedding_service_url="http://embeddings.test")


class TestGetEmbeddingFromMicroservice(BaseJobsServiceTestCase):
    @patch("apps.jobs.domain.services.jobs_service.requests.post")
    def test_retorna_vector_en_respuesta_exitosa(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200, json=lambda: {"vector": [0.1, 0.2], "dimension": 2}
        )

        result = self.service.get_embedding_from_microservice("texto")

        self.assertEqual(result, [0.1, 0.2])

    @patch("apps.jobs.domain.services.jobs_service.requests.post")
    def test_retorna_none_si_no_hay_vector_en_respuesta(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200, json=lambda: {"vector": None}
        )

        self.assertIsNone(self.service.get_embedding_from_microservice("texto"))

    @patch("apps.jobs.domain.services.jobs_service.requests.post")
    def test_retorna_none_si_status_no_es_200(self, mock_post):
        mock_post.return_value = MagicMock(status_code=500, text="error")

        self.assertIsNone(self.service.get_embedding_from_microservice("texto"))

    @patch("apps.jobs.domain.services.jobs_service.requests.post")
    def test_retorna_none_si_hay_excepcion_de_conexion(self, mock_post):
        import requests

        mock_post.side_effect = requests.ConnectionError("no disponible")

        self.assertIsNone(self.service.get_embedding_from_microservice("texto"))

    @patch("apps.jobs.domain.services.jobs_service.requests.post")
    def test_retorna_none_si_hay_excepcion_inesperada(self, mock_post):
        mock_post.side_effect = ValueError("boom")

        self.assertIsNone(self.service.get_embedding_from_microservice("texto"))


class TestUpdateJobEmbedding(BaseJobsServiceTestCase):
    def test_actualiza_embedding_si_microservicio_responde(self):
        job = Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )
        with patch.object(
            self.service, "get_embedding_from_microservice", return_value=[0.1] * 768
        ):
            result = self.service.update_job_embedding(job.id)

        self.assertTrue(result)
        job.refresh_from_db()
        self.assertIsNotNone(job.embedding)

    def test_retorna_false_si_microservicio_no_devuelve_vector(self):
        job = Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )
        with patch.object(
            self.service, "get_embedding_from_microservice", return_value=None
        ):
            result = self.service.update_job_embedding(job.id)

        self.assertFalse(result)

    def test_retorna_false_si_job_no_existe(self):
        self.assertFalse(self.service.update_job_embedding(999999))


class TestGenerateJobEmbeddingText(BaseJobsServiceTestCase):
    def test_incluye_todos_los_campos_presentes(self):
        job = Jobs.objects.create(
            company=self.company,
            title="Backend Dev",
            description="desc",
            requirements="Python",
            benefits="Remoto",
            location="Bogota",
            job_type="full_time",
            experience_level="senior",
            is_remote=True,
        )

        text = self.service._generate_job_embedding_text(job)

        self.assertIn("Puesto: Backend Dev", text)
        self.assertIn("Requisitos: Python", text)
        self.assertIn("Beneficios: Remoto", text)
        self.assertIn("Ubicación: Bogota", text)
        self.assertIn("Trabajo remoto disponible", text)
        self.assertIn("Empresa: Empresa Uno", text)


class TestGetPersonalizedJobRecommendations(BaseJobsServiceTestCase):
    def test_retorna_recomendaciones_basicas(self):
        Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )

        result = self.service.get_personalized_job_recommendations(
            user_id="u1", limit=5
        )

        self.assertEqual(result.count(), 1)

    def test_acepta_objeto_user_con_id(self):
        Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )
        fake_user = MagicMock(id="u1")

        result = self.service.get_personalized_job_recommendations(
            user=fake_user, limit=5
        )

        self.assertEqual(result.count(), 1)


class TestGetBasicRecommendations(BaseJobsServiceTestCase):
    def test_combina_populares_y_recientes_sin_duplicados(self):
        for i in range(3):
            Jobs.objects.create(
                company=self.company, title=f"Job {i}", description="desc"
            )

        result = self.service._get_basic_recommendations(None, limit=5)

        self.assertEqual(len(set(result.values_list("id", flat=True))), 3)


class TestGetTrendingJobs(BaseJobsServiceTestCase):
    def test_retorna_jobs_recientes_cuando_hay(self):
        Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )

        result = self.service.get_trending_jobs(limit=5)

        self.assertEqual(len(list(result)), 1)

    def test_maneja_excepcion_con_fallback(self):
        with patch(
            "apps.jobs.domain.services.jobs_service.Jobs.objects.count",
            side_effect=RuntimeError("boom"),
        ):
            result = self.service.get_trending_jobs(limit=5)

        self.assertEqual(list(result), [])


class TestSemanticSearchJobs(BaseJobsServiceTestCase):
    def test_usa_busqueda_textual_si_no_hay_embedding(self):
        Jobs.objects.create(
            company=self.company, title="Backend Dev", description="Python jobs"
        )
        with patch.object(
            self.service, "get_embedding_from_microservice", return_value=None
        ):
            result = self.service.semantic_search_jobs("Backend")

        self.assertEqual(result.count(), 1)

    def test_maneja_excepcion_con_fallback_textual(self):
        Jobs.objects.create(
            company=self.company, title="Backend Dev", description="Python jobs"
        )
        with patch.object(
            self.service,
            "get_embedding_from_microservice",
            side_effect=RuntimeError("boom"),
        ):
            result = self.service.semantic_search_jobs("Backend")

        self.assertEqual(result.count(), 1)


class TestTextSearchJobs(BaseJobsServiceTestCase):
    def test_busca_por_titulo_descripcion_requisitos_o_empresa(self):
        Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )

        result = self.service._text_search_jobs("Backend")

        self.assertEqual(result.count(), 1)

    def test_aplica_filtros_si_se_proporcionan(self):
        Jobs.objects.create(
            company=self.company,
            title="Backend Dev",
            description="desc",
            is_remote=True,
        )
        Jobs.objects.create(
            company=self.company,
            title="Backend Dev 2",
            description="desc",
            is_remote=False,
        )

        result = self.service._text_search_jobs(
            "Backend", filters={"is_remote": True}
        )

        self.assertEqual(result.count(), 1)


class TestApplyFilters(BaseJobsServiceTestCase):
    def test_aplica_todos_los_filtros_disponibles(self):
        job = Jobs.objects.create(
            company=self.company,
            title="Backend Dev",
            description="desc",
            job_type="full_time",
            experience_level="senior",
            salary_min=1000,
            salary_max=2000,
            location="Bogota",
            is_remote=True,
        )
        Jobs.objects.create(
            company=self.company,
            title="Other",
            description="desc",
            job_type="internship",
            experience_level="entry",
            is_remote=False,
        )

        result = self.service._apply_filters(
            Jobs.objects.all(),
            {
                "is_remote": True,
                "job_type": "full_time",
                "experience_level": "senior",
                "salary_min": 500,
                "salary_max": 3000,
                "location": "bogota",
                "company": "Empresa",
            },
        )

        self.assertEqual(list(result), [job])

    def test_job_type_y_experience_level_aceptan_listas(self):
        job = Jobs.objects.create(
            company=self.company,
            title="Backend Dev",
            description="desc",
            job_type="contract",
            experience_level="mid",
        )

        result = self.service._apply_filters(
            Jobs.objects.all(),
            {
                "job_type": ["contract", "freelance"],
                "experience_level": ["mid", "senior"],
            },
        )

        self.assertEqual(list(result), [job])


class TestHandleJobInteraction(BaseJobsServiceTestCase):
    def test_incrementa_view_count(self):
        job = Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )
        user = MagicMock(id="u1")

        self.service.handle_job_interaction(user, job, "view")

        job.refresh_from_db()
        self.assertEqual(job.view_count, 1)

    def test_incrementa_application_count(self):
        job = Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )
        user = MagicMock(id="u1")

        self.service.handle_job_interaction(user, job, "application")

        job.refresh_from_db()
        self.assertEqual(job.application_count, 1)

    def test_no_lanza_si_falla_el_registro_de_vectores_de_usuario(self):
        job = Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )
        user = MagicMock(id="u1")

        with patch(
            "apps.jobs.domain.services.jobs_service.user_vector_service"
        ) as mock_vector_service:
            mock_vector_service.update_user_vectors_on_interaction.side_effect = (
                RuntimeError("boom")
            )
            # No debe propagar la excepcion.
            self.service.handle_job_interaction(user, job, "view")
