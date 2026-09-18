from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.custom_auth.identity_principal import snapshot_from_principal
from apps.custom_auth.identity_profile_client import (
    get_identity_user_snapshot,
    merge_identity_snapshot,
)
from apps.feeds.domain.entities.comment import Comment
from apps.feeds.domain.entities.feed_post import FeedPost
from apps.feeds.domain.services.feed_service import FeedService
from apps.feeds.infrastructure.api.v1.serializers.comment_serializers import (
    CommentCreateSerializer,
    CommentDetailSerializer,
    CommentSerializer,
    CommentThreadSerializer,
)


class CommentListCreateView(generics.ListCreateAPIView):
    """
    List and create comments for a post

    GET: List post comments
    POST: Create new comment
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Get comments for a post"""
        post_id = self.kwargs.get("post_id")
        return Comment.objects.filter(
            post_id=post_id, parent_comment=None, is_deleted=False  # Only root comments
        ).order_by("-created_at")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CommentCreateSerializer
        return CommentSerializer

    def perform_create(self, serializer):
        """Create comment"""
        post_id = self.kwargs.get("post_id")
        post = get_object_or_404(FeedPost, id=post_id)
        identity_payload = get_identity_user_snapshot(
            self.request.user.id,
            authorization_header=self.request.headers.get("Authorization", ""),
            cache={},
        )
        author_snapshot = merge_identity_snapshot(
            snapshot_from_principal(self.request.user),
            identity_payload,
        )

        with transaction.atomic():
            # Create comment using service
            feed_service = FeedService()
            comment = feed_service.create_comment(
                author_id=self.request.user.id,
                post_id=post.id,
                content=serializer.validated_data["content"],
                parent_comment_id=(
                    serializer.validated_data.get("parent_comment").id
                    if serializer.validated_data.get("parent_comment")
                    else None
                ),
                author_snapshot=author_snapshot,
            )

            # Update serializer instance for response
            serializer.instance = comment

    def create(self, request, *args, **kwargs):
        """Create comment and return full representation"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        # Return the full comment representation using the read serializer
        comment = serializer.instance
        if comment:
            response_serializer = CommentDetailSerializer(
                comment, context={"request": request}
            )
            headers = self.get_success_headers(response_serializer.data)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED,
                headers=headers,
            )
        else:
            return Response(
                {"error": "No se pudo crear el comentario"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class CommentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a comment

    GET: Get comment details with replies
    PUT/PATCH: Update comment (author only)
    DELETE: Soft delete comment (author only)
    """

    serializer_class = CommentDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Comment.objects.select_related("post").prefetch_related("replies")

    def get_object(self):
        """Get comment and check permissions"""
        obj = get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])

        # Don't show deleted comments to non-authors
        if obj.is_deleted and obj.author_identity_id != str(self.request.user.id):
            raise PermissionDenied("Comment not found")

        return obj

    def perform_update(self, serializer):
        """Update comment (author only)"""
        if serializer.instance.author_identity_id != str(self.request.user.id):
            raise PermissionDenied("You can only edit your own comments")

        if serializer.instance.is_deleted:
            raise PermissionDenied("Cannot edit deleted comment")

        serializer.save()

    def perform_destroy(self, instance):
        """Soft delete comment (author only)"""
        if instance.author_identity_id != str(self.request.user.id):
            raise PermissionDenied("You can only delete your own comments")

        # Soft delete
        instance.soft_delete()


class CommentThreadView(generics.RetrieveAPIView):
    """
    Get full comment thread with all replies

    GET: Get comment thread with nested replies
    """

    serializer_class = CommentThreadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            Comment.objects.filter(is_deleted=False)
            .select_related("post")
            .prefetch_related("replies")
        )


class CommentRepliesView(generics.ListCreateAPIView):
    """
    List and create replies to a comment

    GET: List comment replies
    POST: Create reply to comment
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Get replies to a comment"""
        comment_id = self.kwargs.get("comment_id")
        return Comment.objects.filter(
            parent_comment_id=comment_id, is_deleted=False
        ).order_by("created_at")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CommentCreateSerializer
        return CommentSerializer

    def perform_create(self, serializer):
        """Create reply to comment"""
        comment_id = self.kwargs.get("comment_id")
        parent_comment = get_object_or_404(Comment, id=comment_id)

        if parent_comment.is_deleted:
            raise PermissionDenied("Cannot reply to deleted comment")

        # Check thread depth limit
        if parent_comment.get_level() >= 5:
            raise PermissionDenied("Maximum reply depth reached")
        identity_payload = get_identity_user_snapshot(
            self.request.user.id,
            authorization_header=self.request.headers.get("Authorization", ""),
            cache={},
        )
        author_snapshot = merge_identity_snapshot(
            snapshot_from_principal(self.request.user),
            identity_payload,
        )

        with transaction.atomic():
            # Create reply using service
            feed_service = FeedService()
            comment = feed_service.create_comment(
                author_id=self.request.user.id,
                post_id=parent_comment.post.id,
                content=serializer.validated_data["content"],
                parent_comment_id=parent_comment.id,
                author_snapshot=author_snapshot,
            )

            # Update serializer instance for response
            serializer.instance = comment


class CommentSearchView(generics.ListAPIView):
    """
    Search comments

    GET: Search comments by content
    """

    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Search comments"""
        queryset = Comment.objects.filter(is_deleted=False)

        # Search parameters
        query = self.request.query_params.get("q", "")
        post_id = self.request.query_params.get("post_id", "")
        author = self.request.query_params.get("author", "")

        if query:
            queryset = queryset.filter(content__icontains=query)

        if post_id:
            queryset = queryset.filter(post_id=post_id)

        if author:
            queryset = queryset.filter(author_snapshot__username__icontains=author)

        return queryset.select_related("post").order_by("-created_at")
