"""Unitarias de result_concensus_views.py: get_user_data, VotingAlgorithms
(Schulze + posicional ponderado por experticia) y las dos vistas que las
orquestan (persistiendo ConsensusResult o no, segun el endpoint)."""

from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.concensus.domain.entities.final_topic_order import FinalTopicOrder
from apps.concensus.domain.entities.result_concensus import ConsensusResult
from apps.concensus.domain.entities.topic import RecommendedTopic
from apps.concensus.domain.entities.user_expertice import UserExpertise
from apps.concensus.domain.entities.user_phase import UserPhase
from apps.concensus.infrastructure.api.v1.views.result_concensus_views import (
    VotingAlgorithms,
    get_user_data,
)
from apps.concensus.tests.testing_utils import mock_channel_layer
from apps.custom_auth.identity_principal import IdentityPrincipal

CHANNEL_LAYER_PATCH = (
    "apps.concensus.infrastructure.api.v1.views.result_concensus_views."
    "get_channel_layer"
)


class TestVotingAlgorithmsPositional(APITestCase):
    def test_ordena_por_puntaje_ponderado_por_experticia(self):
        # posFinal mas alto = mas preferido (ver test de Schulze abajo).
        positions = {"IA": {"u1": 2, "u2": 1}, "ML": {"u1": 1, "u2": 2}}
        expertise = {"IA": {"u1": 10, "u2": 1}, "ML": {"u1": 10, "u2": 1}}
        result = VotingAlgorithms.calculate_positional_voting(
            ["IA", "ML"], ["u1", "u2"], positions, expertise
        )
        # IA gana: u1 (experto, peso 10) la prefirio por sobre u2 (peso 1).
        self.assertEqual(result[0][0], "IA")

    def test_topic_sin_expertise_asume_peso_1(self):
        positions = {"IA": {"u1": 1}}
        expertise = {"IA": {}}
        result = VotingAlgorithms.calculate_positional_voting(
            ["IA"], ["u1"], positions, expertise
        )
        self.assertEqual(result[0][1], 1.0)


class TestVotingAlgorithmsSchulze(APITestCase):
    def test_topic_preferido_por_todos_gana(self):
        # posFinal mas alto = mas preferido (ver get_user_data/topic_views).
        positions = {
            "IA": {"u1": 2, "u2": 2},
            "ML": {"u1": 1, "u2": 1},
        }
        result = VotingAlgorithms.schulze_voting_algorithm(positions, ["IA", "ML"])
        self.assertEqual(result[0][0], "IA")

    def test_empate_produce_fuerza_cero_para_ambos(self):
        positions = {"IA": {"u1": 1}, "ML": {"u1": 1}}
        result = VotingAlgorithms.schulze_voting_algorithm(positions, ["IA", "ML"])
        self.assertEqual({r[1] for r in result}, {0})


class TestGetUserData(APITestCase):
    def test_sin_usuarios_completos_lanza_value_error(self):
        with self.assertRaises(ValueError):
            get_user_data("g1")

    def test_agrupa_posiciones_y_experticia_por_topico(self):
        UserPhase.objects.create(user_identity_id="u1", group_identity_id="g1", phase=2)
        topic = RecommendedTopic.objects.create(topic_name="IA", group_identity_id="g1")
        FinalTopicOrder.objects.create(
            idGroup_identity_id="g1", idUser_identity_id="u1", idTopic=topic, posFinal=1
        )
        UserExpertise.objects.create(
            user_identity_id="u1",
            group_identity_id="g1",
            topic=topic,
            expertise_level=5,
        )

        (
            topics,
            topic_names,
            completed_users,
            positions_data,
            expertise_data,
            labels_data,
        ) = get_user_data("g1")

        self.assertEqual(topic_names, ["IA"])
        self.assertEqual(completed_users, ["u1"])
        self.assertEqual(positions_data["IA"]["u1"], 1)
        self.assertEqual(expertise_data["IA"]["u1"], 5)

    def test_usuario_sin_experticia_registrada_asume_nivel_1(self):
        UserPhase.objects.create(user_identity_id="u1", group_identity_id="g1", phase=2)
        RecommendedTopic.objects.create(topic_name="IA", group_identity_id="g1")

        _, _, _, _, expertise_data, _ = get_user_data("g1")

        self.assertEqual(expertise_data["IA"]["u1"], 1)


class ExecuteConsensusTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=IdentityPrincipal(id="u1", username="ana"))
        self.group_id = "g1"

    def _setup_completed_user(self):
        UserPhase.objects.create(
            user_identity_id="u1", group_identity_id=self.group_id, phase=2
        )
        topic = RecommendedTopic.objects.create(
            topic_name="IA", group_identity_id=self.group_id
        )
        FinalTopicOrder.objects.create(
            idGroup_identity_id=self.group_id,
            idUser_identity_id="u1",
            idTopic=topic,
            posFinal=1,
        )
        return topic


class TestExecuteConsensusCalculationsView(ExecuteConsensusTestCase):
    def test_persiste_consensus_result_y_notifica(self):
        self._setup_completed_user()
        with patch(CHANNEL_LAYER_PATCH, return_value=mock_channel_layer()):
            response = self.client.get(
                f"/api/v1/groups/{self.group_id}/execute_consensus_calculations/"
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(ConsensusResult.objects.count(), 1)

    def test_sin_usuarios_completos_retorna_400(self):
        response = self.client.get(
            f"/api/v1/groups/{self.group_id}/execute_consensus_calculations/"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestConsensusCalculationByVotingTypeView(ExecuteConsensusTestCase):
    def test_tipo_de_voto_invalido_retorna_400(self):
        response = self.client.get(
            f"/api/v1/groups/{self.group_id}/execute_consensus_calculations/"
            "no-valido/"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_positional_voting_no_persiste(self):
        self._setup_completed_user()
        response = self.client.get(
            f"/api/v1/groups/{self.group_id}/execute_consensus_calculations/"
            "non-positional-voting/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(ConsensusResult.objects.count(), 0)
        self.assertEqual(response.data["results"][0]["labels"], ["There aren't labels"])
