from django.urls import path

from apps.feeds.infrastructure.api.v1.views.feed_post_views import (
    FeedPostDetailView,
    FeedPostFileUploadView,
    FeedPostListCreateView,
    FeedPostSearchView,
    FeedPostStatsView,
)

urlpatterns = [
    # Post CRUD
    path("posts/", FeedPostListCreateView.as_view(), name="feed-post-list-create"),
    path("posts/<uuid:pk>/", FeedPostDetailView.as_view(), name="feed-post-detail"),
    path(
        "posts/<uuid:post_id>/files/",
        FeedPostFileUploadView.as_view(),
        name="feed-post-file-upload",
    ),
    path("posts/<uuid:pk>/stats/", FeedPostStatsView.as_view(), name="feed-post-stats"),
    # Post search
    path("posts/search/", FeedPostSearchView.as_view(), name="feed-post-search"),
]
