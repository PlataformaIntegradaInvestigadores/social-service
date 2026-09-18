from django.urls import path

from apps.feeds.infrastructure.api.v1.views.comment_views import (
    CommentDetailView,
    CommentListCreateView,
    CommentRepliesView,
    CommentSearchView,
    CommentThreadView,
)

urlpatterns = [
    # Comments for posts
    path(
        "posts/<uuid:post_id>/comments/",
        CommentListCreateView.as_view(),
        name="comment-list-create",
    ),
    # Comment CRUD
    path("comments/<uuid:pk>/", CommentDetailView.as_view(), name="comment-detail"),
    path(
        "comments/<uuid:pk>/thread/", CommentThreadView.as_view(), name="comment-thread"
    ),
    # Comment replies
    path(
        "comments/<uuid:comment_id>/replies/",
        CommentRepliesView.as_view(),
        name="comment-replies",
    ),
    # Comment search
    path("comments/search/", CommentSearchView.as_view(), name="comment-search"),
]
