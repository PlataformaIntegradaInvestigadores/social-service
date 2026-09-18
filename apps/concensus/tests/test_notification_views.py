"""Unitarias de notification_views.py: listados de notificaciones fase 1/2,
topic-visited, combined-search, phase-one-completed, topic-reorder/tag."""

from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.concensus.domain.entities.notification import (
    NotificationPhaseOne,
    NotificationPhaseTwo,
)
from apps.concensus.domain.entities.topic import RecommendedTopic, TopicAddedUser
from apps.concensus.tests.testing_utils import mock_channel_layer
from apps.custom_auth.identity_principal import IdentityPrincipal

CHANNEL_LAYER_PATCH = (
    "apps.concensus.infrastructure.api.v1.views.notification_views.get_channel_layer"
)


class NotificationViewsTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = IdentityPrincipal(id="u1", username="ana", first_name="Ana")
        self.client.force_authenticate(user=self.user)
        self.group_id = "g1"


class TestNotificationListViews(NotificationViewsTestCase):
    def test_lista_fase_uno_del_grupo(self):
        NotificationPhaseOne.objects.create(
            user_identity_id="u1",
            group_identity_id=self.group_id,
            notification_type="new_topic",
            message="hola",
        )
        response = self.client.get(f"/api/v1/groups/{self.group_id}/notifications/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_lista_fase_dos_del_grupo(self):
        NotificationPhaseTwo.objects.create(
            user_identity_id="u1",
            group_identity_id=self.group_id,
            notification_type="topic_reorder",
            message="hola",
        )
        response = self.client.get(
            f"/api/v1/groups/{self.group_id}/notifications-phase-two/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class TestTopicVisitedView(NotificationViewsTestCase):
    def test_registra_visita_a_recommended_topic(self):
        topic = RecommendedTopic.objects.create(
            topic_name="IA", group_identity_id=self.group_id
        )
        with patch(CHANNEL_LAYER_PATCH, return_value=mock_channel_layer()):
            response = self.client.post(
                f"/api/v1/groups/{self.group_id}/topic-visited/",
                {"topic_id": topic.id},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(NotificationPhaseOne.objects.count(), 1)

    def test_registra_visita_a_topic_added_user(self):
        topic = RecommendedTopic.objects.create(
            topic_name="IA", group_identity_id=self.group_id
        )
        added = TopicAddedUser.objects.create(
            topic=topic, group_identity_id=self.group_id, user_identity_id="otro"
        )
        with patch(CHANNEL_LAYER_PATCH, return_value=mock_channel_layer()):
            response = self.client.post(
                f"/api/v1/groups/{self.group_id}/topic-visited/",
                {"topic_id": added.id},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_topic_inexistente_retorna_404(self):
        response = self.client.post(
            f"/api/v1/groups/{self.group_id}/topic-visited/",
            {"topic_id": 999},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_sin_topic_id_retorna_400(self):
        response = self.client.post(
            f"/api/v1/groups/{self.group_id}/topic-visited/", {}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestCombinedSearchView(NotificationViewsTestCase):
    def test_registra_busqueda_combinada(self):
        t1 = RecommendedTopic.objects.create(
            topic_name="IA", group_identity_id=self.group_id
        )
        t2 = RecommendedTopic.objects.create(
            topic_name="ML", group_identity_id=self.group_id
        )
        with patch(CHANNEL_LAYER_PATCH, return_value=mock_channel_layer()):
            response = self.client.post(
                f"/api/v1/groups/{self.group_id}/combined-search/",
                {"topics": [t1.id, t2.id]},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_topic_inexistente_retorna_404(self):
        response = self.client.post(
            f"/api/v1/groups/{self.group_id}/combined-search/",
            {"topics": [999]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_sin_topics_retorna_400(self):
        response = self.client.post(
            f"/api/v1/groups/{self.group_id}/combined-search/", {}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestPhaseOneCompletedView(NotificationViewsTestCase):
    def test_marca_fase_completada_y_notifica(self):
        with patch(CHANNEL_LAYER_PATCH, return_value=mock_channel_layer()):
            response = self.client.post(
                f"/api/v1/groups/{self.group_id}/phase-one-completed/",
                {},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(NotificationPhaseOne.objects.count(), 1)


class TestTopicReorderAndTagViews(NotificationViewsTestCase):
    def setUp(self):
        super().setUp()
        self.topic = RecommendedTopic.objects.create(
            topic_name="IA", group_identity_id=self.group_id
        )

    def test_reorder_topic(self):
        with patch(CHANNEL_LAYER_PATCH, return_value=mock_channel_layer()):
            response = self.client.post(
                f"/api/v1/groups/{self.group_id}/topic-reorder/",
                {
                    "topic_id": self.topic.id,
                    "original_position": 2,
                    "new_position": 1,
                },
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(NotificationPhaseTwo.objects.count(), 1)

    def test_reorder_sin_posiciones_retorna_400(self):
        response = self.client.post(
            f"/api/v1/groups/{self.group_id}/topic-reorder/",
            {"topic_id": self.topic.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_tag_topic(self):
        with patch(CHANNEL_LAYER_PATCH, return_value=mock_channel_layer()):
            response = self.client.post(
                f"/api/v1/groups/{self.group_id}/tag-topic/",
                {"topic_id": self.topic.id, "tag": "interesante"},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_tag_sin_tag_retorna_400(self):
        response = self.client.post(
            f"/api/v1/groups/{self.group_id}/tag-topic/",
            {"topic_id": self.topic.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_topic_inexistente_retorna_404(self):
        response = self.client.post(
            f"/api/v1/groups/{self.group_id}/tag-topic/",
            {"topic_id": 999, "tag": "x"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
