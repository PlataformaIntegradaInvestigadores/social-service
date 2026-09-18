"""Unitarias de las vistas de comentarios: CommentListCreateView,
CommentDetailView, CommentThreadView, CommentRepliesView, CommentSearchView."""

from unittest.mock import patch

import requests
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.custom_auth.identity_principal import IdentityPrincipal
from apps.feeds.domain.entities.comment import Comment
from apps.feeds.domain.entities.feed_post import FeedPost

# Necesario para que Django registre "feeds.Poll" (FeedPost.poll es un
# OneToOneField lazy hacia ese modelo); ver test_feed_service.py.
from apps.feeds.domain.entities.poll import Poll  # noqa: F401

IDENTITY_GET = "apps.custom_auth.identity_profile_client.requests.get"


def _no_identity():
    return patch(IDENTITY_GET, side_effect=requests.ConnectionError("down"))


def _post(**kwargs):
    defaults = {
        "author_identity_id": "u1",
        "author_snapshot": {"id": "u1", "username": "ana"},
        "content": "hola",
    }
    defaults.update(kwargs)
    return FeedPost.objects.create(**defaults)


class CommentViewsTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = IdentityPrincipal(id="u1", username="ana")
        self.client.force_authenticate(user=self.user)
        self.post = _post()


class TestCommentListCreateView(CommentViewsTestCase):
    def test_lista_solo_comentarios_raiz(self):
        root = Comment.objects.create(
            post=self.post, author_identity_id="u1", content="raiz"
        )
        Comment.objects.create(
            post=self.post, author_identity_id="u2", content="hijo", parent_comment=root
        )
        with _no_identity():
            response = self.client.get(f"/api/v1/posts/{self.post.id}/comments/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_crea_comentario(self):
        with _no_identity():
            response = self.client.post(
                f"/api/v1/posts/{self.post.id}/comments/", {"content": "hola"}
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Comment.objects.count(), 1)

    def test_crear_con_contenido_invalido_falla(self):
        with _no_identity():
            response = self.client.post(
                f"/api/v1/posts/{self.post.id}/comments/", {"content": ""}
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestCommentDetailView(CommentViewsTestCase):
    def test_get_comentario_no_borrado(self):
        comment = Comment.objects.create(
            post=self.post, author_identity_id="u1", content="c"
        )
        with _no_identity():
            response = self.client.get(f"/api/v1/comments/{comment.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_comentario_borrado_de_otro_usuario_403(self):
        comment = Comment.objects.create(
            post=self.post, author_identity_id="u2", content="c"
        )
        comment.soft_delete()
        response = self.client.get(f"/api/v1/comments/{comment.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_por_no_autor_403(self):
        comment = Comment.objects.create(
            post=self.post, author_identity_id="otro", content="c"
        )
        with _no_identity():
            response = self.client.patch(
                f"/api/v1/comments/{comment.id}/", {"content": "editado"}
            )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_comentario_borrado_403(self):
        comment = Comment.objects.create(
            post=self.post, author_identity_id="u1", content="c"
        )
        comment.soft_delete()
        with _no_identity():
            response = self.client.patch(
                f"/api/v1/comments/{comment.id}/", {"content": "editado"}
            )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_exitoso(self):
        comment = Comment.objects.create(
            post=self.post, author_identity_id="u1", content="c"
        )
        with _no_identity():
            response = self.client.patch(
                f"/api/v1/comments/{comment.id}/", {"content": "editado"}
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        comment.refresh_from_db()
        self.assertEqual(comment.content, "editado")

    def test_delete_por_no_autor_403(self):
        comment = Comment.objects.create(
            post=self.post, author_identity_id="otro", content="c"
        )
        with _no_identity():
            response = self.client.delete(f"/api/v1/comments/{comment.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_exitoso_es_soft_delete(self):
        comment = Comment.objects.create(
            post=self.post, author_identity_id="u1", content="c"
        )
        with _no_identity():
            response = self.client.delete(f"/api/v1/comments/{comment.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        comment.refresh_from_db()
        self.assertTrue(comment.is_deleted)


class TestCommentThreadView(CommentViewsTestCase):
    def test_get_thread(self):
        comment = Comment.objects.create(
            post=self.post, author_identity_id="u1", content="c"
        )
        with _no_identity():
            response = self.client.get(f"/api/v1/comments/{comment.id}/thread/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class TestCommentRepliesView(CommentViewsTestCase):
    def test_lista_respuestas(self):
        root = Comment.objects.create(
            post=self.post, author_identity_id="u1", content="raiz"
        )
        Comment.objects.create(
            post=self.post, author_identity_id="u2", content="hijo", parent_comment=root
        )
        with _no_identity():
            response = self.client.get(f"/api/v1/comments/{root.id}/replies/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_crea_respuesta(self):
        root = Comment.objects.create(
            post=self.post, author_identity_id="u1", content="raiz"
        )
        with _no_identity():
            response = self.client.post(
                f"/api/v1/comments/{root.id}/replies/", {"content": "respuesta"}
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_responder_a_borrado_403(self):
        root = Comment.objects.create(
            post=self.post, author_identity_id="u1", content="raiz"
        )
        root.soft_delete()
        with _no_identity():
            response = self.client.post(
                f"/api/v1/comments/{root.id}/replies/", {"content": "respuesta"}
            )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_maximo_de_anidacion_403(self):
        """Regresion: perform_create usaba parent_comment.thread_depth
        (atributo inexistente); ahora usa get_level()."""
        parent = None
        comment = Comment.objects.create(
            post=self.post, author_identity_id="u1", content="raiz"
        )
        for _ in range(5):
            comment = Comment.objects.create(
                post=self.post,
                author_identity_id="u1",
                content="c",
                parent_comment=comment,
            )
        with _no_identity():
            response = self.client.post(
                f"/api/v1/comments/{comment.id}/replies/", {"content": "otra"}
            )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class TestCommentSearchView(CommentViewsTestCase):
    def test_busca_por_contenido(self):
        Comment.objects.create(
            post=self.post, author_identity_id="u1", content="hola mundo"
        )
        Comment.objects.create(
            post=self.post, author_identity_id="u1", content="otro texto"
        )
        with _no_identity():
            response = self.client.get("/api/v1/comments/search/?q=mundo")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_busca_por_post_id(self):
        other_post = _post()
        Comment.objects.create(post=self.post, author_identity_id="u1", content="c1")
        Comment.objects.create(
            post=other_post, author_identity_id="u1", content="c2"
        )
        with _no_identity():
            response = self.client.get(
                f"/api/v1/comments/search/?post_id={self.post.id}"
            )
        self.assertEqual(len(response.data), 1)

    def test_busca_por_author(self):
        Comment.objects.create(
            post=self.post,
            author_identity_id="u1",
            author_snapshot={"username": "ana"},
            content="c1",
        )
        with _no_identity():
            response = self.client.get("/api/v1/comments/search/?author=ana")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
