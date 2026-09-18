import logging

from django.db import models
from django.db.models.expressions import RawSQL
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes as perm_classes
from rest_framework.response import Response

from apps.feeds.domain.entities.feed_post import FeedPost
from apps.feeds.domain.services.feed_service import FeedService
from apps.feeds.infrastructure.api.v1.serializers.feed_post_serializers import (
    FeedPostDetailSerializer,
    FeedPostSerializer,
)
from apps.feeds.infrastructure.api.v1.serializers.feed_serializers import (
    FeedFilterSerializer,
    FeedRequestSerializer,
    UserInteractionSerializer,
)

logger = logging.getLogger(__name__)


class FeedView(generics.GenericAPIView):
    """
    Get personalized or trending feed

    GET: Get feed based on type (personalized, trending, latest)
    POST: Get feed with filters
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """Get feed"""
        # Parse query parameters
        serializer = FeedRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        feed_type = serializer.validated_data["feed_type"]
        limit = serializer.validated_data["limit"]
        cursor = serializer.validated_data.get("cursor")
        author = serializer.validated_data.get("author")

        # Si se especifica un autor, filtrar por posts de ese usuario
        if author:
            try:
                author_user = str(author)

                # Obtener posts del usuario específico
                queryset = (
                    FeedPost.objects.filter(
                        author_identity_id=author_user, is_public=True
                    )
                    .prefetch_related("post_files", "comments")
                    .order_by("-created_at")
                )

                # Apply cursor pagination if provided
                if cursor:
                    try:
                        from datetime import datetime

                        cursor_date = datetime.fromisoformat(
                            cursor.replace("Z", "+00:00")
                        )
                        queryset = queryset.filter(created_at__lt=cursor_date)
                    except (ValueError, TypeError):
                        pass  # Invalid cursor, ignore

                # Get posts with limit + 1 to check if there's a next page
                posts = list(queryset[: limit + 1])
                has_next = len(posts) > limit

                if has_next:
                    posts = posts[:limit]

                # Get next cursor
                next_cursor = None
                if has_next and posts:
                    next_cursor = posts[-1].created_at.isoformat()

            except Exception:
                # Usuario no existe, retornar lista vacía
                posts = []
                has_next = False
                next_cursor = None

        else:
            # Get feed using service (lógica original)
            feed_service = FeedService()

            if feed_type == "personalized":
                posts, has_next, next_cursor = feed_service.get_personalized_feed(
                    user=request.user, limit=limit, cursor=cursor
                )
            elif feed_type == "trending":
                posts, has_next, next_cursor = feed_service.get_trending_feed(
                    limit=limit, cursor=cursor, exclude_user_id=request.user.id
                )
            else:  # latest
                posts, has_next, next_cursor = feed_service.get_latest_feed(
                    limit=limit, cursor=cursor, exclude_user_id=request.user.id
                )

        # Serialize response
        post_serializer = FeedPostSerializer(
            posts, many=True, context={"request": request}
        )

        response_data = {
            "posts": post_serializer.data,
            "has_next": has_next,
            "next_cursor": next_cursor,
            "total_count": len(posts),
        }

        return Response(response_data)

    def post(self, request, *args, **kwargs):
        """Get filtered feed"""
        # Parse request data
        request_serializer = FeedRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)

        filter_serializer = FeedFilterSerializer(data=request.data.get("filters", {}))
        filter_serializer.is_valid(raise_exception=True)

        feed_type = request_serializer.validated_data["feed_type"]
        limit = request_serializer.validated_data["limit"]
        cursor = request_serializer.validated_data.get("cursor")
        filters = filter_serializer.validated_data

        # Get filtered feed
        feed_service = FeedService()
        posts, has_next, next_cursor = feed_service.get_filtered_feed(
            user=request.user,
            feed_type=feed_type,
            filters=filters,
            limit=limit,
            cursor=cursor,
        )

        # Serialize response
        post_serializer = FeedPostDetailSerializer(
            posts, many=True, context={"request": request}
        )

        response_data = {
            "posts": post_serializer.data,
            "has_next": has_next,
            "next_cursor": next_cursor,
            "total_count": len(posts),
        }

        return Response(response_data)


class UserInteractionView(generics.GenericAPIView):
    """
    Record user interactions with posts

    POST: Record interaction (view, share, click, save)
    """

    serializer_class = UserInteractionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        """Record user interaction"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        post_id = serializer.validated_data["post_id"]
        interaction_type = serializer.validated_data["interaction_type"]

        # Get post
        post = get_object_or_404(FeedPost, id=post_id)

        # Record interaction using service
        feed_service = FeedService()
        feed_service.handle_user_interaction(
            user_id=str(request.user.id),
            post_id=str(post.id),
            interaction_type=interaction_type,
        )

        return Response(
            {
                "message": f"{interaction_type.title()} recorded successfully",
                "post_id": post_id,
                "interaction_type": interaction_type,
            }
        )


