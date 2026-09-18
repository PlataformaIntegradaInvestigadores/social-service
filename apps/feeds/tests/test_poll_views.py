"""Unitarias de las vistas de encuestas: vote_poll, remove_vote,
get_poll_details."""

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.custom_auth.identity_principal import IdentityPrincipal
from apps.feeds.domain.entities.poll import Poll, PollOption, PollVote


class PollViewsTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = IdentityPrincipal(id="u1", username="ana")
        self.client.force_authenticate(user=self.user)
        self.poll = Poll.objects.create(question="Q1")
        self.opt_a = PollOption.objects.create(poll=self.poll, text="A", order=0)
        self.opt_b = PollOption.objects.create(poll=self.poll, text="B", order=1)


class TestVotePoll(PollViewsTestCase):
    def test_vota_exitosamente(self):
        response = self.client.post(
            f"/api/v1/polls/{self.poll.id}/vote/",
            {"option_ids": [str(self.opt_a.id)]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.opt_a.refresh_from_db()
        self.assertEqual(self.opt_a.votes_count, 1)

    def test_encuesta_inactiva(self):
        self.poll.is_active = False
        self.poll.save()
        response = self.client.post(
            f"/api/v1/polls/{self.poll.id}/vote/",
            {"option_ids": [str(self.opt_a.id)]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_encuesta_expirada(self):
        self.poll.expires_at = timezone.now() - timezone.timedelta(hours=1)
        self.poll.save()
        response = self.client.post(
            f"/api/v1/polls/{self.poll.id}/vote/",
            {"option_ids": [str(self.opt_a.id)]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sin_opciones(self):
        response = self.client.post(
            f"/api/v1/polls/{self.poll.id}/vote/", {"option_ids": []}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_multiples_opciones_en_encuesta_no_multiple(self):
        response = self.client.post(
            f"/api/v1/polls/{self.poll.id}/vote/",
            {"option_ids": [str(self.opt_a.id), str(self.opt_b.id)]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_ya_voto(self):
        PollVote.objects.create(
            user_identity_id="u1", poll=self.poll, option=self.opt_a
        )
        response = self.client.post(
            f"/api/v1/polls/{self.poll.id}/vote/",
            {"option_ids": [str(self.opt_b.id)]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_encuesta_inexistente_404(self):
        import uuid

        response = self.client.post(
            f"/api/v1/polls/{uuid.uuid4()}/vote/",
            {"option_ids": [str(self.opt_a.id)]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_opcion_invalida(self):
        import uuid

        response = self.client.post(
            f"/api/v1/polls/{self.poll.id}/vote/",
            {"option_ids": [str(uuid.uuid4())]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_multiple_choice_reemplaza_votos_previos(self):
        self.poll.is_multiple_choice = True
        self.poll.save()
        PollVote.objects.create(
            user_identity_id="u1", poll=self.poll, option=self.opt_a
        )
        response = self.client.post(
            f"/api/v1/polls/{self.poll.id}/vote/",
            {"option_ids": [str(self.opt_b.id)]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            PollVote.objects.filter(user_identity_id="u1").count(), 1
        )


class TestRemoveVote(PollViewsTestCase):
    def test_encuesta_inactiva(self):
        self.poll.is_active = False
        self.poll.save()
        response = self.client.delete(f"/api/v1/polls/{self.poll.id}/remove-vote/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sin_votos(self):
        response = self.client.delete(f"/api/v1/polls/{self.poll.id}/remove-vote/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_elimina_voto_existente(self):
        PollVote.objects.create(
            user_identity_id="u1", poll=self.poll, option=self.opt_a
        )
        response = self.client.delete(f"/api/v1/polls/{self.poll.id}/remove-vote/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(PollVote.objects.count(), 0)


class TestGetPollDetails(PollViewsTestCase):
    def test_obtiene_detalles(self):
        response = self.client.get(f"/api/v1/polls/{self.poll.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["question"], "Q1")

    def test_encuesta_inexistente_404(self):
        """Regresion: vote_poll/remove_vote/get_poll_details envolvian
        get_object_or_404 en un try/except que solo distinguia
        Exception generico, asi que Http404 (no es una subclase de
        DoesNotExist) siempre caia al except generico y devolvia 500."""
        import uuid

        response = self.client.get(f"/api/v1/polls/{uuid.uuid4()}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
