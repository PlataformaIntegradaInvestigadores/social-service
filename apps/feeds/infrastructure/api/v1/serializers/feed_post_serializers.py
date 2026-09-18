import json

from rest_framework import serializers

from apps.custom_auth.identity_principal import snapshot_from_principal
from apps.custom_auth.identity_profile_client import (
    get_identity_user_snapshot,
    merge_identity_snapshot,
)
from apps.feeds.domain.entities.feed_post import FeedPost
from apps.feeds.domain.entities.poll import Poll
from apps.feeds.domain.entities.post_file import PostFile

from .poll_serializers import PollSerializer


class RelativeFileField(serializers.FileField):
    def to_representation(self, value):
        if not value:
            return None
        try:
            return value.url
        except ValueError:
            return None


class RelativeImageField(serializers.ImageField):
    def to_representation(self, value):
        if not value:
            return None
        try:
            return value.url
        except ValueError:
            return None


class PostFileSerializer(serializers.ModelSerializer):
    """Serializer for post file attachments"""

    file = RelativeFileField(read_only=True)

    class Meta:
        model = PostFile
        fields = [
            "id",
            "file",
            "file_type",
            "file_size",
            "original_filename",
            "alt_text",
            "uploaded_at",
        ]
        read_only_fields = ["id", "file_size", "original_filename", "uploaded_at"]


class AuthorSerializer(serializers.Serializer):
    """Minimal user serializer for post authors"""

    id = serializers.CharField(read_only=True)
    username = serializers.CharField(read_only=True, allow_blank=True)
    first_name = serializers.CharField(read_only=True, allow_blank=True)
    last_name = serializers.CharField(read_only=True, allow_blank=True)
    profile_picture = serializers.CharField(read_only=True, allow_blank=True)


class FlexibleTagsField(serializers.Field):
    """Accept tags from JSON payloads and multipart FormData."""

    default_error_messages = {
        "invalid": "Tags must be a JSON array or a comma-separated string.",
        "not_list": "Tags must be a list of text values.",
    }

    def to_internal_value(self, data):
        if data in (None, ""):
            return []

        if isinstance(data, str):
            data = data.strip()
            if not data:
                return []
            if data.startswith("["):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    try:
                        data = json.loads(data.replace('\\"', '"'))
                    except json.JSONDecodeError:
                        self.fail("invalid")
            else:
                data = [tag.strip() for tag in data.split(",") if tag.strip()]

        if not isinstance(data, list):
            self.fail("not_list")

        cleaned_tags = []
        seen_tags = set()
        for tag in data:
            if not isinstance(tag, str):
                self.fail("not_list")
            cleaned_tag = tag.strip().lstrip("#").strip()
            normalized_tag = cleaned_tag.casefold()
            if cleaned_tag and normalized_tag not in seen_tags:
                seen_tags.add(normalized_tag)
                cleaned_tags.append(cleaned_tag)
        return cleaned_tags

    def to_representation(self, value):
        return value or []


