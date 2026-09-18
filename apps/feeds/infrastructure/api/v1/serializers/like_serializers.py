from rest_framework import serializers

from apps.feeds.domain.entities.like import Like


class LikeSerializer(serializers.ModelSerializer):
    """Serializer for likes"""

    user = serializers.StringRelatedField(read_only=True)
    content_object = serializers.SerializerMethodField()

    class Meta:
        model = Like
        fields = [
            "id",
            "user",
            "content_type",
            "object_id",
            "content_object",
            "created_at",
        ]
        read_only_fields = ["id", "user", "content_object", "created_at"]

    def get_content_object(self, obj):
        """Get string representation of liked object"""
        content_obj = obj.content_object
        if hasattr(content_obj, "content"):
            # For posts and comments
            content = content_obj.content[:100]
            if len(content_obj.content) > 100:
                content += "..."
            return f"{content_obj.__class__.__name__}: {content}"
        return str(content_obj)


class LikeToggleSerializer(serializers.Serializer):
    """Serializer for toggling likes"""

    content_type = serializers.CharField()
    object_id = serializers.UUIDField()

    def validate_content_type(self, value):
        """Validate content type"""
        from django.contrib.contenttypes.models import ContentType

        valid_types = ["feedpost", "comment"]
        if value.lower() not in valid_types:
            raise serializers.ValidationError(
                f"Content type must be one of: {', '.join(valid_types)}"
            )

        try:
            if value.lower() == "feedpost":
                from apps.feeds.domain.entities.feed_post import FeedPost

                ContentType.objects.get_for_model(FeedPost)
            elif value.lower() == "comment":
                from apps.feeds.domain.entities.comment import Comment

                ContentType.objects.get_for_model(Comment)
        except Exception:
            raise serializers.ValidationError("Invalid content type") from None

        return value.lower()

    def validate_object_id(self, value):
        """Validate object ID"""
        return value

    def validate(self, attrs):
        """Validate that the object exists"""
        from apps.feeds.domain.entities.comment import Comment
        from apps.feeds.domain.entities.feed_post import FeedPost

        content_type = attrs["content_type"]
        object_id = attrs["object_id"]

        try:
            if content_type == "feedpost":
                FeedPost.objects.get(id=object_id)
            elif content_type == "comment":
                comment = Comment.objects.get(id=object_id)
                if comment.is_deleted:
                    raise serializers.ValidationError("Cannot like deleted comment")
        except (FeedPost.DoesNotExist, Comment.DoesNotExist):
            raise serializers.ValidationError("Object does not exist") from None

        return attrs
