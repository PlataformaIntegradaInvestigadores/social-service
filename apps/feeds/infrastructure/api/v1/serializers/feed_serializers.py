from rest_framework import serializers

from .feed_post_serializers import FeedPostSerializer


class FeedSerializer(serializers.Serializer):
    """Serializer for feed responses"""

    posts = FeedPostSerializer(many=True, read_only=True)
    has_next = serializers.BooleanField(read_only=True)
    next_cursor = serializers.CharField(read_only=True, allow_null=True)
    total_count = serializers.IntegerField(read_only=True)


class FeedRequestSerializer(serializers.Serializer):
    """Serializer for feed requests"""

    feed_type = serializers.ChoiceField(
        choices=["personalized", "trending", "latest"],
        default="personalized",
        required=False,
    )
    type = serializers.ChoiceField(
        choices=["personalized", "trending", "latest"], required=False
    )
    limit = serializers.IntegerField(min_value=1, max_value=50, default=20)
    cursor = serializers.CharField(required=False, allow_null=True)
    author = serializers.CharField(required=False, allow_null=True)

    def validate(self, attrs):
        """Custom validation to handle both type and feed_type"""
        feed_type = attrs.get("feed_type")
        type_param = attrs.get("type")

        # Si se proporciona 'type', usarlo como feed_type
        if type_param:
            attrs["feed_type"] = type_param
        elif not feed_type:
            attrs["feed_type"] = "personalized"  # default

        # Limpiar el campo 'type' ya que no lo necesitamos
        attrs.pop("type", None)

        return attrs

    def validate_cursor(self, value):
        """Validate cursor format"""
        if value is None:
            return value

        # Basic cursor validation - should be a timestamp or encoded value
        if not isinstance(value, str) or len(value) == 0:
            raise serializers.ValidationError("Invalid cursor format")

        return value


class UserInteractionSerializer(serializers.Serializer):
    """Serializer for user interactions (view, share, etc.)"""

    post_id = serializers.UUIDField()
    interaction_type = serializers.ChoiceField(
        choices=["view", "share", "click", "save"]
    )
    metadata = serializers.JSONField(required=False, default=dict)

    def validate_post_id(self, value):
        """Validate post exists"""
        from apps.feeds.domain.entities.feed_post import FeedPost

        try:
            FeedPost.objects.get(id=value)
        except FeedPost.DoesNotExist:
            raise serializers.ValidationError("Post does not exist") from None

        return value

    def validate_metadata(self, value):
        """Validate interaction metadata"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Metadata must be a dictionary")

        # Limit metadata size
        if len(str(value)) > 1000:
            raise serializers.ValidationError("Metadata too large")

        return value


class FeedFilterSerializer(serializers.Serializer):
    """Serializer for feed filtering options"""

    tags = serializers.ListField(
        child=serializers.CharField(max_length=50), required=False, allow_empty=True
    )
    author_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, allow_empty=True
    )
    date_from = serializers.DateTimeField(required=False)
    date_to = serializers.DateTimeField(required=False)
    has_files = serializers.BooleanField(required=False)
    file_types = serializers.ListField(
        child=serializers.CharField(max_length=20), required=False, allow_empty=True
    )

    def validate_tags(self, value):
        """Validate tags format"""
        if not value:
            return value

        if len(value) > 10:
            raise serializers.ValidationError("Cannot filter by more than 10 tags")

        for tag in value:
            if not tag.strip():
                raise serializers.ValidationError("Tags cannot be empty")

        return [tag.strip().lower() for tag in value]

    def validate(self, attrs):
        """Cross-field validation"""
        date_from = attrs.get("date_from")
        date_to = attrs.get("date_to")

        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError("date_from cannot be later than date_to")

        return attrs
