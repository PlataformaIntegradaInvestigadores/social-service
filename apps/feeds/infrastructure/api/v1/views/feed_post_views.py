import logging

from django.db import connection
from django.db.models import BooleanField
from django.db.models.expressions import RawSQL
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.feeds.domain.entities.feed_post import FeedPost
from apps.feeds.domain.entities.post_file import PostFile
from apps.feeds.domain.services.feed_service import FeedService
from apps.feeds.infrastructure.api.v1.serializers.feed_post_serializers import (
    FeedPostCreateSerializer,
    FeedPostDetailSerializer,
    FeedPostSerializer,
    PostFileSerializer,
)

logger = logging.getLogger(__name__)


def _normalize_search_tag(tag):
    """Return the canonical value used only for tag comparisons."""
    return str(tag).strip().lstrip("#").strip().casefold()


def _parse_search_tags(query_params):
    """Accept repeated and legacy comma-separated ``tags`` parameters."""
    normalized_tags = []
    seen = set()

    for raw_value in query_params.getlist("tags", []):
        for raw_tag in raw_value.split(","):
            tag = _normalize_search_tag(raw_tag)
            if tag and tag not in seen:
                seen.add(tag)
                normalized_tags.append(tag)

    return normalized_tags


def _post_matches_any_tag(post, normalized_tags):
    """Check tag intersection for results already loaded into memory."""
    post_tags = {
        _normalize_search_tag(tag)
        for tag in (post.tags or [])
        if _normalize_search_tag(tag)
    }
    return bool(post_tags.intersection(normalized_tags))


def _filter_queryset_by_tags(queryset, normalized_tags):
    """Filter a JSON array of tags case-insensitively using PostgreSQL."""
    if not normalized_tags:
        return queryset

    table_name = connection.ops.quote_name(queryset.model._meta.db_table)
    matches_tags_sql = f"""
        EXISTS (
            SELECT 1
            FROM jsonb_array_elements_text(
                CASE
                    WHEN jsonb_typeof({table_name}."tags") = 'array'
                    THEN {table_name}."tags"
                    ELSE '[]'::jsonb
                END
            ) AS stored_tag(value)
            WHERE LOWER(BTRIM(stored_tag.value)) = ANY(%s::text[])
        )
    """

    return queryset.annotate(
        matches_requested_tags=RawSQL(
            matches_tags_sql,
            (normalized_tags,),
            output_field=BooleanField(),
        )
    ).filter(matches_requested_tags=True)


class FeedPostListCreateView(generics.ListCreateAPIView):
    """
    List and create feed posts

    GET: List user's posts
    POST: Create new post
    """

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]  # Para manejar archivos

    def get_queryset(self):
        """Get user's posts"""
        return FeedPost.objects.filter(
            author_identity_id=str(self.request.user.id)
        ).order_by("-created_at")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return FeedPostCreateSerializer
        return FeedPostSerializer

    def perform_create(self, serializer):
        """Create post with author"""
        serializer.validated_data["author"] = self.request.user

        # El serializer se encarga de crear el post con archivos y embeddings
        post = serializer.save()

        # Generar embedding para el post después de crearlo
        feed_service = FeedService()
        feed_service.update_post_embedding(post.id)

        logger.info(f"Post creado: {post.id} por {self.request.user}")

    def create(self, request, *args, **kwargs):
        """Create post and return full representation"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        # Return the full post representation using the read serializer
        post = serializer.instance
        response_serializer = FeedPostDetailSerializer(
            post, context={"request": request}
        )

        headers = self.get_success_headers(response_serializer.data)
        return Response(
            response_serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )


class FeedPostDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a feed post

    GET: Get post details
    PUT/PATCH: Update post (author only)
    DELETE: Delete post (author only)
    """

    serializer_class = FeedPostDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return FeedPost.objects.prefetch_related("post_files", "comments")

    def get_object(self):
        """Get post and record view interaction"""
        obj = get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])

        # Record view interaction if GET request
        if self.request.method == "GET":
            feed_service = FeedService()
            feed_service.handle_user_interaction(
                user_id=str(self.request.user.id),
                post_id=str(obj.id),
                interaction_type="view",
            )

        return obj

    def perform_update(self, serializer):
        """Update post (author only)"""
        if serializer.instance.author_identity_id != str(self.request.user.id):
            raise PermissionDenied("You can only edit your own posts")

        content_changed = "content" in serializer.validated_data
        post = serializer.save()

        # Update embedding if content changed
        if content_changed:
            feed_service = FeedService()
            feed_service.update_post_embedding(post.id)

    def perform_destroy(self, instance):
        """Delete post (author only)"""
        if instance.author_identity_id != str(self.request.user.id):
            raise PermissionDenied("You can only delete your own posts")
        instance.delete()


