"""Unitarias de fetch_grs_topics: consulta al GRS (predictive_model_backend)
los topicos recomendados de un grupo persistente por scopus_id."""

from unittest.mock import MagicMock, patch

import requests
from django.test import SimpleTestCase, override_settings

from apps.concensus.infrastructure.external.grs_client import fetch_grs_topics


class TestFetchGrsTopics(SimpleTestCase):
    def test_sin_scopus_ids_retorna_none(self):
        self.assertIsNone(fetch_grs_topics([]))
        self.assertIsNone(fetch_grs_topics([None, ""]))

    @override_settings(GRS_SERVICE_URL="http://grs.local")
    def test_grupo_no_vinculado_retorna_none(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"linked": False}
        with patch(
            "apps.concensus.infrastructure.external.grs_client.requests.post",
            return_value=mock_resp,
        ):
            self.assertIsNone(fetch_grs_topics(["123"]))

    @override_settings(GRS_SERVICE_URL="http://grs.local")
    def test_grupo_vinculado_retorna_nombres_de_topico(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "linked": True,
            "recommendations": [{"topic": "IA"}, {"topic": "ML"}],
        }
        with patch(
            "apps.concensus.infrastructure.external.grs_client.requests.post",
            return_value=mock_resp,
        ):
            self.assertEqual(fetch_grs_topics(["123"]), ["IA", "ML"])

    @override_settings(GRS_SERVICE_URL="http://grs.local")
    def test_error_de_red_retorna_none(self):
        with patch(
            "apps.concensus.infrastructure.external.grs_client.requests.post",
            side_effect=requests.ConnectionError("down"),
        ):
            self.assertIsNone(fetch_grs_topics(["123"]))

    @override_settings(GRS_SERVICE_URL="http://grs.local")
    def test_filtra_scopus_ids_vacios_y_convierte_a_str(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"linked": False}
        with patch(
            "apps.concensus.infrastructure.external.grs_client.requests.post",
            return_value=mock_resp,
        ) as mock_post:
            fetch_grs_topics([123, None, "", 456])
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["scopus_ids"], ["123", "456"])
