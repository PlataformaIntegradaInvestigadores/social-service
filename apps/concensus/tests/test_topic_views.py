"""Unitarias de las vistas de topic.py no cubiertas por apps/concensus/tests.py:
TopicViewSet.list, RecommendedTopicsByGroupView, FinalTopicsVotedByUserView,
TopicsAddedByGroupView, GroupTopicsView, AddTopicView, y las rutas del GRS en
RandomRecommendedTopicView (fallback ya cubierto en tests.py)."""

from unittest.mock import MagicMock, patch

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.concensus.domain.entities.final_topic_order import FinalTopicOrder
from apps.concensus.domain.entities.topic import RecommendedTopic, Topic, TopicAddedUser
from apps.concensus.domain.entities.user_phase import UserPhase
from apps.concensus.tests.testing_utils import mock_channel_layer
from apps.custom_auth.identity_principal import IdentityPrincipal

CHANNEL_LAYER_PATCH = (
    "apps.concensus.infrastructure.api.v1.views.topic_views.get_channel_layer"
)


class TopicViewsTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = IdentityPrincipal(id="u1", username="ana", first_name="Ana")
        self.client.force_authenticate(user=self.user)
        self.group_id = "g1"


class TestTopicViewSetList(TopicViewsTestCase):
    def test_lista_topics_del_grupo(self):
        Topic.objects.create(
            name="IA", group_identity_id=self.group_id, group_snapshot={}
        )
        Topic.objects.create(
            name="Otro grupo", group_identity_id="g2", group_snapshot={}
        )
        response = self.client.get(f"/api/v1/topic/topic/?group_id={self.group_id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]), 1)


class TestRecommendedTopicsByGroupView(TopicViewsTestCase):
    def test_lista_ordenada_por_nombre(self):
        RecommendedTopic.objects.create(
            topic_name="Zeta", group_identity_id=self.group_id
        )
        RecommendedTopic.objects.create(
            topic_name="Alfa", group_identity_id=self.group_id
        )
        response = self.client.get(
            f"/api/v1/groups/{self.group_id}/recommended-topics/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([t["topic_name"] for t in response.data], ["Alfa", "Zeta"])


class TestTopicsAddedByGroupView(TopicViewsTestCase):
    def test_lista_topics_agregados_por_usuarios(self):
        topic = RecommendedTopic.objects.create(
            topic_name="IA", group_identity_id=self.group_id
        )
        TopicAddedUser.objects.create(
            topic=topic,
            group_identity_id=self.group_id,
            user_identity_id="u1",
        )
        response = self.client.get(f"/api/v1/groups/{self.group_id}/added-topics/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class TestGroupTopicsView(TopicViewsTestCase):
    def test_retorna_recomendados_y_agregados(self):
        topic = RecommendedTopic.objects.create(
            topic_name="IA", group_identity_id=self.group_id
        )
        TopicAddedUser.objects.create(
            topic=topic, group_identity_id=self.group_id, user_identity_id="u1"
        )
        response = self.client.get(f"/api/v1/groups/{self.group_id}/topics/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["recommended_topics"]), 1)
        self.assertEqual(len(response.data["added_topics"]), 1)


class TestFinalTopicsVotedByUserView(TopicViewsTestCase):
    def test_retorna_topics_con_tags_separados(self):
        topic = RecommendedTopic.objects.create(
            topic_name="IA", group_identity_id=self.group_id
        )
        FinalTopicOrder.objects.create(
            idGroup_identity_id=self.group_id,
            idUser_identity_id="u1",
            idTopic=topic,
            posFinal=1,
            label="bueno, interesante",
        )
        response = self.client.get(f"/api/v1/groups/{self.group_id}/finals-topics/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"][0]["tags"], ["bueno", "interesante"])

    def test_sin_label_retorna_tags_vacios(self):
        topic = RecommendedTopic.objects.create(
            topic_name="IA", group_identity_id=self.group_id
        )
        FinalTopicOrder.objects.create(
            idGroup_identity_id=self.group_id,
            idUser_identity_id="u1",
            idTopic=topic,
            posFinal=1,
        )
        response = self.client.get(f"/api/v1/groups/{self.group_id}/finals-topics/")
        self.assertEqual(response.data["data"][0]["tags"], [])


class TestAddTopicView(TopicViewsTestCase):
    def test_agrega_topic_nuevo(self):
        with patch(CHANNEL_LAYER_PATCH, return_value=mock_channel_layer()):
            response = self.client.post(
                f"/api/v1/groups/{self.group_id}/add-topic/",
                {"topic": "Nuevo Topic"},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(RecommendedTopic.objects.count(), 1)
        self.assertEqual(TopicAddedUser.objects.count(), 1)

    def test_sin_topic_retorna_400(self):
        response = self.client.post(
            f"/api/v1/groups/{self.group_id}/add-topic/", {}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rechaza_si_ya_hay_usuarios_en_fase_2(self):
        UserPhase.objects.create(
            group_identity_id=self.group_id, user_identity_id="otro", phase=2
        )
        response = self.client.post(
            f"/api/v1/groups/{self.group_id}/add-topic/",
            {"topic": "Nuevo"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_rechaza_si_el_usuario_ya_agrego_un_topic(self):
        topic = RecommendedTopic.objects.create(
            topic_name="Existente", group_identity_id=self.group_id
        )
        TopicAddedUser.objects.create(
            topic=topic, group_identity_id=self.group_id, user_identity_id="u1"
        )
        response = self.client.post(
            f"/api/v1/groups/{self.group_id}/add-topic/",
            {"topic": "Otro"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_rechaza_topic_duplicado_en_el_grupo(self):
        topic = RecommendedTopic.objects.create(
            topic_name="IA", group_identity_id=self.group_id
        )
        TopicAddedUser.objects.create(
            topic=topic, group_identity_id=self.group_id, user_identity_id="otro"
        )
        response = self.client.post(
            f"/api/v1/groups/{self.group_id}/add-topic/",
            {"topic": "IA"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reusa_recommended_topic_existente_sin_added_user(self):
        RecommendedTopic.objects.create(
            topic_name="IA", group_identity_id=self.group_id
        )
        with patch(CHANNEL_LAYER_PATCH, return_value=mock_channel_layer()):
            response = self.client.post(
                f"/api/v1/groups/{self.group_id}/add-topic/",
                {"topic": "IA"},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(RecommendedTopic.objects.count(), 1)


class TestRandomRecommendedTopicViewGrs(TopicViewsTestCase):
    @patch(
        "apps.concensus.infrastructure.api.v1.views.topic_views."
        "RandomRecommendedTopicView._get_grs_topics"
    )
    def test_usa_topics_del_grs_cuando_hay_vinculo(self, mock_get_grs):
        # Sin group_identity_id todavia: si lo tuviera, get_queryset() lo
        # encontraria como "already_assigned" y nunca llegaria a llamar
        # _get_grs_topics (el mock quedaria sin ejercitar).
        mock_get_grs.return_value = [
            RecommendedTopic.objects.create(topic_name="GRS Topic")
        ]
        response = self.client.get(f"/api/v1/groups/{self.group_id}/topics/random/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["topic_name"], "GRS Topic")

    @patch(
        "apps.concensus.infrastructure.api.v1.views.topic_views."
        "get_identity_group_detail"
    )
    def test_get_grs_topics_sin_detalle_de_grupo_retorna_none(self, mock_detail):
        mock_detail.return_value = None
        from apps.concensus.infrastructure.api.v1.views.topic_views import (
            RandomRecommendedTopicView,
        )

        view = RandomRecommendedTopicView()
        view.request = MagicMock(headers={})
        self.assertIsNone(view._get_grs_topics(self.group_id))

    @patch(
        "apps.concensus.infrastructure.api.v1.views.topic_views."
        "get_identity_group_detail"
    )
    def test_get_grs_topics_sin_scopus_ids_retorna_none(self, mock_detail):
        mock_detail.return_value = {"users": [{"scopus_id": None}]}
        from apps.concensus.infrastructure.api.v1.views.topic_views import (
            RandomRecommendedTopicView,
        )

        view = RandomRecommendedTopicView()
        view.request = MagicMock(headers={})
        self.assertIsNone(view._get_grs_topics(self.group_id))

    @patch("apps.concensus.infrastructure.api.v1.views.topic_views.fetch_grs_topics")
    @patch(
        "apps.concensus.infrastructure.api.v1.views.topic_views."
        "get_identity_group_detail"
    )
    def test_get_grs_topics_crea_recommended_topics(self, mock_detail, mock_fetch):
        mock_detail.return_value = {"users": [{"scopus_id": "123"}]}
        mock_fetch.return_value = ["Tema A", "Tema B"]
        from apps.concensus.infrastructure.api.v1.views.topic_views import (
            RandomRecommendedTopicView,
        )

        view = RandomRecommendedTopicView()
        view.request = MagicMock(headers={})
        result = view._get_grs_topics(self.group_id)
        self.assertEqual(len(result), 2)
        self.assertEqual(RecommendedTopic.objects.count(), 2)