class FeedPostFileUploadView(generics.CreateAPIView):
    """
    Upload additional files to existing post

    POST: Add files to post
    """

    serializer_class = PostFileSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def create(self, request, *args, **kwargs):
        """Add files to existing post"""
        post_id = kwargs.get("post_id")
        post = get_object_or_404(FeedPost, id=post_id)

        # Check ownership
        if post.author_identity_id != str(request.user.id):
            return Response(
                {"error": "You can only add files to your own posts"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check file limit
        current_files = post.post_files.count()
        new_files = request.FILES.getlist("files", [])

        if current_files + len(new_files) > 10:
            return Response(
                {"error": "Cannot have more than 10 files per post"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create file attachments
        created_files = []
        for file in new_files:
            file_obj = PostFile.objects.create(post=post, file=file)
            created_files.append(file_obj)

        serializer = self.get_serializer(created_files, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class FeedPostSearchView(generics.ListAPIView):
    """
    Search feed posts using hybrid vector + full-text search.

    GET: Search posts by semantic similarity + keyword relevance.
    Returns results with scoring breakdown (similarity_score,
    text_match, relevance_score) for transparency.
    """

    serializer_class = FeedPostSerializer
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request, *args, **kwargs):
        """
        Override list to inject search-specific scoring fields into the
        serialized response without needing a separate serializer.
        """
        from apps.feeds.domain.services.feed_service import FeedService

        # ── Parámetros de búsqueda ──
        query = request.query_params.get("q", "")
        tags = _parse_search_tags(request.query_params)
        author = request.query_params.get("author", "")
        use_vector = request.query_params.get("vector", "true").lower() == "true"
        limit = int(request.query_params.get("limit", "20"))

        if not query and not tags and not author:
            return Response([])

        feed_service = FeedService()
        posts = []

        # ── Búsqueda híbrida vectorial + FTS ──
        if query and use_vector:
            try:
                posts = feed_service.search_posts_by_similarity(query, limit=limit)
            except Exception as e:
                logger.error(f"Error en búsqueda vectorial, fallback a texto: {str(e)}")

        # Filtro adicional por tags y autor
        if posts and (tags or author):
            if tags:
                posts = [p for p in posts if _post_matches_any_tag(p, tags)]
            if author:
                posts = [
                    p for p in posts if author.lower() in p.author.username.lower()
                ]

        # Fallback: búsqueda por texto si no hay resultados vectoriales
        if not posts and (query or tags or author):
            qs = FeedPost.objects.filter(is_public=True)
            if query:
                qs = qs.filter(content__icontains=query)
            if tags:
                qs = _filter_queryset_by_tags(qs, tags)
            if author:
                qs = qs.filter(author_snapshot__username__icontains=author)
            posts = list(qs.order_by("-created_at")[:limit])

        # ── Serialización con scores de búsqueda ──
        serializer = self.get_serializer(posts, many=True)
        results = serializer.data

        for i, post in enumerate(posts):
            if i < len(results):
                if (
                    hasattr(post, "relevance_score")
                    and post.relevance_score is not None
                ):
                    results[i]["relevance_score"] = round(
                        float(post.relevance_score), 4
                    )
                if hasattr(post, "similarity") and post.similarity is not None:
                    results[i]["similarity_score"] = round(float(post.similarity), 4)
                if hasattr(post, "text_match") and post.text_match is not None:
                    results[i]["text_match"] = round(float(post.text_match), 4)

        return Response(results)


class FeedPostStatsView(generics.RetrieveAPIView):
    """
    Get post statistics

    GET: Get detailed post stats
    """

    permission_classes = [permissions.IsAuthenticated]

    def retrieve(self, request, *args, **kwargs):
        """Get post statistics"""
        post_id = kwargs.get("pk")
        post = get_object_or_404(FeedPost, id=post_id)

        # Check if user can view stats (author only for now)
        if post.author_identity_id != str(request.user.id):
            return Response(
                {"error": "You can only view stats for your own posts"},
                status=status.HTTP_403_FORBIDDEN,
            )

        stats = {
            "post_id": post.id,
            "likes_count": post.likes_count,
            "comments_count": post.comments_count,
            "views_count": post.views_count,
            "shares_count": post.shares_count,
            "engagement_score": post.engagement_score,
            "files_count": post.post_files.count(),
            "created_at": post.created_at,
            "last_interaction": post.metadata.get("last_interaction"),
        }

        return Response(stats)