@api_view(["GET"])
@perm_classes([permissions.IsAuthenticated])
def trending_posts(request):
    """
    Get trending posts

    GET: Get trending posts based on engagement
    """
    # Get parameters
    try:
        limit = min(max(int(request.GET.get("limit", 20)), 1), 50)
    except (TypeError, ValueError):
        limit = 20
    time_range = request.GET.get("time_range", "24h")  # 24h, 7d, 30d

    # Calculate time threshold
    now = timezone.now()
    if time_range == "24h":
        time_threshold = now - timezone.timedelta(hours=24)
    elif time_range == "7d":
        time_threshold = now - timezone.timedelta(days=7)
    elif time_range == "30d":
        time_threshold = now - timezone.timedelta(days=30)
    else:
        time_threshold = now - timezone.timedelta(hours=24)

    # Calcular horas desde la creación para mostrar en respuesta
    hours_old_sql = 'EXTRACT(EPOCH FROM (NOW() - "feeds_feedpost"."created_at")) / 3600'

    # Obtener trending score mejorado para ordenamiento
    trending_score_sql = """
        (
            engagement_score * 0.8 + 
            (engagement_score / SQRT(GREATEST(1, EXTRACT(EPOCH FROM (NOW() - "feeds_feedpost"."created_at")) / 3600))) * 0.2
        )
    """

    try:
        # Get trending posts con score calculado
        posts = list(
            FeedPost.objects.filter(created_at__gte=time_threshold, is_public=True)
            .annotate(
                hours_old=RawSQL(hours_old_sql, []),
                trending_rank=RawSQL(trending_score_sql, []),
                comments_count_real=models.Count(
                    "comments", filter=models.Q(comments__is_deleted=False)
                ),
            )
            .prefetch_related("post_files", "comments")
            .order_by("-trending_rank", "-engagement_score", "-created_at")[:limit]
        )
    except Exception as exc:
        logger.exception(
            "Error calculando feed trending; se devuelve feed reciente: %s", exc
        )
        posts = list(
            FeedPost.objects.filter(created_at__gte=time_threshold, is_public=True)
            .prefetch_related("post_files", "comments")
            .order_by("-created_at")[:limit]
        )

    # Serialize
    serializer = FeedPostDetailSerializer(
        posts, many=True, context={"request": request}
    )

    # Agregar metadatos de trending a la respuesta
    post_data = serializer.data
    for i, post in enumerate(posts):
        post_data[i]["trending_metadata"] = {
            "hours_old": round(
                getattr(
                    post, "hours_old", (now - post.created_at).total_seconds() / 3600
                ),
                1,
            ),
            "engagement_score": round(post.engagement_score, 2),
            "trending_rank": round(getattr(post, "trending_rank", 0), 2),
        }

    return Response(
        {"posts": post_data, "time_range": time_range, "total_count": len(posts)}
    )


@api_view(["GET"])
@perm_classes([permissions.IsAuthenticated])
def user_feed_stats(request):
    """
    Get user's feed statistics

    GET: Get user's posting and engagement stats
    """
    user = request.user

    # Get user's posts
    user_posts = FeedPost.objects.filter(author_identity_id=str(user.id))

    # Calculate stats
    stats = {
        "total_posts": user_posts.count(),
        "total_likes_received": sum(post.likes_count for post in user_posts),
        "total_comments_received": sum(post.comments_count for post in user_posts),
        "total_views_received": sum(post.views_count for post in user_posts),
        "total_shares_received": sum(post.shares_count for post in user_posts),
        "average_engagement": user_posts.aggregate(
            avg_engagement=models.Avg("engagement_score")
        )["avg_engagement"]
        or 0,
        "most_liked_post": None,
        "most_commented_post": None,
    }

    # Get most liked and commented posts
    most_liked = user_posts.order_by("-likes_count").first()
    most_commented = user_posts.order_by("-comments_count").first()

    if most_liked:
        stats["most_liked_post"] = {
            "id": most_liked.id,
            "content": most_liked.content[:100],
            "likes_count": most_liked.likes_count,
        }

    if most_commented:
        stats["most_commented_post"] = {
            "id": most_commented.id,
            "content": most_commented.content[:100],
            "comments_count": most_commented.comments_count,
        }

    return Response(stats)


