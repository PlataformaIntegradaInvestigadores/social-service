"""Unitarias ligeras de los management commands de feeds. Los comandos de
benchmark/validacion golpean un microservicio real por diseño (son
herramientas de diagnostico manual), asi que aqui solo se mockea esa llamada
para cubrir la logica propia del comando sin red ni sleeps largos."""

import io
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.feeds.domain.entities.feed_post import FeedPost

# Necesario para que Django registre "feeds.Poll".
from apps.feeds.domain.entities.poll import Poll  # noqa: F401
from apps.feeds.management.commands.validate_semantics import Command as SemCommand

EMBEDDING_POST = "apps.feeds.domain.services.feed_service.requests.post"


def _post(**kwargs):
    defaults = {
        "author_identity_id": "u1",
        "author_snapshot": {"id": "u1", "username": "ana"},
        "content": "hola",
    }
    defaults.update(kwargs)
    return FeedPost.objects.create(**defaults)


def _mock_embedding_response(vector=None):
    return type(
        "R",
        (),
        {
            "status_code": 200,
            "json": lambda self=None: {"vector": vector or [0.1] * 768},
        },
    )()


class TestUpdatePostEmbeddings(TestCase):
    def test_sin_posts_no_falla(self):
        out = io.StringIO()
        call_command("update_post_embeddings", stdout=out)
        self.assertIn("No hay posts", out.getvalue())

    def test_actualiza_posts_sin_embedding(self):
        _post()
        out = io.StringIO()
        with patch(EMBEDDING_POST, return_value=_mock_embedding_response()):
            call_command("update_post_embeddings", stdout=out)
        self.assertIn("actualizados correctamente", out.getvalue())

    def test_force_reprocesa_todos(self):
        post = _post()
        post.embedding = [0.1] * 768
        post.save(update_fields=["embedding"])
        out = io.StringIO()
        with patch(EMBEDDING_POST, return_value=_mock_embedding_response()):
            call_command("update_post_embeddings", "--force", stdout=out)
        self.assertIn("Procesando 1 posts", out.getvalue())

    def test_post_id_especifico(self):
        post = _post()
        other = _post()
        out = io.StringIO()
        with patch(EMBEDDING_POST, return_value=_mock_embedding_response()):
            call_command(
                "update_post_embeddings", f"--post-id={post.id}", stdout=out
            )
        self.assertIn("Procesando 1 posts", out.getvalue())

    def test_reporta_errores(self):
        _post()
        out = io.StringIO()
        import requests

        with patch(EMBEDDING_POST, side_effect=requests.ConnectionError("down")):
            call_command("update_post_embeddings", stdout=out)
        self.assertIn("Errores: 1", out.getvalue())


class TestBenchmarkEmbeddings(TestCase):
    def test_ejecuta_benchmark_mockeado(self):
        out = io.StringIO()
        with (
            patch(EMBEDDING_POST, return_value=_mock_embedding_response()),
            patch("time.sleep", return_value=None),
        ):
            call_command("benchmark_embeddings", "--iterations=1", stdout=out)
        self.assertIn("Resultados para Textos Cortos", out.getvalue())
        self.assertIn("Resultados para Textos Largos", out.getvalue())


class TestValidateSemantics(TestCase):
    def test_cosine_similarity_vectores_identicos(self):
        cmd = SemCommand()
        self.assertAlmostEqual(cmd.cosine_similarity([1, 0], [1, 0]), 1.0)

    def test_cosine_similarity_ortogonales(self):
        cmd = SemCommand()
        self.assertAlmostEqual(cmd.cosine_similarity([1, 0], [0, 1]), 0.0)

    def test_cosine_similarity_vector_cero(self):
        cmd = SemCommand()
        self.assertEqual(cmd.cosine_similarity([0, 0], [1, 1]), 0.0)

    def test_cosine_similarity_longitudes_distintas(self):
        cmd = SemCommand()
        self.assertEqual(cmd.cosine_similarity([1, 0], [1, 0, 0]), 0.0)

    def test_ejecuta_comando_mockeado(self):
        out = io.StringIO()
        with patch(EMBEDDING_POST, return_value=_mock_embedding_response([1.0, 0.0])):
            call_command("validate_semantics", stdout=out)
        self.assertIn("RESUMEN DE VALIDACIÓN SEMÁNTICA", out.getvalue())

    def test_sin_embeddings_reporta_error(self):
        out = io.StringIO()
        import requests

        with patch(EMBEDDING_POST, side_effect=requests.ConnectionError("down")):
            call_command("validate_semantics", stdout=out)
        self.assertIn("Error al generar embeddings", out.getvalue())


class TestValidateFunctionality(TestCase):
    def test_ejecuta_comando_mockeado(self):
        out = io.StringIO()
        with patch(
            "apps.feeds.management.commands.validate_functionality.Command.print_report"
        ) as mock_report:
            with patch(EMBEDDING_POST, return_value=_mock_embedding_response()):
                call_command("validate_functionality", stdout=out)
        mock_report.assert_called_once()
        # Los posts de prueba se limpian al finalizar.
        self.assertEqual(FeedPost.objects.count(), 0)
