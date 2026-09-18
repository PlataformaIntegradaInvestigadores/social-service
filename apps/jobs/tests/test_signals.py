"""Unitarias de los signals post_save/post_delete de Jobs: generacion
automatica de embedding al crear/actualizar un job sin embedding."""

from unittest.mock import patch

from django.test import TestCase

from apps.jobs.domain.entities.company import Company
from apps.jobs.domain.entities.jobs import Jobs

UPDATE_JOB_EMBEDDING = (
    "apps.jobs.infrastructure.signals.vector_service.update_job_embedding"
)


class TestHandleJobSave(TestCase):
    def setUp(self):
        self.company = Company.objects.create_user(
            username="empresa@example.com",
            password="secret123",
            company_name="Empresa Uno",
        )

    def test_genera_embedding_al_crear_job_nuevo(self):
        with patch(UPDATE_JOB_EMBEDDING, return_value=True) as mock_update:
            Jobs.objects.create(
                company=self.company, title="Backend Dev", description="desc"
            )

        mock_update.assert_called_once()

    def test_no_lanza_si_falla_generacion_de_embedding(self):
        with patch(UPDATE_JOB_EMBEDDING, side_effect=RuntimeError("boom")):
            # No debe propagar la excepcion, el signal la captura y loguea.
            Jobs.objects.create(
                company=self.company, title="Backend Dev", description="desc"
            )

    def test_job_actualizado_sin_embedding_regenera(self):
        with patch(UPDATE_JOB_EMBEDDING, return_value=True) as mock_update:
            job = Jobs.objects.create(
                company=self.company, title="Backend Dev", description="desc"
            )
            mock_update.reset_mock()

            job.title = "Backend Dev Senior"
            job.save()

        mock_update.assert_called_once()

    def test_job_actualizado_con_embedding_no_regenera(self):
        with patch(UPDATE_JOB_EMBEDDING, return_value=True) as mock_update:
            job = Jobs.objects.create(
                company=self.company, title="Backend Dev", description="desc"
            )
            job.embedding = [0.1] * 768
            job.save()
            mock_update.reset_mock()

            job.title = "Backend Dev Senior"
            job.save()

        mock_update.assert_not_called()


class TestHandleJobDelete(TestCase):
    def setUp(self):
        self.company = Company.objects.create_user(
            username="empresa@example.com",
            password="secret123",
            company_name="Empresa Uno",
        )

    def test_eliminar_job_no_lanza_excepcion(self):
        with patch(UPDATE_JOB_EMBEDDING, return_value=True):
            job = Jobs.objects.create(
                company=self.company, title="Backend Dev", description="desc"
            )

        job.delete()

        self.assertFalse(Jobs.objects.filter(id=job.id).exists())
