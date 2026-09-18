from rest_framework import serializers

from apps.custom_auth.identity_profile_client import (
    get_identity_user_snapshot,
    merge_identity_snapshot,
)
from apps.feeds.domain.entities.comment import Comment


class CommentAuthorSerializer(serializers.Serializer):
    """Minimal user serializer for comment authors"""

    id = serializers.CharField(read_only=True)
    username = serializers.CharField(read_only=True, allow_blank=True)
    first_name = serializers.CharField(read_only=True, allow_blank=True)
    last_name = serializers.CharField(read_only=True, allow_blank=True)
    profile_picture = serializers.CharField(read_only=True, allow_blank=True)


class CommentSerializer(serializers.ModelSerializer):
    """Basic comment serializer"""

    author = serializers.SerializerMethodField()
    replies_count = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "content",
            "author",
            "parent_comment",
            "likes_count",
            "replies_count",
            "is_liked",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "author",
            "likes_count",
            "replies_count",
            "is_liked",
            "is_deleted",
            "created_at",
            "updated_at",
        ]

    def get_author(self, obj):
        request = self.context.get("request")
        authorization = request.headers.get("Authorization", "") if request else ""
        cache = self.context.setdefault("identity_user_cache", {})
        identity_payload = get_identity_user_snapshot(
            obj.author_identity_id,
            authorization_header=authorization,
            cache=cache,
        )
        snapshot = merge_identity_snapshot(obj.author_snapshot, identity_payload)
        return CommentAuthorSerializer(snapshot).data

    def get_replies_count(self, obj):
        """Get count of non-deleted replies"""
        return obj.replies.filter(is_deleted=False).count()

    def get_is_liked(self, obj):
        """Check if current user has liked the comment"""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False

        from django.contrib.contenttypes.models import ContentType

        from apps.feeds.domain.entities.like import Like

        content_type = ContentType.objects.get_for_model(Comment)
        return Like.objects.filter(
            user_identity_id=str(request.user.id),
            content_type=content_type,
            object_id=obj.id,
        ).exists()


class CommentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating comments"""

    class Meta:
        model = Comment
        fields = ["content", "parent_comment"]

    def validate_content(self, value):
        """Validate comment content"""
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Content cannot be empty")
        if len(value) > 1000:
            raise serializers.ValidationError("Content cannot exceed 1000 characters")
        return value.strip()

    def validate_parent_comment(self, value):
        """Validate parent comment"""
        if value and value.is_deleted:
            raise serializers.ValidationError("Cannot reply to deleted comment")
        return value


class CommentDetailSerializer(CommentSerializer):
    """Detailed comment serializer with replies"""

    replies = serializers.SerializerMethodField()

    class Meta(CommentSerializer.Meta):
        fields = CommentSerializer.Meta.fields + ["replies"]

    def get_replies(self, obj):
        """Get comment replies (limited depth)"""
        if obj.get_level() >= 3:  # Limit nesting depth
            return []

        replies = obj.replies.filter(is_deleted=False).order_by("created_at")
        return CommentSerializer(replies, many=True, context=self.context).data


class CommentThreadSerializer(serializers.ModelSerializer):
    """Serializer for comment threads with full hierarchy"""

    author = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()
    user_has_liked = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "content",
            "author",
            "likes_count",
            "replies",
            "user_has_liked",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "author",
            "likes_count",
            "user_has_liked",
            "is_deleted",
            "created_at",
            "updated_at",
        ]

    def get_author(self, obj):
        request = self.context.get("request")
        authorization = request.headers.get("Authorization", "") if request else ""
        cache = self.context.setdefault("identity_user_cache", {})
        identity_payload = get_identity_user_snapshot(
            obj.author_identity_id,
            authorization_header=authorization,
            cache=cache,
        )
        snapshot = merge_identity_snapshot(obj.author_snapshot, identity_payload)
        return CommentAuthorSerializer(snapshot).data

    def get_replies(self, obj):
        """Get all replies recursively"""
        if obj.get_level() >= 5:  # Hard limit for recursion
            return []

        replies = obj.replies.filter(is_deleted=False).order_by("created_at")
        return CommentThreadSerializer(replies, many=True, context=self.context).data

    def get_user_has_liked(self, obj):
        """Check if current user has liked the comment"""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False

        from django.contrib.contenttypes.models import ContentType

        from apps.feeds.domain.entities.like import Like

        content_type = ContentType.objects.get_for_model(Comment)
        return Like.objects.filter(
            user_identity_id=str(request.user.id),
            content_type=content_type,
            object_id=obj.id,
        ).exists()
