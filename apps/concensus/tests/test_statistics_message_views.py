"""Unitarias de StatisticsView (conteo de posturas + usuarios activos en cache)
y MessageHistoryView (historial de mensajes raiz de un debate)."""

from datetime import timedelta

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.concensus.domain.entities.debate import Debate
from apps.concensus.domain.entities.debate_message import Message
from apps.concensus.domain.entities.debate_participant_posture import UserPosture
from apps.custom_auth.identity_principal import IdentityPrincipal


class ViewsTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=IdentityPrincipal(id="u1", username="ana"))
        self.debate = Debate.objects.create(
            title="T1",
            description="d",
            end_time=timedelta(hours=1),
            group_identity_id="g1",
            group_snapshot={"id": "g1"},
        )


class TestStatisticsView(ViewsTestCase):
    def test_cuenta_posturas_por_tipo(self):
        UserPosture.objects.create(
            debate=self.debate, posture="agree", user_identity_id="u1"
        )
        UserPosture.objects.create(
            debate=self.debate, posture="disagree", user_identity_id="u2"
        )

        response = self.client.get(f"/api/v1/debates/{self.debate.id}/statistics/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_agree"], 1)
        self.assertEqual(response.data["total_disagree"], 1)
        self.assertEqual(response.data["total_neutral"], 0)
        self.assertEqual(response.data["total_active_users"], 0)


class TestMessageHistoryView(ViewsTestCase):
    def test_lista_solo_mensajes_raiz_ordenados(self):
        root = Message.objects.create(
            debate=self.debate, text="primero", user_identity_id="u1"
        )
        Message.objects.create(
            debate=self.debate,
            text="respuesta",
            user_identity_id="u2",
            parent=root,
        )

        response = self.client.get(f"/api/v1/messages/{self.debate.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["text"], "primero")
