from django.test import SimpleTestCase, override_settings
from django.urls import resolve
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.custom_auth.infrastructure.api.v1.serializers.company_serializer import (
    CompanyProfileSerializer,
)
from apps.custom_auth.infrastructure.api.v1.views.retired_legacy_identity_views import (
    RetiredLegacyIdentityRouteView,
)
from apps.jobs.domain.entities.company import Company


class RetiredLegacyIdentityRoutesTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    def test_researcher_auth_profile_and_group_routes_are_retired(self):
        retired_routes = [
            ("post", "/api/token/"),
            ("post", "/api/token/refresh/"),
            ("post", "/api/register/"),
            ("get", "/api/users/"),
            ("patch", "/api/users/user-1/update/"),
            ("get", "/api/profile-information/"),
            ("put", "/api/profile-information/user-1/"),
            ("get", "/api/groups/"),
            ("delete", "/api/test/user/groups/group-1/delete/"),
            ("post", "/api/test/user/groups/group-1/leave/"),
        ]

        for method, path in retired_routes:
            with self.subTest(path=path, method=method):
                response = getattr(self.client, method)(path, {}, format="json")
                self.assertEqual(response.status_code, status.HTTP_410_GONE)
                self.assertEqual(
                    response.data["canonical_service"], "profile_identity_backend"
                )

    def test_magic_link_legacy_auth_is_retired(self):
        response = self.client.get("/auth/magic-link/")

        self.assertEqual(response.status_code, status.HTTP_410_GONE)
        self.assertEqual(response.data["canonical_service"], "profile_identity_backend")


class CompanyAuthenticationRoutesAreRetiredFromSocialTests(SimpleTestCase):
    def test_company_registration_and_login_are_owned_by_identity(self):
        for path in ["/api/companies/register/", "/api/companies/token/"]:
            with self.subTest(path=path):
                resolved = resolve(path)
                self.assertIs(resolved.func.view_class, RetiredLegacyIdentityRouteView)


@override_settings(PROFILE_SYNC_INTERNAL_TOKEN="test-profile-sync-token")
class CompanyIdentitySyncTests(APITestCase):
    endpoint = "/internal/profile-sync/company-identities/"

    def test_internal_endpoint_rejects_missing_service_token(self):
        response = self.client.get(self.endpoint)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_identity_can_provision_profile_without_a_login_password(self):
        response = self.client.post(
            self.endpoint,
            {
                "id": "company01",
                "username": "company@example.com",
                "company_name": "Centinela Labs",
                "industry": "technology",
            },
            format="json",
            HTTP_X_PROFILE_SYNC_TOKEN="test-profile-sync-token",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        company = Company.objects.get(id="company01")
        self.assertFalse(company.has_usable_password())
        self.assertEqual(company.company_name, "Centinela Labs")

    def test_company_logo_uses_gateway_relative_media_url(self):
        company = Company.objects.create(
            id="company02",
            username="logo@example.com",
            company_name="Logo Company",
            password="!",
            logo="company_logos/example.jpg",
        )

        data = CompanyProfileSerializer(company).data

        self.assertEqual(data["logo"], "/media/company_logos/example.jpg")
