from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes as perm_classes
from rest_framework.response import Response

from apps.feeds.domain.entities.comment import Comment
from apps.feeds.domain.entities.feed_post import FeedPost
from apps.feeds.domain.entities.like import Like
from apps.feeds.domain.services.feed_service import FeedService
from apps.feeds.infrastructure.api.v1.serializers.like_serializers import (
    LikeSerializer,
    LikeToggleSerializer,
)


class LikeToggleView(generics.GenericAPIView):
    """
    Toggle like on post or comment

    POST: Toggle like (like/unlike)
    """

    serializer_class = LikeToggleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        """Toggle like"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        content_type = serializer.validated_data["content_type"]
        object_id = serializer.validated_data["object_id"]

        # Get the object to like
        if content_type == "feedpost":
            content_object = get_object_or_404(FeedPost, id=object_id)
            ContentType.objects.get_for_model(FeedPost)
        else:  # comment
            content_object = get_object_or_404(Comment, id=object_id)
            if content_object.is_deleted:
                return Response(
                    {"error": "Cannot like deleted comment"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            ContentType.objects.get_for_model(Comment)

        # Toggle like using service
        feed_service = FeedService()

        if content_type == "feedpost":
            is_liked = feed_service.toggle_like(request.user, content_object)
        else:
            is_liked = feed_service.toggle_comment_like(request.user, content_object)

        return Response(
            {
                "liked": is_liked,
                "likes_count": content_object.likes_count,
                "message": "Liked" if is_liked else "Unliked",
            }
        )


class UserLikesView(generics.ListAPIView):
    """
    Get user's likes

    GET: List posts/comments liked by user
    """

    serializer_class = LikeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Get user's likes"""
        queryset = Like.objects.filter(user_identity_id=str(self.request.user.id))

        # Filter by content type if specified
        content_type = self.request.query_params.get("content_type", "")
        if content_type:
            if content_type.lower() == "feedpost":
                ct = ContentType.objects.get_for_model(FeedPost)
                queryset = queryset.filter(content_type=ct)
            elif content_type.lower() == "comment":
                ct = ContentType.objects.get_for_model(Comment)
                queryset = queryset.filter(content_type=ct)

        return queryset.select_related("content_type").order_by("-created_at")


@api_view(["POST", "DELETE"])
@perm_classes([permissions.IsAuthenticated])
def like_post(request, post_id):
    """
    Like/Unlike a specific post

    POST: Toggle like (like/unlike)
    DELETE: Remove like
    """
    post = get_object_or_404(FeedPost, id=post_id)

    feed_service = FeedService()

    if request.method == "POST":
        # Toggle like (existing behavior)
        is_liked = feed_service.toggle_like(request.user, post)
        return Response(
            {
                "liked": is_liked,
                "likes_count": post.likes_count,
                "message": "Liked" if is_liked else "Unliked",
            }
        )

    elif request.method == "DELETE":
        # Remove like specifically
        ct = ContentType.objects.get_for_model(FeedPost)

        # Check if like exists and remove it
        like_exists = Like.objects.filter(
            user_identity_id=str(request.user.id), content_type=ct, object_id=post.id
        ).exists()

        if like_exists:
            Like.objects.filter(
                user_identity_id=str(request.user.id),
                content_type=ct,
                object_id=post.id,
            ).delete()

            # Update likes count
            post.likes_count = max(0, post.likes_count - 1)
            post.save(update_fields=["likes_count"])

            return Response(
                {"liked": False, "likes_count": post.likes_count, "message": "Unliked"}
            )
        else:
            return Response(
                {
                    "liked": False,
                    "likes_count": post.likes_count,
                    "message": "Post was not liked",
                }
            )


@api_view(["POST", "DELETE"])
@perm_classes([permissions.IsAuthenticated])
def like_comment(request, comment_id):
    """
    Like/Unlike a specific comment

    POST: Toggle like (like/unlike)
    DELETE: Remove like
    """
    comment = get_object_or_404(Comment, id=comment_id)

    if comment.is_deleted:
        return Response(
            {"error": "Cannot like deleted comment"}, status=status.HTTP_400_BAD_REQUEST
        )

    feed_service = FeedService()

    if request.method == "POST":
        # Toggle like (existing behavior)
        is_liked = feed_service.toggle_comment_like(request.user, comment)
        return Response(
            {
                "liked": is_liked,
                "likes_count": comment.likes_count,
                "message": "Liked" if is_liked else "Unliked",
            }
        )

    elif request.method == "DELETE":
        # Remove like specifically
        ct = ContentType.objects.get_for_model(Comment)

        # Check if like exists and remove it
        like_exists = Like.objects.filter(
            user_identity_id=str(request.user.id), content_type=ct, object_id=comment.id
        ).exists()

        if like_exists:
            Like.objects.filter(
                user_identity_id=str(request.user.id),
                content_type=ct,
                object_id=comment.id,
            ).delete()

            # Update likes count
            comment.likes_count = max(0, comment.likes_count - 1)
            comment.save(update_fields=["likes_count"])

            return Response(
                {
                    "liked": False,
                    "likes_count": comment.likes_count,
                    "message": "Unliked",
                }
            )
        else:
            return Response(
                {
                    "liked": False,
                    "likes_count": comment.likes_count,
                    "message": "Comment was not liked",
                }
            )


@api_view(["GET"])
@perm_classes([permissions.IsAuthenticated])
def post_likes(request, post_id):
    """
    Get users who liked a post

    GET: List users who liked the post
    """
    post = get_object_or_404(FeedPost, id=post_id)

    # Get likes for this post
    ct = ContentType.objects.get_for_model(FeedPost)
    likes = Like.objects.filter(content_type=ct, object_id=post.id).order_by(
        "-created_at"
    )

    # Serialize the likes
    serializer = LikeSerializer(likes, many=True)

    return Response({"likes": serializer.data, "total_count": likes.count()})


@api_view(["GET"])
@perm_classes([permissions.IsAuthenticated])
def comment_likes(request, comment_id):
    """
    Get users who liked a comment

    GET: List users who liked the comment
    """
    comment = get_object_or_404(Comment, id=comment_id)

    if comment.is_deleted:
        return Response(
            {"error": "Comment not found"}, status=status.HTTP_404_NOT_FOUND
        )

    # Get likes for this comment
    ct = ContentType.objects.get_for_model(Comment)
    likes = Like.objects.filter(content_type=ct, object_id=comment.id).order_by(
        "-created_at"
    )

    # Serialize the likes
    serializer = LikeSerializer(likes, many=True)

    return Response({"likes": serializer.data, "total_count": likes.count()})
