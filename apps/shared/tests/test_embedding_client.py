"""EmbeddingClient: the single place that talks to the embeddings microservice."""

from unittest.mock import MagicMock, patch

import requests
from django.test import SimpleTestCase, override_settings

from apps.shared.embedding_client import EmbeddingClient, TextVector

POST = "apps.shared.embedding_client.requests.post"


def _response(status=200, body=None, text=""):
    response = MagicMock(status_code=status, text=text)
    response.json.return_value = body if body is not None else {}
    return response


class TestVectorize(SimpleTestCase):
    def setUp(self):
        self.client = EmbeddingClient("http://embed.local")

    @patch(POST)
    def test_returns_vector_and_processed_text(self, post):
        post.return_value = _response(
            body={"vector": [0.1, 0.2], "dimension": 2, "processed_text": "hello"}
        )

        result = self.client.vectorize("hola")

        self.assertEqual(result, TextVector([0.1, 0.2], "hello"))

    @patch(POST)
    def test_posts_the_text_with_the_cleaning_options(self, post):
        post.return_value = _response(body={"vector": [1.0]})

        self.client.vectorize("hola")

        args, kwargs = post.call_args
        self.assertEqual(args[0], "http://embed.local/text-processing/vectorize/")
        self.assertEqual(
            kwargs["json"],
            {"text": "hola", "translate_to_english": True, "clean_text": True},
        )
        self.assertEqual(kwargs["timeout"], 30)

    @patch(POST)
    def test_processed_text_is_optional(self, post):
        post.return_value = _response(body={"vector": [1.0]})

        self.assertIsNone(self.client.vectorize("hola").processed_text)

    @patch(POST)
    def test_non_200_answer_gives_none(self, post):
        post.return_value = _response(status=500, text="boom")

        self.assertIsNone(self.client.vectorize("hola"))

    @patch(POST)
    def test_answer_without_a_vector_gives_none(self, post):
        post.return_value = _response(body={"vector": []})

        self.assertIsNone(self.client.vectorize("hola"))

    @patch(POST, side_effect=requests.ConnectionError("down"))
    def test_connection_error_gives_none(self, post):
        self.assertIsNone(self.client.vectorize("hola"))

    @patch(POST)
    def test_unreadable_json_gives_none(self, post):
        response = _response()
        response.json.side_effect = ValueError("not json")
        post.return_value = response

        self.assertIsNone(self.client.vectorize("hola"))


class TestEmbed(SimpleTestCase):
    @patch(POST)
    def test_returns_only_the_vector(self, post):
        post.return_value = _response(body={"vector": [0.5, 0.6]})

        self.assertEqual(EmbeddingClient("http://e").embed("x"), [0.5, 0.6])

    @patch(POST, side_effect=requests.Timeout("slow"))
    def test_returns_none_on_failure(self, post):
        self.assertIsNone(EmbeddingClient("http://e").embed("x"))


class TestConfiguration(SimpleTestCase):
    @override_settings(EMBEDDING_SERVICE_URL="http://from-settings:8001")
    def test_base_url_defaults_to_the_setting(self):
        self.assertEqual(EmbeddingClient().base_url, "http://from-settings:8001")

    def test_explicit_base_url_wins(self):
        self.assertEqual(EmbeddingClient("http://x").base_url, "http://x")
