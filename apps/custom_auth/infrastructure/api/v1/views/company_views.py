from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser

from apps.jobs.domain.entities.company import Company

from ..serializers.company_serializer import (
    CompanyListSerializer,
    CompanyProfileSerializer,
)


class CompanyListView(generics.ListAPIView):
    """Lista todas las empresas (para administradores o uso interno)."""

    serializer_class = CompanyListSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Company.objects.filter(is_active=True)

    def get_queryset(self):
        """Filtra las empresas activas y verificadas."""
        queryset = super().get_queryset()
        # Opcionalmente, solo mostrar empresas verificadas
        if self.request.query_params.get("verified_only", "").lower() == "true":
            queryset = queryset.filter(is_verified=True)
        return queryset


class CompanyUpdateView(generics.UpdateAPIView):
    """Permite a una empresa actualizar su perfil."""

    queryset = Company.objects.all()
    serializer_class = CompanyProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def get_object(self):
        """Asegura que solo la empresa puede editar su propio perfil."""
        obj = super().get_object()
        if obj.id != self.request.user.id:
            raise PermissionDenied("No tienes permiso para editar esta empresa.")
        return obj

    def update(self, request, *args, **kwargs):
        """Actualiza el perfil de la empresa."""
        kwargs["partial"] = True
        return super().update(request, *args, **kwargs)


class CompanyDetailView(generics.RetrieveAPIView):
    """Obtiene los detalles de una empresa específica."""

    queryset = Company.objects.filter(is_active=True)
    serializer_class = CompanyProfileSerializer
    permission_classes = [permissions.IsAuthenticated]


class CompanyProfileView(generics.RetrieveAPIView):
    """Obtiene el perfil de la empresa autenticada."""

    serializer_class = CompanyProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        """Retorna la empresa autenticada."""
        return self.request.user
