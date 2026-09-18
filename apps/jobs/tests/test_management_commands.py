"""Unitarias del management command update_job_embeddings y de la tarea
periodica de Celery update_missing_job_embeddings que lo invoca."""

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.jobs.domain.entities.company import Company
from apps.jobs.domain.entities.jobs import Jobs
from apps.jobs.tasks import update_missing_job_embeddings

UPDATE_JOB_EMBEDDING = (
    "apps.jobs.infrastructure.signals.vector_service.update_job_embedding"
)
VECTOR_SERVICE_UPDATE = (
    "apps.jobs.management.commands.update_job_embeddings.vector_service"
    ".update_job_embedding"
)


class BaseCommandTestCase(TestCase):
    def setUp(self):
        patcher = patch(UPDATE_JOB_EMBEDDING, return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.company = Company.objects.create_user(
            username="empresa@example.com",
            password="secret123",
            company_name="Empresa Uno",
        )


class TestUpdateJobEmbeddingsCommand(BaseCommandTestCase):
    def test_sin_jobs_para_procesar_informa_advertencia(self):
        out = StringIO()

        call_command("update_job_embeddings", stdout=out)

        self.assertIn("No hay jobs para procesar", out.getvalue())

    def test_procesa_jobs_sin_embedding(self):
        Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )
        out = StringIO()

        with patch(VECTOR_SERVICE_UPDATE, return_value=True) as mock_update:
            call_command("update_job_embeddings", stdout=out)

        mock_update.assert_called_once()
        self.assertIn("1 embeddings actualizados", out.getvalue())

    def test_force_reprocesa_jobs_con_embedding(self):
        job = Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )
        job.embedding = [0.1] * 768
        job.save(update_fields=["embedding"])
        out = StringIO()

        with patch(VECTOR_SERVICE_UPDATE, return_value=True) as mock_update:
            call_command("update_job_embeddings", "--force", stdout=out)

        mock_update.assert_called_once()

    def test_job_id_filtra_un_solo_job(self):
        job1 = Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )
        Jobs.objects.create(
            company=self.company, title="Frontend Dev", description="desc"
        )
        out = StringIO()

        with patch(VECTOR_SERVICE_UPDATE, return_value=True) as mock_update:
            call_command("update_job_embeddings", "--job-id", job1.id, stdout=out)

        mock_update.assert_called_once_with(job1)

    def test_errores_se_cuentan_y_reportan(self):
        Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )
        out = StringIO()

        with patch(VECTOR_SERVICE_UPDATE, return_value=False):
            call_command("update_job_embeddings", stdout=out)

        self.assertIn("1 jobs tuvieron errores", out.getvalue())

    def test_excepcion_individual_no_detiene_el_lote(self):
        Jobs.objects.create(
            company=self.company, title="Backend Dev", description="desc"
        )
        out = StringIO()

        with patch(VECTOR_SERVICE_UPDATE, side_effect=RuntimeError("boom")):
            call_command("update_job_embeddings", stdout=out)

        self.assertIn("Excepción en job", out.getvalue())


class TestUpdateMissingJobEmbeddingsTask(BaseCommandTestCase):
    def test_invoca_el_management_command(self):
        with patch(
            "apps.jobs.tasks.call_command"
        ) as mock_call_command:
            update_missing_job_embeddings()

        mock_call_command.assert_called_once_with(
            "update_job_embeddings", batch_size=50
        )

    def test_no_lanza_si_el_comando_falla(self):
        with patch(
            "apps.jobs.tasks.call_command", side_effect=RuntimeError("boom")
        ):
            # No debe propagar la excepcion, la tarea la captura y loguea.
            update_missing_job_embeddings()
