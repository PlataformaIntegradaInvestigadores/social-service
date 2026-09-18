import pytest
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.jobs.domain.entities.company import Company
from apps.jobs.domain.entities.jobs import Jobs


@pytest.mark.integration
class JobsListIntegrationTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.company = Company.objects.create_user(
            username="empresa1@example.com",
            password="testpass123",
            company_name="Empresa Uno",
        )
        self.other_company = Company.objects.create_user(
            username="empresa2@example.com",
            password="testpass123",
            company_name="Empresa Dos",
        )
        Jobs.objects.create(
            company=self.company,
            title="Backend Developer",
            description="Vacante de la Empresa Uno",
        )
        Jobs.objects.create(
            company=self.other_company,
            title="Frontend Developer",
            description="Vacante de la Empresa Dos",
        )

    def test_company_only_sees_its_own_jobs(self):
        self.client.force_authenticate(user=self.company)

        response = self.client.get("/api/v1/jobs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [job["title"] for job in response.data]
        self.assertEqual(titles, ["Backend Developer"])

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get("/api/v1/jobs/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
