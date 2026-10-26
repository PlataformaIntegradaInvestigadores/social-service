from rest_framework import serializers

from apps.feeds.domain.services import moderation_service as moderation


class ModerationRepresentationMixin:
    """Añade ``moderation`` y oculta el texto bloqueado a quien no modera.

    Cada serializer declara ``moderation = SerializerMethodField()`` (DRF solo
    recoge campos declarados en clases Serializer, no en mixins simples)."""

    def _viewer(self):
        request = self.context.get("request")
        return getattr(request, "user", None) if request else None

    def get_moderation(self, obj):
        return moderation.moderation_payload(obj, self._viewer())

    def to_representation(self, instance):
        data = super().to_representation(instance)
        return moderation.redact_if_blocked(instance, data, self._viewer())


class ReportSerializer(serializers.Serializer):
    reason = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=255
    )


class ReviewQueueQuerySerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=["pending", "resolved", "all"], required=False, default="pending"
    )
    reason = serializers.ChoiceField(
        choices=["hidden_by_model", "reported", "deferred"], required=False
    )
    content_type = serializers.ChoiceField(choices=["post", "comment"], required=False)
    limit = serializers.IntegerField(
        required=False, min_value=1, max_value=100, default=20
    )
    offset = serializers.IntegerField(required=False, min_value=0, default=0)


class DecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["approve", "keep_hidden", "block"])
    notes = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=2000
    )
