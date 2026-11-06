"""CV download and what a company may change on an application.

The CV is personal data: only the company that owns the job and the applicant get
it, through an authenticated view, never from /media/. A company can move the status
(and add notes) but cannot rewrite what the applicant submitted.
"""

import shutil
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.custom_auth.identity_principal import IdentityPrincipal
from apps.jobs.domain.entities.company import Company
from apps.jobs.domain.entities.jobs import Jobs
from apps.jobs.domain.entities.postulants import Postulants

SIGNAL_UPDATE_EMBEDDING = (
    "apps.jobs.infrastructure.signals.job_embedding_service.update_job_embedding"
)
PDF = b"%PDF-1.4\n%%EOF\n"


class BaseCase(APITestCase):
    def setUp(self):
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=media)
        override.enable()
        self.addCleanup(override.disable)

        patcher = patch(SIGNAL_UPDATE_EMBEDDING, return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.client = APIClient()
        self.company = Company.objects.create_user(
            username="a@example.com", password="x12345678", company_name="A"
        )
        self.other_company = Company.objects.create_user(
            username="b@example.com", password="x12345678", company_name="B"
        )
        self.user = IdentityPrincipal(id="u1", username="ana")
        self.other_user = IdentityPrincipal(id="u2", username="beto")
        self.job = Jobs.objects.create(
            company=self.company, title="Dev", description="d"
        )
        self.other_job = Jobs.objects.create(
            company=self.other_company, title="Otro", description="d"
        )
        self.application = Postulants.objects.create(
            user_identity_id=self.user.id,
            job=self.job,
            cover_letter="Mi carta",
            resume_file=SimpleUploadedFile(
                "cv.pdf", PDF, content_type="application/pdf"
            ),
        )

    def url(self, application=None):
        return f"/api/v1/applications/{(application or self.application).id}/resume/"


class TestResumeDownload(BaseCase):
    def test_the_company_that_owns_the_job_gets_the_cv(self):
        self.client.force_authenticate(user=self.company)

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(b"".join(response.streaming_content), PDF)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_the_applicant_gets_their_own_cv(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_another_company_cannot_get_it(self):
        self.client.force_authenticate(user=self.other_company)

        self.assertEqual(self.client.get(self.url()).status_code, 403)

    def test_another_applicant_cannot_get_it(self):
        self.client.force_authenticate(user=self.other_user)

        self.assertEqual(self.client.get(self.url()).status_code, 403)

    def test_anonymous_requests_are_rejected(self):
        self.assertIn(self.client.get(self.url()).status_code, (401, 403))

    def test_unknown_application_is_404(self):
        self.client.force_authenticate(user=self.company)

        response = self.client.get("/api/v1/applications/99999/resume/")

        self.assertEqual(response.status_code, 404)

    def test_application_without_cv_is_404(self):
        bare = Postulants.objects.create(user_identity_id="u9", job=self.job)
        self.client.force_authenticate(user=self.company)

        self.assertEqual(self.client.get(self.url(bare)).status_code, 404)

    def test_missing_file_on_disk_is_404(self):
        self.application.resume_file.storage.delete(self.application.resume_file.name)
        self.client.force_authenticate(user=self.company)

        self.assertEqual(self.client.get(self.url()).status_code, 404)

    def test_resumes_are_not_served_from_media(self):
        name = self.application.resume_file.name
        self.client.force_authenticate(user=self.company)

        self.assertEqual(self.client.get(f"/media/{name}").status_code, 404)


class TestCompanyCanOnlyChangeStatusAndNotes(BaseCase):
    def put(self, data, user=None):
        self.client.force_authenticate(user=user or self.company)
        return self.client.put(
            f"/api/v1/applications/{self.application.id}/", data, format="json"
        )

    def test_status_and_notes_are_updated(self):
        response = self.put({"status": "reviewing", "notes": "Buen perfil"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "reviewing")
        self.assertEqual(self.application.notes, "Buen perfil")

    def test_the_cover_letter_cannot_be_rewritten(self):
        self.put({"status": "reviewing", "cover_letter": "REESCRITA"})

        self.application.refresh_from_db()
        self.assertEqual(self.application.cover_letter, "Mi carta")
        self.assertEqual(self.application.status, "reviewing")

    def test_the_application_cannot_be_moved_to_another_job(self):
        self.put({"status": "reviewing", "job": self.other_job.id})

        self.application.refresh_from_db()
        self.assertEqual(self.application.job_id, self.job.id)

    def test_the_applicant_cannot_be_changed(self):
        self.put({"status": "reviewing", "user_identity_id": "otra-persona"})

        self.application.refresh_from_db()
        self.assertEqual(self.application.user_identity_id, self.user.id)

    def test_an_unknown_status_is_rejected(self):
        response = self.put({"status": "ESTO-NO-ES-UN-ESTADO"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("allowed", response.data)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "pending")

    def test_a_company_cannot_mark_an_application_as_withdrawn(self):
        response = self.put({"status": "withdrawn"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_another_company_cannot_change_it(self):
        response = self.put({"status": "accepted"}, user=self.other_company)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_the_applicant_edits_their_cover_letter_but_not_the_status(self):
        response = self.put(
            {"cover_letter": "Nueva carta", "status": "accepted"}, user=self.user
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.application.refresh_from_db()
        self.assertEqual(self.application.cover_letter, "Nueva carta")
        self.assertEqual(self.application.status, "pending")


class TestBulkStatusUpdate(BaseCase):
    def put(self, data):
        self.client.force_authenticate(user=self.company)
        return self.client.put(
            f"/api/v1/jobs/{self.job.id}/applications/", data, format="json"
        )

    def test_a_valid_status_is_saved(self):
        response = self.put(
            {"application_id": self.application.id, "status": "interviewed"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "interviewed")

    def test_an_unknown_status_is_rejected_and_nothing_is_saved(self):
        response = self.put(
            {"application_id": self.application.id, "status": "inventado"}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("allowed", response.data)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "pending")

    def test_withdrawn_is_not_assignable_by_a_company(self):
        response = self.put(
            {"application_id": self.application.id, "status": "withdrawn"}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
