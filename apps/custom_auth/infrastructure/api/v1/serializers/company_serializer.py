from rest_framework import serializers

from apps.jobs.domain.entities.company import Company


class RelativeImageField(serializers.ImageField):
    """Return a gateway-safe path instead of an origin inferred by Django."""

    def to_representation(self, value):
        if not value:
            return None
        try:
            return value.url
        except ValueError:
            return None


class CompanyListSerializer(serializers.ModelSerializer):
    industry_display = serializers.CharField(
        source="get_industry_display_name", read_only=True
    )

    class Meta:
        model = Company
        fields = [
            "id",
            "company_name",
            "username",
            "industry",
            "industry_display",
            "is_verified",
        ]


class CompanyProfileSerializer(serializers.ModelSerializer):
    """Serializador para mostrar el perfil completo de la empresa."""

    industry_display = serializers.CharField(
        source="get_industry_display_name", read_only=True
    )
    logo = RelativeImageField(required=False, allow_null=True)

    class Meta:
        model = Company
        fields = [
            "id",
            "company_name",
            "username",
            "industry",
            "industry_display",
            "description",
            "website",
            "phone",
            "address",
            "logo",
            "founded_year",
            "employee_count",
            "is_verified",
            "date_joined",
        ]
        read_only_fields = ["id", "username", "is_verified", "date_joined"]
