"""Unitarias de DebateViewSet: CRUD de debates + cierre automatico/manual por
expiracion de end_time, y el helper send_notification (crea/actualiza
NotificationPhaseOne y emite por el channel layer)."""

from datetime import timedelta
from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.concensus.domain.entities.debate import Debate
from apps.concensus.domain.entities.notification import NotificationPhaseOne
from apps.concensus.infrastructure.api.v1.views.debate_views import send_notification
from apps.concensus.tests.testing_utils import mock_channel_layer
from apps.custom_auth.identity_principal import IdentityPrincipal

CHANNEL_LAYER_PATCH = (
    "apps.concensus.infrastructure.api.v1.views.debate_views.get_channel_layer"
)


class DebateTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = IdentityPrincipal(id="u1", username="ana", first_name="Ana")
        self.client.force_authenticate(user=self.user)
        self.group_id = "g1"

    def _debate(self, **extra):
        defaults = dict(
            title="T1",
            description="d",
            end_time=timedelta(hours=1),
            group_identity_id=self.group_id,
            group_snapshot={"id": self.group_id},
        )
        defaults.update(extra)
        return Debate.objects.create(**defaults)


class TestSendNotification(DebateTestCase):
    def test_crea_notificacion_y_emite(self):
        with patch(CHANNEL_LAYER_PATCH, return_value=mock_channel_layer()):
            notif = send_notification(
                self.user, self.group_id, "debate_created", "hola"
            )
        self.assertEqual(NotificationPhaseOne.objects.count(), 1)
        self.assertEqual(notif.message, "hola")

    def test_notificacion_repetida_solo_actualiza_created_at(self):
        with patch(CHANNEL_LAYER_PATCH, return_value=mock_channel_layer()):
            first = send_notification(
                self.user, self.group_id, "debate_created", "hola"
            )
            second = send_notification(
                self.user, self.group_id, "debate_created", "hola"
            )
        self.assertEqual(NotificationPhaseOne.objects.count(), 1)
        self.assertEqual(first.id, second.id)


class TestDebateList(DebateTestCase):
    def test_lista_debates_del_grupo_y_cierra_los_expirados(self):
        expired = self._debate(end_time=timedelta(seconds=-1))
        active = self._debate(title="T2")

        response = self.client.get(f"/api/v1/groups/{self.group_id}/debates/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expired.refresh_from_db()
        active.refresh_from_db()
        self.assertTrue(expired.is_closed)
        self.assertFalse(active.is_closed)

    def test_no_ve_debates_de_otro_grupo(self):
        self._debate(
            group_identity_id="otro-grupo", group_snapshot={"id": "otro-grupo"}
        )
        response = self.client.get(f"/api/v1/groups/{self.group_id}/debates/")
        self.assertEqual(response.data, [])


class TestDebateCreate(DebateTestCase):
    def test_crea_debate_si_no_hay_uno_activo(self):
        with patch(CHANNEL_LAYER_PATCH, return_value=mock_channel_layer()):
            response = self.client.post(
                f"/api/v1/groups/{self.group_id}/debates/",
                {
                    "title": "Nuevo debate",
                    "description": "desc",
                    "end_time": "01:00:00",
                },
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Debate.objects.count(), 1)

    def test_rechaza_si_ya_hay_un_debate_activo(self):
        self._debate()
        response = self.client.post(
            f"/api/v1/groups/{self.group_id}/debates/",
            {"title": "Otro", "description": "d", "end_time": "01:00:00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestDebateRetrieve(DebateTestCase):
    def test_retrieve_cierra_si_expiro(self):
        debate = self._debate(end_time=timedelta(seconds=-1))
        response = self.client.get(
            f"/api/v1/groups/{self.group_id}/debates/{debate.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        debate.refresh_from_db()
        self.assertTrue(debate.is_closed)


class TestDebateClose(DebateTestCase):
    def test_cierra_manualmente(self):
        debate = self._debate()
        with patch(CHANNEL_LAYER_PATCH, return_value=mock_channel_layer()):
            response = self.client.post(
                f"/api/v1/groups/{self.group_id}/debates/{debate.id}/close/"
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        debate.refresh_from_db()
        self.assertTrue(debate.is_closed)

    def test_ya_cerrado_retorna_400(self):
        debate = self._debate(is_closed=True)
        response = self.client.post(
            f"/api/v1/groups/{self.group_id}/debates/{debate.id}/close/"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestDebateValidateStatus(DebateTestCase):
    def test_abierto_retorna_200(self):
        debate = self._debate()
        response = self.client.get(
            f"/api/v1/groups/{self.group_id}/debates/{debate.id}/validate-status/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_cerrado_retorna_400(self):
        debate = self._debate(is_closed=True)
        response = self.client.get(
            f"/api/v1/groups/{self.group_id}/debates/{debate.id}/validate-status/"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestDebateDestroy(DebateTestCase):
    def test_elimina_el_debate(self):
        debate = self._debate()
        response = self.client.delete(
            f"/api/v1/groups/{self.group_id}/debates/{debate.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Debate.objects.filter(id=debate.id).exists())
