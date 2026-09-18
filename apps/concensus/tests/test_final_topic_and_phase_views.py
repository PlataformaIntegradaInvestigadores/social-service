"""Unitarias de SaveFinalTopicOrderView, UserCurrentPhaseView y
UpdateGroupPhaseView."""

from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.concensus.domain.entities.final_topic_order import FinalTopicOrder
from apps.concensus.domain.entities.topic import RecommendedTopic
from apps.concensus.domain.entities.user_phase import UserPhase
from apps.concensus.tests.testing_utils import mock_channel_layer
from apps.custom_auth.identity_principal import IdentityPrincipal


class ViewsTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = IdentityPrincipal(id="u1", username="ana", first_name="Ana")
        self.client.force_authenticate(user=self.user)
        self.group_id = "g1"


class TestSaveFinalTopicOrderView(ViewsTestCase):
    def test_guarda_el_orden_y_avanza_a_fase_2(self):
        topic = RecommendedTopic.objects.create(
            topic_name="IA", group_identity_id=self.group_id
        )
        with patch(
            "apps.concensus.infrastructure.api.v1.views.final_topic_views."
            "get_channel_layer",
            return_value=mock_channel_layer(),
        ):
            response = self.client.post(
                f"/api/v1/groups/{self.group_id}/save-final-topic-order/",
                {
                    "final_topic_orders": [
                        {"idTopic": topic.id, "posFinal": 1, "label": "bueno"}
                    ]
                },
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(FinalTopicOrder.objects.count(), 1)
        phase = UserPhase.objects.get(
            user_identity_id="u1", group_identity_id=self.group_id
        )
        self.assertEqual(phase.phase, 2)

    def test_sin_ordenes_retorna_400(self):
        response = self.client.post(
            f"/api/v1/groups/{self.group_id}/save-final-topic-order/",
            {"final_topic_orders": []},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_borra_el_orden_previo_del_usuario_antes_de_guardar(self):
        topic = RecommendedTopic.objects.create(
            topic_name="IA", group_identity_id=self.group_id
        )
        FinalTopicOrder.objects.create(
            idGroup_identity_id=self.group_id,
            idUser_identity_id="u1",
            idTopic=topic,
            posFinal=5,
        )
        with patch(
            "apps.concensus.infrastructure.api.v1.views.final_topic_views."
            "get_channel_layer",
            return_value=mock_channel_layer(),
        ):
            self.client.post(
                f"/api/v1/groups/{self.group_id}/save-final-topic-order/",
                {"final_topic_orders": [{"idTopic": topic.id, "posFinal": 1}]},
                format="json",
            )
        self.assertEqual(FinalTopicOrder.objects.count(), 1)
        self.assertEqual(FinalTopicOrder.objects.first().posFinal, 1)


class TestUserCurrentPhaseView(ViewsTestCase):
    def test_sin_registro_retorna_phase_0(self):
        response = self.client.get(f"/api/v1/groups/{self.group_id}/current-phase/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"phase": 0})

    def test_con_registro_retorna_la_fase(self):
        UserPhase.objects.create(
            user_identity_id="u1", group_identity_id=self.group_id, phase=2
        )
        response = self.client.get(f"/api/v1/groups/{self.group_id}/current-phase/")
        self.assertEqual(response.data["phase"], 2)


class TestUpdateGroupPhaseView(ViewsTestCase):
    def test_actualiza_la_fase_de_todos_los_usuarios(self):
        UserPhase.objects.create(
            user_identity_id="u1", group_identity_id=self.group_id, phase=1
        )
        UserPhase.objects.create(
            user_identity_id="u2", group_identity_id=self.group_id, phase=1
        )
        with patch(
            "apps.concensus.infrastructure.api.v1.views.user_phase_views."
            "get_channel_layer",
            return_value=mock_channel_layer(),
        ):
            response = self.client.post(
                f"/api/v1/groups/{self.group_id}/update-phase/",
                {"phase": 3},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(UserPhase.objects.values_list("phase", flat=True)), {3})

    def test_sin_usuarios_en_el_grupo_retorna_404(self):
        response = self.client.post(
            f"/api/v1/groups/{self.group_id}/update-phase/",
            {"phase": 3},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
