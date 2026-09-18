from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.concensus.domain.default_topics import DEFAULT_RECOMMENDED_TOPICS
from apps.concensus.domain.entities.topic import RecommendedTopic, Topic
from apps.concensus.infrastructure.api.v1.views.topic_views import (
    RandomRecommendedTopicView,
)


class TopicListIntegrationTests(APITestCase):
    def setUp(self):
        self.client = APIClient()

    def test_list_topics_filtered_by_group(self):
        Topic.objects.create(
            name="IA en salud publica",
            group_identity_id="group-1",
            group_snapshot={"id": "group-1", "name": "Grupo Uno", "title": ""},
        )
        Topic.objects.create(
            name="Topic de otro grupo",
            group_identity_id="group-2",
            group_snapshot={"id": "group-2", "name": "Grupo Dos", "title": ""},
        )

        response = self.client.get("/api/v1/topic/topic/", {"group_id": "group-1"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "IA en salud publica")
        self.assertEqual(data[0]["group_name"], "Grupo Uno")

    def test_list_topics_empty_for_unknown_group(self):
        Topic.objects.create(
            name="Topic existente",
            group_identity_id="group-1",
            group_snapshot={"id": "group-1", "name": "Grupo Uno", "title": ""},
        )

        response = self.client.get(
            "/api/v1/topic/topic/", {"group_id": "group-does-not-exist"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"], [])


class RecommendedTopicFallbackTests(APITestCase):
    def test_creates_five_fallback_topics_when_catalog_is_empty(self):
        view = RandomRecommendedTopicView()
        view.kwargs = {"group_id": "group-without-recommendations"}
        view._get_grs_topics = lambda _group_id: None

        topics = list(view.get_queryset())

        self.assertEqual(len(topics), 5)
        self.assertTrue(
            all(topic.topic_name in DEFAULT_RECOMMENDED_TOPICS for topic in topics)
        )
        self.assertTrue(
            all(
                topic.group_identity_id == "group-without-recommendations"
                for topic in topics
            )
        )
        self.assertEqual(
            RecommendedTopic.objects.filter(
                group_identity_id="group-without-recommendations"
            ).count(),
            5,
        )

    def test_reuses_topics_already_assigned_to_group(self):
        existing_topic = RecommendedTopic.objects.create(
            topic_name="Existing recommendation",
            group_identity_id="group-with-recommendations",
            group_snapshot={"id": "group-with-recommendations"},
        )
        view = RandomRecommendedTopicView()
        view.kwargs = {"group_id": "group-with-recommendations"}

        topics = list(view.get_queryset())

        self.assertEqual(topics, [existing_topic])
        self.assertEqual(RecommendedTopic.objects.count(), 1)
