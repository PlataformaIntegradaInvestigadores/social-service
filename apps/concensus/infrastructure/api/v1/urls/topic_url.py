from rest_framework.routers import DefaultRouter

from apps.concensus.infrastructure.api.v1.views.topic_views import TopicViewSet

router = DefaultRouter()
router.register("topic", TopicViewSet, basename="topic")
urlpatterns = router.urls