class FeedPostSerializer(serializers.ModelSerializer):
    """Basic feed post serializer"""

    tags = FlexibleTagsField(required=False)
    author = serializers.SerializerMethodField()
    files = serializers.SerializerMethodField()
    poll = PollSerializer(read_only=True)
    is_liked = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()

    class Meta:
        model = FeedPost
        fields = [
            "id",
            "content",
            "author",
            "files",
            "poll",
            "tags",
            "likes_count",
            "comments_count",
            "views_count",
            "shares_count",
            "engagement_score",
            "is_public",
            "is_liked",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "author",
            "likes_count",
            "comments_count",
            "views_count",
            "shares_count",
            "engagement_score",
            "is_liked",
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
        return AuthorSerializer(snapshot).data

    def get_is_liked(self, obj):
        """Check if current user has liked this post"""
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            from django.contrib.contenttypes.models import ContentType

            from apps.feeds.domain.entities.like import Like

            content_type = ContentType.objects.get_for_model(obj)
            return Like.objects.filter(
                user_identity_id=str(request.user.id),
                content_type=content_type,
                object_id=obj.id,
            ).exists()
        return False

    def get_comments_count(self, obj):
        """Get accurate comments count"""
        if hasattr(obj, "comments_count_real"):
            return obj.comments_count_real
        return obj.comments.filter(is_deleted=False).count()

    def get_files(self, obj):
        """Return only media files that still exist in storage."""
        existing_files = []
        for post_file in obj.post_files.all():
            try:
                if post_file.file and post_file.file.storage.exists(
                    post_file.file.name
                ):
                    existing_files.append(post_file)
            except OSError:
                continue
        return PostFileSerializer(existing_files, many=True, context=self.context).data


class FeedPostCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating feed posts"""

    tags = FlexibleTagsField(required=False, default=list)
    files = serializers.ListField(
        child=serializers.FileField(), required=False, allow_empty=True, write_only=True
    )
    poll_data = serializers.CharField(
        required=False,
        write_only=True,
        allow_blank=True,
        help_text="Poll data as JSON string with 'question' and 'options' fields",
    )

    class Meta:
        model = FeedPost
        fields = ["content", "tags", "is_public", "files", "poll_data"]

    def validate_poll_data(self, value):
        """Validate poll data"""
        import logging

        logger = logging.getLogger(__name__)

        logger.info(f"Validating poll_data: {value} (type: {type(value)})")

        # Handle empty values
        if not value or value == "{}" or (isinstance(value, dict) and not value):
            logger.info("poll_data is empty, returning None")
            return None

        # Parse JSON string
        if isinstance(value, str):
            import json

            logger.info(f"poll_data is string, parsing: {value}")
            try:
                value = json.loads(value)
                logger.info(f"Parsed poll_data: {value}")
            except (json.JSONDecodeError, TypeError) as e:
                logger.error(f"JSON parse error: {e}")
                raise serializers.ValidationError(
                    f"Invalid JSON format for poll_data: {e}"
                ) from e

        # Validate required fields
        if not isinstance(value, dict):
            raise serializers.ValidationError("Poll data must be a valid JSON object")

        if "question" not in value or "options" not in value:
            logger.error(f"poll_data missing required fields: {value}")
            raise serializers.ValidationError(
                "Poll data must contain 'question' and 'options'"
            )

        question = value["question"].strip()
        if not question:
            raise serializers.ValidationError("Poll question cannot be empty")

        options = value["options"]
        if not isinstance(options, list) or len(options) < 2:
            raise serializers.ValidationError("Poll must have at least 2 options")

        # Clean and validate options
        cleaned_options = [opt.strip() for opt in options if opt.strip()]
        if len(cleaned_options) < 2:
            raise serializers.ValidationError("Poll must have at least 2 valid options")

        result = {"question": question, "options": cleaned_options}
        logger.info(f"Validated poll_data: {result}")
        return result

    def validate_content(self, value):
        """Validate post content"""
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError(
                "La descripción de la publicación es obligatoria."
            )
        if len(value) > 5000:
            raise serializers.ValidationError(
                "La descripción no puede superar los 5000 caracteres."
            )
        return value.strip()

    def validate_files(self, value):
        """Validate uploaded files"""
        if not value:
            return value

        if len(value) > 10:
            raise serializers.ValidationError(
                "No se pueden subir más de 10 archivos por publicación."
            )

        total_size = sum(f.size for f in value)
        if total_size > 50 * 1024 * 1024:  # 50MB total limit
            raise serializers.ValidationError(
                "El tamaño total de los archivos no puede superar 50 MB."
            )

        for file in value:
            if file.size > 10 * 1024 * 1024:  # 10MB per file
                raise serializers.ValidationError(
                    "Cada archivo debe pesar como máximo 10 MB."
                )

        return value

    def create(self, validated_data):
        """Create post with files and poll"""
        import logging

        logger = logging.getLogger(__name__)

        files_data = validated_data.pop("files", [])
        poll_data = validated_data.pop("poll_data", None)
        author = validated_data.pop("author", None)

        logger.info(f"Creating post with poll_data: {poll_data}")

        if author is not None:
            request = self.context.get("request")
            authorization = request.headers.get("Authorization", "") if request else ""
            identity_payload = get_identity_user_snapshot(
                getattr(author, "id", ""),
                authorization_header=authorization,
                cache=self.context.setdefault("identity_user_cache", {}),
            )
            validated_data["author_identity_id"] = str(author.id)
            validated_data["author_snapshot"] = merge_identity_snapshot(
                snapshot_from_principal(author),
                identity_payload,
            )

        post = FeedPost.objects.create(**validated_data)

        # Create file attachments
        for file_data in files_data:
            # Determine file type based on file extension or content type
            file_type = self._determine_file_type(file_data)

            PostFile.objects.create(
                post=post,
                file=file_data,
                file_type=file_type,
                file_size=file_data.size,
                original_filename=file_data.name,
            )

        # Create poll if provided
        if poll_data:
            logger.info(f"Creating poll with question: {poll_data['question']}")
            logger.info(f"Poll options: {poll_data['options']}")

            poll = Poll.objects.create(question=poll_data["question"])

            logger.info(f"Poll created with ID: {poll.id}")

            # Create poll options
            for index, option_text in enumerate(poll_data["options"]):
                from apps.feeds.domain.entities.poll import PollOption

                PollOption.objects.create(poll=poll, text=option_text, order=index)
                logger.info(f"Created poll option {index}: {option_text}")

            # Associate poll with post
            post.poll = poll
            post.save(update_fields=["poll"])
            logger.info(f"Associated poll {poll.id} with post {post.id}")
        else:
            logger.info("No poll_data provided")

        return post

    def _determine_file_type(self, file):
        """Determine file type based on extension and content type"""

        filename = file.name.lower()
        content_type = file.content_type if hasattr(file, "content_type") else None

        # Check by MIME type first
        if content_type:
            if content_type.startswith("image/"):
                return "image"
            elif content_type.startswith("video/"):
                return "video"
            elif content_type.startswith("audio/"):
                return "audio"

        # Check by file extension
        if filename.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg")):
            return "image"
        elif filename.endswith((".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm")):
            return "video"
        elif filename.endswith((".mp3", ".wav", ".ogg", ".m4a", ".aac")):
            return "audio"
        elif filename.endswith((".pdf", ".doc", ".docx", ".txt", ".rtf")):
            return "document"

        return "other"


class FeedPostDetailSerializer(FeedPostSerializer):
    """Detailed feed post serializer with comments preview"""

    recent_comments = serializers.SerializerMethodField()
    user_has_liked = serializers.SerializerMethodField()

    class Meta(FeedPostSerializer.Meta):
        fields = FeedPostSerializer.Meta.fields + ["recent_comments", "user_has_liked"]

    def get_recent_comments(self, obj):
        """Get recent comments preview"""
        from .comment_serializers import CommentSerializer

        recent_comments = obj.comments.filter(
            parent_comment=None, is_deleted=False
        ).order_by("-created_at")[:3]
        return CommentSerializer(recent_comments, many=True, context=self.context).data

    def get_user_has_liked(self, obj):
        """Check if current user has liked the post"""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False

        from django.contrib.contenttypes.models import ContentType

        from apps.feeds.domain.entities.like import Like

        content_type = ContentType.objects.get_for_model(FeedPost)
        return Like.objects.filter(
            user_identity_id=str(request.user.id),
            content_type=content_type,
            object_id=obj.id,
        ).exists()
