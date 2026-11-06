"""JobEmbeddingService: the text a job is embedded from, and storing the vector."""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.jobs.domain.entities.company import Company
from apps.jobs.domain.entities.jobs import Jobs
from apps.jobs.domain.services.job_embedding_service import (
    JobEmbeddingService,
    job_embedding_text,
)

SIGNAL_UPDATE_EMBEDDING = (
    "apps.jobs.infrastructure.signals.job_embedding_service.update_job_embedding"
)


class BaseJobEmbeddingTestCase(TestCase):
    def setUp(self):
        patcher = patch(SIGNAL_UPDATE_EMBEDDING, return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.company = Company.objects.create_user(
            username="empresa@example.com",
            password="secret123",
            company_name="Empresa Uno",
        )
        self.embeddings = MagicMock()
        self.service = JobEmbeddingService(embeddings=self.embeddings)

    def job(self, **fields):
        data = {"company": self.company, "title": "Backend Dev", "description": "desc"}
        data.update(fields)
        return Jobs.objects.create(**data)


class TestJobEmbeddingText(BaseJobEmbeddingTestCase):
    def test_includes_only_the_fields_that_are_filled(self):
        text = job_embedding_text(
            self.job(requirements="Python", location="Quito", job_type="full_time")
        )

        self.assertIn("Puesto: Backend Dev", text)
        self.assertIn("Descripción: desc", text)
        self.assertIn("Requisitos: Python", text)
        self.assertIn("Ubicación: Quito", text)
        self.assertIn("Tipo de trabajo: full_time", text)

    def test_parts_are_joined_with_periods(self):
        text = job_embedding_text(self.job(requirements="", location=""))

        self.assertTrue(text.startswith("Puesto: Backend Dev. Descripción: desc"))
        self.assertNotIn("Requisitos", text)
        self.assertNotIn("Ubicación", text)


class TestUpdateJobEmbedding(BaseJobEmbeddingTestCase):
    def test_stores_the_vector_when_the_service_answers(self):
        self.embeddings.embed.return_value = [0.1] * 768
        job = self.job()

        result = self.service.update_job_embedding(job)

        self.assertTrue(result)
        job.refresh_from_db()
        self.assertIsNotNone(job.embedding)
        self.embeddings.embed.assert_called_once_with(job_embedding_text(job))

    def test_returns_false_and_stores_nothing_without_a_vector(self):
        self.embeddings.embed.return_value = None
        job = self.job()

        result = self.service.update_job_embedding(job)

        self.assertFalse(result)
        job.refresh_from_db()
        self.assertIsNone(job.embedding)
