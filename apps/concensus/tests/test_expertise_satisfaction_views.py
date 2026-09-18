"""Unitarias de UserExpertiseView, UserSatisfactionView,
LoadUserSatisfactionNotificationsView y LoadSatisfactionCountsView."""

from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.concensus.domain.entities.topic import RecommendedTopic, TopicAddedUser
from apps.concensus.domain.entities.user_expertice import UserExpertise
from apps.concensus.domain.entities.user_satisfaction import UserSatisfaction
from apps.concensus.tests.testing_utils import mock_channel_layer
from apps.custom_auth.identity_principal import IdentityPrincipal

EXPERTISE_CHANNEL_PATCH = (
    "apps.concensus.infrastructure.api.v1.views.user_expertice_views."
    "get_channel_layer"
)
SATISFACTION_CHANNEL_PATCH = (
    "apps.concensus.infrastructure.api.v1.views.user_satisfaction_views."
    "get_channel_layer"
)


class ViewsTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = IdentityPrincipal(id="u1", username="ana", first_name="Ana")
        self.client.force_authenticate(user=self.user)
        self.group_id = "g1"


class TestUserExpertiseView(ViewsTestCase):
    def test_registra_experticia_junior(self):
        topic = RecommendedTopic.objects.create(
            topic_name="IA", group_identity_id=self.group_id
        )
        with patch(EXPERTISE_CHANNEL_PATCH, return_value=mock_channel_layer()):
            response = self.client.post(
                f"/api/v1/groups/{self.group_id}/user-expertise/",
                {"topic_id": topic.id, "expertise_level": 20},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ue = UserExpertise.objects.get()
        self.assertEqual(ue.expertise_level, 2)

    def test_registra_experticia_experto_via_topic_added_user(self):
        topic = RecommendedTopic.objects.create(
            topic_name="IA", group_identity_id=self.group_id
        )
        added = TopicAddedUser.objects.create(
            topic=topic, group_identity_id=self.group_id, user_identity_id="otro"
        )
        with patch(EXPERTISE_CHANNEL_PATCH, return_value=mock_channel_layer()):
            response = self.client.post(
                f"/api/v1/groups/{self.group_id}/user-expertise/",
                {"topic_id": added.id, "expertise_level": 95},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_sin_topic_id_retorna_400(self):
        response = self.client.post(
            f"/api/v1/groups/{self.group_id}/user-expertise/", {}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_expertise_level_no_numerico_retorna_400(self):
        topic = RecommendedTopic.objects.create(
            topic_name="IA", group_identity_id=self.group_id
        )
        response = self.client.post(
            f"/api/v1/groups/{self.group_id}/user-expertise/",
            {"topic_id": topic.id, "expertise_level": "no-numero"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_topic_inexistente_retorna_404(self):
        response = self.client.post(
            f"/api/v1/groups/{self.group_id}/user-expertise/",
            {"topic_id": 999, "expertise_level": 5},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TestUserSatisfactionView(ViewsTestCase):
    def test_registra_satisfaccion_y_cuenta(self):
        with patch(SATISFACTION_CHANNEL_PATCH, return_value=mock_channel_layer()):
            response = self.client.post(
                f"/api/v1/groups/{self.group_id}/user_satisfaction/",
                {"satisfaction_level": "Satisfied"},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(UserSatisfaction.objects.count(), 1)

    def test_sin_nivel_retorna_400(self):
        response = self.client.post(
            f"/api/v1/groups/{self.group_id}/user_satisfaction/", {}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestLoadUserSatisfactionNotificationsView(ViewsTestCase):
    def test_lista_por_grupo(self):
        UserSatisfaction.objects.create(
            user_identity_id="u1",
            group_identity_id=self.group_id,
            satisfaction_level="Satisfied",
            message="ok",
        )
        response = self.client.get(
            f"/api/v1/groups/{self.group_id}/satisfaction/notifications/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class TestLoadSatisfactionCountsView(ViewsTestCase):
    def test_cuenta_por_nivel(self):
        UserSatisfaction.objects.create(
            user_identity_id="u1",
            group_identity_id=self.group_id,
            satisfaction_level="Satisfied",
            message="ok",
        )
        UserSatisfaction.objects.create(
            user_identity_id="u2",
            group_identity_id=self.group_id,
            satisfaction_level="Satisfied",
            message="ok",
        )
        response = self.client.get(
            f"/api/v1/groups/{self.group_id}/satisfaction-counts/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["counts"]["Satisfied"], 2)
