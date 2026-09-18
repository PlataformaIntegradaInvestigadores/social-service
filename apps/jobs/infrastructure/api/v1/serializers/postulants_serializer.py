from rest_framework import serializers

from apps.jobs.domain.entities.jobs import Jobs
from apps.jobs.domain.entities.postulants import Postulants


class UserBasicSerializer(serializers.Serializer):
    """Serializer basico para mostrar informacion del usuario externo."""

    id = serializers.CharField(read_only=True)
    first_name = serializers.CharField(read_only=True, allow_blank=True)
    last_name = serializers.CharField(read_only=True, allow_blank=True)
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    username = serializers.CharField(read_only=True, allow_blank=True)
    profile_picture = serializers.CharField(read_only=True, allow_blank=True)


class JobBasicSerializer(serializers.ModelSerializer):
    """Serializer basico para mostrar informacion del trabajo."""

    company_name = serializers.CharField(source="company.company_name", read_only=True)
    company_logo = serializers.CharField(source="company.logo", read_only=True)

    class Meta:
        model = Jobs
        fields = [
            "id",
            "title",
            "company_name",
            "company_logo",
            "location",
            "job_type",
            "experience_level",
            "created_at",
            "application_deadline",
        ]


class PostulantsSerializer(serializers.ModelSerializer):
    user_info = UserBasicSerializer(source="user", read_only=True)
    job_info = JobBasicSerializer(source="job", read_only=True)
    status_display = serializers.CharField(
        source="get_status_display_name", read_only=True
    )

    class Meta:
        model = Postulants
        fields = [
            "id",
            "user_identity_id",
            "job",
            "cover_letter",
            "resume_file",
            "status",
            "status_display",
            "notes",
            "applied_at",
            "updated_at",
            "user_info",
            "job_info",
        ]
        extra_kwargs = {
            "user_identity_id": {"write_only": True, "required": False},
            "job": {"write_only": True, "required": False},
            "notes": {"read_only": True},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.context.get("request") and self.context["request"].method == "POST":
            self.fields.pop("user_identity_id", None)
            self.fields.pop("job", None)


class PostulantsListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listados de postulaciones."""

    user_info = UserBasicSerializer(source="user", read_only=True)
    job_info = JobBasicSerializer(source="job", read_only=True)
    status_display = serializers.CharField(
        source="get_status_display_name", read_only=True
    )

    class Meta:
        model = Postulants
        fields = [
            "id",
            "status",
            "status_display",
            "applied_at",
            "user_info",
            "job_info",
        ]


class PostulantsUpdateSerializer(serializers.ModelSerializer):
    """Serializer para actualizacion de postulaciones por parte de las companias."""

    class Meta:
        model = Postulants
        fields = ["status", "notes"]

    def validate_status(self, value):
        valid_statuses = [choice[0] for choice in Postulants.STATUS_CHOICES]
        if value not in valid_statuses:
            raise serializers.ValidationError(
                f"Estado invalido. Opciones validas: {valid_statuses}"
            )
        return value
