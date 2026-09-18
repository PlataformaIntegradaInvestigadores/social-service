from django.urls import path

from apps.feeds.infrastructure.api.v1.views.feed_views import (
    FeedView,
    UserInteractionView,
    UserPostsView,
    explain_post_trending,  # Nuevo endpoint de debug
    feed_recommendations,
    trending_posts,
    user_feed_stats,
)

urlpatterns = [
    # Main feed
    path("feed/", FeedView.as_view(), name="feed"),
    # User interactions
    path("interactions/", UserInteractionView.as_view(), name="user-interaction"),
    # User's own posts
    path("user/posts/", UserPostsView.as_view(), name="user-posts"),
    # Specialized feed endpoints
    path("feed/trending/", trending_posts, name="trending-posts"),
    path("feed/recommendations/", feed_recommendations, name="feed-recommendations"),
    # User stats
    path("feed/stats/", user_feed_stats, name="user-feed-stats"),
    # Debug endpoint para explicar algoritmo de trending
    path(
        "posts/<uuid:post_id>/explain-trending/",
        explain_post_trending,
        name="explain-post-trending",
    ),
]
