from django.http import JsonResponse
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.concensus.infrastructure.api.v1.views.debate_message_views import (
    MessageHistoryView,
)
from apps.concensus.infrastructure.api.v1.views.debate_posture_views import (
    PostureViewSet,
)
from apps.concensus.infrastructure.api.v1.views.debate_reaction_views import (
    ReactionViewSet,
)
from apps.concensus.infrastructure.api.v1.views.debate_statistics_views import (
    StatisticsView,
)
from apps.concensus.infrastructure.api.v1.views.debate_views import DebateViewSet
from apps.concensus.infrastructure.api.v1.views.final_topic_views import (
    SaveFinalTopicOrderView,
)
from apps.concensus.infrastructure.api.v1.views.notification_views import (
    CombinedSearchView,
    NotificationListView,
    NotificationPhaseTwoListView,
    PhaseOneCompletedView,
    TopicReorderView,
    TopicTagView,
    TopicVisitedView,
)
from apps.concensus.infrastructure.api.v1.views.result_concensus_views import (
    ConsensusCalculationByVotingTypeView,
    ExecuteConsensusCalculationsView,
)
from apps.concensus.infrastructure.api.v1.views.topic_views import (
    AddTopicView,
    FinalTopicsVotedByUserView,
    GroupTopicsView,
    RandomRecommendedTopicView,
    RecommendedTopicsByGroupView,
    TopicsAddedByGroupView,
)
from apps.concensus.infrastructure.api.v1.views.user_expertice_views import (
    UserExpertiseView,
)
from apps.concensus.infrastructure.api.v1.views.user_phase_views import (
    UpdateGroupPhaseView,
    UserCurrentPhaseView,
)
from apps.concensus.infrastructure.api.v1.views.user_satisfaction_views import (
    LoadSatisfactionCountsView,
    LoadUserSatisfactionNotificationsView,
    UserSatisfactionView,
)


def test_view(_request):
    return JsonResponse({"message": "Test URL of concensus works!"})


# 1. Ruta para listar y crear debates
debate_list = DebateViewSet.as_view(
    {
        "get": "list",  # Permite listar todos los debates de un grupo
        "post": "create",  # Permite crear un nuevo debate en un grupo
    }
)

# 2. Ruta para obtener y eliminar un debate específico
debate_detail = DebateViewSet.as_view(
    {
        "get": "retrieve",  # Permite obtener los detalles de un debate específico
        # Permite eliminar un debate específico si pertenece al grupo
        "delete": "destroy",
    }
)

# 3. Ruta para cerrar un debate específico
debate_close = DebateViewSet.as_view(
    {
        "post": "close",  # Permite cerrar un debate de forma manual
    }
)

# 4. Ruta para validar el estado de un debate
debate_validate_status = DebateViewSet.as_view(
    {
        # Permite verificar si un debate está abierto o cerrado
        "get": "validate_status",
    }
)

router = DefaultRouter()
router.register(r"postures", PostureViewSet, basename="postures")
router.register(r"reactions", ReactionViewSet, basename="reactions")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "topic/",
        include("apps.concensus.infrastructure.api.v1.urls.topic_url"),
        name="topic",
    ),
    path(
        "groups/<str:group_id>/topics/random/",
        RandomRecommendedTopicView.as_view(),
        name="random-recommended-topic",
    ),
    path(
        "groups/<str:group_id>/recommended-topics/",
        RecommendedTopicsByGroupView.as_view(),
        name="recommended-topics-by-group",
    ),
    path(
        "groups/<str:group_id>/added-topics/",
        TopicsAddedByGroupView.as_view(),
        name="topics-added-by-group",
    ),
    path(
        "groups/<str:group_id>/topics/", GroupTopicsView.as_view(), name="group-topics"
    ),
    path("groups/<str:group_id>/add-topic/", AddTopicView.as_view(), name="add-topic"),
    path(
        "groups/<str:group_id>/notifications/",
        NotificationListView.as_view(),
        name="group-notifications",
    ),
    path(
        "groups/<str:group_id>/notifications-phase-two/",
        NotificationPhaseTwoListView.as_view(),
        name="group-notifications-phase-two",
    ),
    path(
        "groups/<str:group_id>/topic-visited/",
        TopicVisitedView.as_view(),
        name="topic-visited",
    ),
    path(
        "groups/<str:group_id>/combined-search/",
        CombinedSearchView.as_view(),
        name="combined-search",
    ),
    path(
        "groups/<str:group_id>/phase-one-completed/",
        PhaseOneCompletedView.as_view(),
        name="phase-one-completed",
    ),
    path(
        "groups/<str:group_id>/user-expertise/",
        UserExpertiseView.as_view(),
        name="user-expertise",
    ),
    path(
        "groups/<str:group_id>/topic-reorder/",
        TopicReorderView.as_view(),
        name="topic-reorder",
    ),
    path("groups/<str:group_id>/tag-topic/", TopicTagView.as_view(), name="tag-topic"),
    path(
        "groups/<str:group_id>/save-final-topic-order/",
        SaveFinalTopicOrderView.as_view(),
        name="save-final-topic-order",
    ),
    path(
        "groups/<str:group_id>/execute_consensus_calculations/",
        ExecuteConsensusCalculationsView.as_view(),
        name="execute_consensus_calculations",
    ),
    path(
        "groups/<str:group_id>/execute_consensus_calculations/<str:voting_type>/",
        ConsensusCalculationByVotingTypeView.as_view(),
        name="execute_consensus_calculations_by_voting_type",
    ),
    path(
        "groups/<str:group_id>/user_satisfaction/",
        UserSatisfactionView.as_view(),
        name="user_satisfaction",
    ),
    path(
        "groups/<str:group_id>/satisfaction/notifications/",
        LoadUserSatisfactionNotificationsView.as_view(),
        name="load-user-satisfaction-notifications",
    ),
    path(
        "groups/<str:group_id>/satisfaction-counts/",
        LoadSatisfactionCountsView.as_view(),
        name="satisfaction-counts",
    ),
    path(
        "groups/<str:group_id>/current-phase/",
        UserCurrentPhaseView.as_view(),
        name="current-phase",
    ),
    path(
        "groups/<str:group_id>/update-phase/",
        UpdateGroupPhaseView.as_view(),
        name="update-group-phase",
    ),
    path(
        "groups/<str:group_id>/finals-topics/",
        FinalTopicsVotedByUserView.as_view(),
        name="finals-topics-voted",
    ),
    # Ruta para listar o crear debates de un grupo específico
    path("groups/<str:group_id>/debates/", debate_list, name="debate-list"),
    # Ruta para obtener, actualizar o eliminar un debate específico
    path(
        "groups/<str:group_id>/debates/<int:pk>/", debate_detail, name="debate-detail"
    ),
    # Ruta para cerrar manualmente un debate específico
    path(
        "groups/<str:group_id>/debates/<int:pk>/close/",
        debate_close,
        name="debate-close",
    ),
    # Ruta para validar el estado de un debate y cerrarlo automáticamente si ha expirado
    path(
        "groups/<str:group_id>/debates/<int:pk>/validate-status/",
        debate_validate_status,
        name="debate-validate-status",
    ),
    path(
        "debates/<int:debate_id>/statistics/",
        StatisticsView.as_view(),
        name="debate_statistics",
    ),
    path(
        "messages/<int:debate_id>/",
        MessageHistoryView.as_view(),
        name="message-history",
    ),
]
