"""Unitarias de PostureViewSet y ReactionViewSet (router DRF en /api/v1/postures/
y /api/v1/reactions/): crear/actualizar postura de debate (bloqueado si el
debate esta cerrado) y crear/borrar reacciones a mensajes (solo el autor)."""

from datetime import timedelta
from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.concensus.domain.entities.debate import Debate
from apps.concensus.domain.entities.debate_message import Message
from apps.concensus.domain.entities.debate_participant_posture import UserPosture
from apps.concensus.domain.entities.debate_reaction import Reaction
from apps.concensus.tests.testing_utils import mock_channel_layer
from apps.custom_auth.identity_principal import IdentityPrincipal

CHANNEL_LAYER_PATCH = (
    "apps.concensus.infrastructure.api.v1.views.debate_views.get_channel_layer"
)


class PostureTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = IdentityPrincipal(id="u1", username="ana", first_name="Ana")
        self.client.force_authenticate(user=self.user)
        self.debate = Debate.objects.create(
            title="T1",
            description="d",
            end_time=timedelta(hours=1),
            group_identity_id="g1",
            group_snapshot={"id": "g1"},
        )


class TestPostureCreate(PostureTestCase):
    def test_crea_postura_y_notifica(self):
        with patch(CHANNEL_LAYER_PATCH, return_value=mock_channel_layer()):
            response = self.client.post(
                "/api/v1/postures/",
                {"debate": self.debate.id, "posture": "agree"},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(UserPosture.objects.count(), 1)
        self.assertEqual(UserPosture.objects.first().user_identity_id, "u1")


class TestPostureUpdate(PostureTestCase):
    def test_actualiza_postura_si_debate_abierto(self):
        posture = UserPosture.objects.create(
            debate=self.debate, posture="agree", user_identity_id="u1"
        )
        with patch(CHANNEL_LAYER_PATCH, return_value=mock_channel_layer()):
            response = self.client.put(
                f"/api/v1/postures/{posture.id}/",
                {"debate": self.debate.id, "posture": "disagree"},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        posture.refresh_from_db()
        self.assertEqual(posture.posture, "disagree")

    def test_rechaza_si_debate_cerrado(self):
        self.debate.is_closed = True
        self.debate.save()
        posture = UserPosture.objects.create(
            debate=self.debate, posture="agree", user_identity_id="u1"
        )
        response = self.client.put(
            f"/api/v1/postures/{posture.id}/",
            {"debate": self.debate.id, "posture": "disagree"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestPostureRetrieve(PostureTestCase):
    def test_retorna_posturas_del_usuario(self):
        UserPosture.objects.create(
            debate=self.debate, posture="agree", user_identity_id="u1"
        )
        response = self.client.get("/api/v1/postures/u1/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_usuario_sin_posturas_retorna_404(self):
        response = self.client.get("/api/v1/postures/no-existe/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TestPostureByDebate(PostureTestCase):
    def test_retorna_la_postura_del_usuario_en_el_debate(self):
        UserPosture.objects.create(
            debate=self.debate, posture="agree", user_identity_id="u1"
        )
        response = self.client.get(f"/api/v1/postures/debate/{self.debate.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_sin_postura_retorna_404(self):
        response = self.client.get(f"/api/v1/postures/debate/{self.debate.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ReactionTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = IdentityPrincipal(id="u1", username="ana")
        self.client.force_authenticate(user=self.user)
        debate = Debate.objects.create(
            title="T1",
            description="d",
            end_time=timedelta(hours=1),
            group_identity_id="g1",
            group_snapshot={"id": "g1"},
        )
        self.message = Message.objects.create(
            debate=debate, text="hola", user_identity_id="u2"
        )


class TestReactionCreate(ReactionTestCase):
    def test_crea_reaccion(self):
        response = self.client.post(
            "/api/v1/reactions/", {"message": self.message.id}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Reaction.objects.count(), 1)


class TestReactionDestroy(ReactionTestCase):
    def test_autor_puede_borrar_su_reaccion(self):
        reaction = Reaction.objects.create(message=self.message, user_identity_id="u1")
        response = self.client.delete(f"/api/v1/reactions/{reaction.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_otro_usuario_no_puede_borrarla(self):
        reaction = Reaction.objects.create(
            message=self.message, user_identity_id="otro"
        )
        response = self.client.delete(f"/api/v1/reactions/{reaction.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Reaction.objects.filter(id=reaction.id).exists())
