from django.urls import path

from apps.feeds.domain.services.moderation_service import COMMENT, POST
from apps.feeds.infrastructure.api.v1.views.moderation_views import (
    ModerationMeView,
    ReportContentView,
    ReviewCaseView,
    ReviewDecisionView,
    ReviewQueueView,
)

urlpatterns = [
    path(
        "posts/<uuid:pk>/report/",
        ReportContentView.as_view(content_type=POST),
        name="post-report",
    ),
    path(
        "comments/<uuid:pk>/report/",
        ReportContentView.as_view(content_type=COMMENT),
        name="comment-report",
    ),
    path("moderation/me/", ModerationMeView.as_view(), name="moderation-me"),
    path(
        "moderation/review-queue/",
        ReviewQueueView.as_view(),
        name="moderation-review-queue",
    ),
    path(
        "moderation/review-queue/<int:case_id>/",
        ReviewCaseView.as_view(),
        name="moderation-review-case",
    ),
    path(
        "moderation/review-queue/<int:case_id>/decision/",
        ReviewDecisionView.as_view(),
        name="moderation-review-decision",
    ),
]
