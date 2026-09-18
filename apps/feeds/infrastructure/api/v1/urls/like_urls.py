from django.urls import path

from apps.feeds.infrastructure.api.v1.views.like_views import (
    LikeToggleView,
    UserLikesView,
    comment_likes,
    like_comment,
    like_post,
    post_likes,
)

urlpatterns = [
    # Like toggle (generic)
    path("likes/toggle/", LikeToggleView.as_view(), name="like-toggle"),
    # User likes
    path("likes/user/", UserLikesView.as_view(), name="user-likes"),
    # Specific like endpoints
    path("posts/<uuid:post_id>/like/", like_post, name="like-post"),
    path("comments/<uuid:comment_id>/like/", like_comment, name="like-comment"),
    # Like lists
    path("posts/<uuid:post_id>/likes/", post_likes, name="post-likes"),
    path("comments/<uuid:comment_id>/likes/", comment_likes, name="comment-likes"),
]
