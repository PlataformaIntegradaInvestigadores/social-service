from rest_framework import serializers

from apps.jobs.domain.entities.company import Company
from apps.jobs.domain.entities.jobs import Jobs
from apps.jobs.domain.entities.postulants import Postulants


class CompanyBasicSerializer(serializers.ModelSerializer):
    """Serializer básico para mostrar información de la compañía en los jobs"""

    class Meta:
        model = Company
        fields = ["id", "company_name", "logo", "industry", "website", "address"]


class JobsSerializer(serializers.ModelSerializer):
    company_info = CompanyBasicSerializer(source="company", read_only=True)
    experience_display = serializers.CharField(
        source="get_experience_display_name", read_only=True
    )
    job_type_display = serializers.CharField(
        source="get_job_type_display_name", read_only=True
    )
    applications_count = serializers.SerializerMethodField()
    has_applied = serializers.SerializerMethodField()
    user_application = serializers.SerializerMethodField()

    class Meta:
        model = Jobs
        fields = [
            "id",
            "title",
            "description",
            "requirements",
            "benefits",
            "location",
            "job_type",
            "job_type_display",
            "experience_level",
            "experience_display",
            "salary_min",
            "salary_max",
            "is_remote",
            "application_deadline",
            "created_at",
            "updated_at",
            "company",
            "company_info",
            "applications_count",
            "has_applied",
            "user_application",
        ]
        extra_kwargs = {
            "company": {
                "write_only": True,
                "required": False,
            },  # Solo para escritura, no se muestra en respuesta, no requerido
        }

    def get_applications_count(self, obj):
        """Retorna el número de postulaciones para este trabajo"""
        return obj.applications.count()

    def get_has_applied(self, obj):
        """Indica si el usuario actual ya postuló a este trabajo"""
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            # Solo verificar para usuarios regulares, no para compañías
            if not hasattr(request.user, "company_name"):
                return Postulants.objects.filter(
                    user_identity_id=str(request.user.id), job=obj
                ).exists()
        return False

    def get_user_application(self, obj):
        """Retorna información de la postulación del usuario actual si existe"""
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            # Solo para usuarios regulares, no para compañías
            if not hasattr(request.user, "company_name"):
                try:
                    application = Postulants.objects.get(
                        user_identity_id=str(request.user.id), job=obj
                    )
                    return {
                        "id": application.id,
                        "status": application.status,
                        "status_display": application.get_status_display_name(),
                        "applied_at": application.applied_at,
                    }
                except Postulants.DoesNotExist:
                    pass
        return None

    def validate(self, data):
        """Validaciones personalizadas"""
        salary_min = data.get("salary_min")
        salary_max = data.get("salary_max")

        if salary_min and salary_max and salary_min > salary_max:
            raise serializers.ValidationError(
                "El salario mínimo no puede ser mayor al salario máximo"
            )

        return data


class JobsListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listados de jobs"""

    company_info = CompanyBasicSerializer(source="company", read_only=True)
    job_type_display = serializers.CharField(
        source="get_job_type_display_name", read_only=True
    )
    has_applied = serializers.SerializerMethodField()

    class Meta:
        model = Jobs
        fields = [
            "id",
            "title",
            "location",
            "job_type",
            "job_type_display",
            "experience_level",
            "salary_min",
            "salary_max",
            "is_remote",
            "created_at",
            "company_info",
            "has_applied",
        ]

    def get_has_applied(self, obj):
        """Indica si el usuario actual ya postuló a este trabajo"""
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            # Solo verificar para usuarios regulares, no para compañías
            if not hasattr(request.user, "company_name"):
                return Postulants.objects.filter(
                    user_identity_id=str(request.user.id), job=obj
                ).exists()
        return False


class JobsCompanySerializer(serializers.ModelSerializer):
    """Serializer específico para empresas - incluye información de postulaciones"""

    company_info = CompanyBasicSerializer(source="company", read_only=True)
    experience_display = serializers.CharField(
        source="get_experience_display_name", read_only=True
    )
    job_type_display = serializers.CharField(
        source="get_job_type_display_name", read_only=True
    )
    applications_count = serializers.SerializerMethodField()
    recent_applications = serializers.SerializerMethodField()

    class Meta:
        model = Jobs
        fields = [
            "id",
            "title",
            "description",
            "requirements",
            "benefits",
            "location",
            "job_type",
            "job_type_display",
            "experience_level",
            "experience_display",
            "salary_min",
            "salary_max",
            "is_remote",
            "application_deadline",
            "created_at",
            "updated_at",
            "company_info",
            "applications_count",
            "recent_applications",
        ]

    def get_applications_count(self, obj):
        """Retorna el número de postulaciones para este trabajo"""
        return obj.applications.count()

    def get_recent_applications(self, obj):
        """Retorna las últimas 5 postulaciones para este trabajo"""
        from apps.jobs.infrastructure.api.v1.serializers.postulants_serializer import (
            PostulantsListSerializer,
        )

        recent_apps = obj.applications.order_by("-applied_at")[:5]
        return PostulantsListSerializer(recent_apps, many=True).data
