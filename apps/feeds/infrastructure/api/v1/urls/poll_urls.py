from django.urls import path

from apps.feeds.infrastructure.api.v1.views.poll_views import (
    get_poll_details,
    remove_vote,
    vote_poll,
)

urlpatterns = [
    # Polls
    path("polls/<str:poll_id>/", get_poll_details, name="poll-detail"),
    path("polls/<str:poll_id>/vote/", vote_poll, name="poll-vote"),
    path("polls/<str:poll_id>/remove-vote/", remove_vote, name="poll-remove-vote"),
]