@api_view(["GET"])
@perm_classes([permissions.IsAuthenticated])
def feed_recommendations(request):
    """
    Get personalized feed recommendations

    GET: Get posts recommended based on user embeddings
    """
    limit = min(int(request.GET.get("limit", 10)), 50)

    # Get recommendations using service
    feed_service = FeedService()
    posts, has_next, next_cursor = feed_service.get_personalized_feed(
        user=request.user, limit=limit
    )

    # Serialize
    serializer = FeedPostDetailSerializer(
        posts, many=True, context={"request": request}
    )

    return Response(
        {
            "recommendations": serializer.data,
            "has_next": has_next,
            "next_cursor": next_cursor,
            "total_count": len(posts),
        }
    )


class UserPostsView(generics.ListAPIView):
    """
    Get posts from the current authenticated user

    GET: Get user's own posts with pagination and filters
    """

    serializer_class = FeedPostDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Get current user's posts"""
        user = self.request.user
        queryset = (
            FeedPost.objects.filter(author_identity_id=str(user.id))
            .prefetch_related("post_files", "comments")
            .order_by("-created_at")
        )

        return queryset

    def list(self, request, *args, **kwargs):
        """List user posts with pagination"""
        queryset = self.get_queryset()

        # Parse pagination parameters
        limit = min(int(request.GET.get("limit", 20)), 50)
        cursor = request.GET.get("cursor")

        # Apply cursor pagination if provided
        if cursor:
            try:
                from datetime import datetime

                cursor_date = datetime.fromisoformat(cursor.replace("Z", "+00:00"))
                queryset = queryset.filter(created_at__lt=cursor_date)
            except (ValueError, TypeError):
                pass  # Invalid cursor, ignore

        # Get posts with limit + 1 to check if there's a next page
        posts = list(queryset[: limit + 1])
        has_next = len(posts) > limit

        if has_next:
            posts = posts[:limit]

        # Get next cursor
        next_cursor = None
        if has_next and posts:
            next_cursor = posts[-1].created_at.isoformat()

        # Serialize posts
        serializer = self.get_serializer(posts, many=True)

        # Calculate total posts count for user
        total_count = FeedPost.objects.filter(
            author_identity_id=str(request.user.id)
        ).count()

        response_data = {
            "posts": serializer.data,
            "has_next": has_next,
            "next_cursor": next_cursor,
            "total_count": total_count,
            "user_info": {
                "id": str(request.user.id),
                "username": request.user.username,
                "first_name": request.user.first_name,
                "last_name": request.user.last_name,
            },
        }

        return Response(response_data, status=status.HTTP_200_OK)


@api_view(["GET"])
@perm_classes([permissions.IsAuthenticated])
def explain_post_trending(request, post_id):
    """
    Explica en detalle el cálculo del trending score para un post específico

    GET: Obtener explicación detallada del algoritmo de trending
    """
    try:
        post = FeedPost.objects.get(id=post_id)

        # Obtener explicación del algoritmo
        explanation = post.explain_trending_score()

        # Agregar datos adicionales del post
        explanation.update(
            {
                "author": f"{post.author.first_name} {post.author.last_name}",
                "content_preview": (
                    post.content[:100] + "..."
                    if len(post.content) > 100
                    else post.content
                ),
                "created_at": post.created_at,
                "current_time": timezone.now(),
            }
        )

        # Explicación del algoritmo en términos entendibles
        explanation["algorithm_explanation"] = [
            "El trending score se calcula en base a los siguientes factores:",
            (
                f"1. Engagement bruto: likes ({explanation['likes']}) × 1 + "
                f"comentarios ({explanation['comments']}) × 2 + "
                f"compartidos ({explanation['shares']}) × 3 + "
                f"vistas ({explanation['views']}) × 0.1 = "
                f"{explanation['raw_engagement_score']}"
            ),
            (
                f"2. Factor de decaimiento: {explanation['time_decay_factor']} "
                f"(basado en {explanation['created_hours_ago']} horas desde "
                f"publicación y engagement de {explanation['engagement_weight']})"
            ),
            (
                f"3. Engagement con decaimiento: {explanation['engagement_score']} "
                f"(engagement bruto × factor de decaimiento)"
            ),
            (
                f"4. Boost por velocidad reciente: {explanation['velocity_boost']} "
                f"(inversamente proporcional a la raíz del tiempo)"
            ),
            (
                f"5. Trending score final: {explanation['trending_score']} "
                f"(80% engagement con decaimiento + 20% boost por velocidad)"
            ),
        ]

        return Response(explanation)

    except FeedPost.DoesNotExist:
        return Response(
            {"error": f"Post with ID {post_id} not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
