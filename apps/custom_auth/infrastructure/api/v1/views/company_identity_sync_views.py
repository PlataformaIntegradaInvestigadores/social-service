import secrets

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import transaction
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.jobs.domain.entities.company import Company


class HasProfileSyncToken(permissions.BasePermission):
    def has_permission(self, request, view):
        configured_token = settings.PROFILE_SYNC_INTERNAL_TOKEN
        supplied_token = request.headers.get("X-Profile-Sync-Token", "")
        return bool(configured_token and supplied_token) and secrets.compare_digest(
            configured_token,
            supplied_token,
        )


class CompanyIdentitySyncView(APIView):
    """Internal anti-corruption endpoint between Identity and the company profile store."""

    authentication_classes = []
    permission_classes = [HasProfileSyncToken]

    def get(self, request):
        companies = Company.objects.all().values(
            "id",
            "username",
            "password",
            "company_name",
            "is_active",
            "is_staff",
        )
        return Response({"companies": list(companies)}, status=status.HTTP_200_OK)

    @transaction.atomic
    def post(self, request):
        company_id = str(request.data.get("id", "")).strip()
        username = str(request.data.get("username", "")).strip().lower()
        company_name = str(request.data.get("company_name", "")).strip()
        if not company_id or not username or not company_name:
            return Response(
                {"detail": "id, username and company_name are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email_conflict = Company.objects.filter(username__iexact=username).exclude(id=company_id).exists()
        if email_conflict:
            return Response(
                {"detail": "A company profile with this email already exists."},
                status=status.HTTP_409_CONFLICT,
            )

        defaults = {
            "username": username,
            "company_name": company_name,
            "industry": request.data.get("industry") or "other",
            "description": request.data.get("description") or None,
            "website": request.data.get("website") or None,
            "phone": request.data.get("phone") or None,
            "address": request.data.get("address") or None,
            "founded_year": request.data.get("founded_year") or None,
            "employee_count": request.data.get("employee_count") or None,
        }
        company, created = Company.objects.update_or_create(id=company_id, defaults=defaults)
        if created:
            company.password = make_password(None)
            company.save(update_fields=["password"])
        return Response(
            {"company_id": company.id, "created": created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
