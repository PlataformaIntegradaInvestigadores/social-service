"""Unitarias de las vistas de posts: FeedPostListCreateView,
FeedPostDetailView, FeedPostFileUploadView, FeedPostSearchView,
FeedPostStatsView."""

from unittest.mock import patch

import requests
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.custom_auth.identity_principal import IdentityPrincipal
from apps.feeds.domain.entities.feed_post import FeedPost
from apps.feeds.domain.entities.post_file import PostFile

# Necesario para que Django registre "feeds.Poll" (FeedPost.poll es un
# OneToOneField lazy hacia ese modelo); ver test_feed_service.py.
from apps.feeds.domain.entities.poll import Poll  # noqa: F401

IDENTITY_GET = "apps.custom_auth.identity_profile_client.requests.get"
EMBEDDING_POST = "apps.feeds.domain.services.feed_service.requests.post"


def _no_identity():
    return patch(IDENTITY_GET, side_effect=requests.ConnectionError("down"))


def _no_embedding():
    return patch(EMBEDDING_POST, side_effect=requests.ConnectionError("down"))


def _post(**kwargs):
    defaults = {
        "author_identity_id": "u1",
        "author_snapshot": {"id": "u1", "username": "ana"},
        "content": "hola",
    }
    defaults.update(kwargs)
    return FeedPost.objects.create(**defaults)


class FeedPostViewsTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = IdentityPrincipal(id="u1", username="ana")
        self.client.force_authenticate(user=self.user)


class TestFeedPostListCreateView(FeedPostViewsTestCase):
    def test_lista_solo_posts_del_usuario(self):
        _post(author_identity_id="u1")
        _post(author_identity_id="u2")
        with _no_identity():
            response = self.client.get("/api/v1/posts/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_crea_post(self):
        with _no_identity(), _no_embedding():
            response = self.client.post(
                "/api/v1/posts/", {"content": "nuevo post"}, format="multipart"
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(FeedPost.objects.count(), 1)

    def test_crear_sin_contenido_falla(self):
        with _no_identity():
            response = self.client.post(
                "/api/v1/posts/", {"content": ""}, format="multipart"
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestFeedPostDetailView(FeedPostViewsTestCase):
    def test_get_registra_interaccion_de_vista(self):
        post = _post(author_identity_id="u1")
        with _no_identity():
            response = self.client.get(f"/api/v1/posts/{post.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        post.refresh_from_db()
        self.assertEqual(post.views_count, 1)

    def test_update_por_no_autor_403(self):
        post = _post(author_identity_id="otro")
        with _no_identity():
            response = self.client.patch(
                f"/api/v1/posts/{post.id}/", {"is_public": False}
            )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_sin_cambiar_content_persiste(self):
        """Regresion: perform_update solo llamaba serializer.save() cuando
        "content" venia en validated_data; cambiar solo is_public no
        persistia nada."""
        post = _post(author_identity_id="u1", is_public=True)
        with _no_identity():
            response = self.client.patch(
                f"/api/v1/posts/{post.id}/", {"is_public": False}
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        post.refresh_from_db()
        self.assertFalse(post.is_public)

    def test_update_cambiando_content_regenera_embedding(self):
        post = _post(author_identity_id="u1")
        with _no_identity(), _no_embedding():
            response = self.client.patch(
                f"/api/v1/posts/{post.id}/", {"content": "actualizado"}
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        post.refresh_from_db()
        self.assertEqual(post.content, "actualizado")

    def test_delete_por_no_autor_403(self):
        post = _post(author_identity_id="otro")
        with _no_identity():
            response = self.client.delete(f"/api/v1/posts/{post.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_exitoso(self):
        post = _post(author_identity_id="u1")
        with _no_identity():
            response = self.client.delete(f"/api/v1/posts/{post.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(FeedPost.objects.count(), 0)


class TestFeedPostFileUploadView(FeedPostViewsTestCase):
    def test_agregar_archivo_a_post_propio(self):
        post = _post(author_identity_id="u1")
        f = SimpleUploadedFile("a.png", b"data")
        response = self.client.post(
            f"/api/v1/posts/{post.id}/files/", {"files": [f]}, format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PostFile.objects.count(), 1)

    def test_agregar_archivo_a_post_ajeno_403(self):
        post = _post(author_identity_id="otro")
        f = SimpleUploadedFile("a.png", b"data")
        response = self.client.post(
            f"/api/v1/posts/{post.id}/files/", {"files": [f]}, format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_limite_de_archivos(self):
        post = _post(author_identity_id="u1")
        for i in range(10):
            PostFile.objects.create(
                post=post,
                file_type="image",
                file_size=1,
                original_filename=f"{i}.png",
            )
        f = SimpleUploadedFile("extra.png", b"data")
        response = self.client.post(
            f"/api/v1/posts/{post.id}/files/", {"files": [f]}, format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_archivo_subido_detecta_tipo_correctamente(self):
        """Regresion: PostFile.save() detectaba el tipo de archivo antes de
        fijar original_filename, asi que siempre caia en 'other'."""
        post = _post(author_identity_id="u1")
        f = SimpleUploadedFile("foto.jpg", b"data")
        self.client.post(
            f"/api/v1/posts/{post.id}/files/", {"files": [f]}, format="multipart"
        )
        pf = PostFile.objects.get(post=post)
        self.assertEqual(pf.file_type, "image")


class TestFeedPostSearchView(FeedPostViewsTestCase):
    def test_sin_parametros_retorna_vacio(self):
        with _no_identity():
            response = self.client.get("/api/v1/posts/search/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_busqueda_con_query_hace_fallback_a_texto(self):
        _post(content="hola desde investigacion cientifica muy interesante")
        with _no_identity(), _no_embedding():
            response = self.client.get("/api/v1/posts/search/?q=investigacion")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_busqueda_por_tags(self):
        _post(tags=["ia"])
        with _no_identity():
            response = self.client.get("/api/v1/posts/search/?tags=ia&vector=false")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class TestFeedPostStatsView(FeedPostViewsTestCase):
    def test_stats_de_post_propio(self):
        post = _post(author_identity_id="u1", likes_count=3)
        response = self.client.get(f"/api/v1/posts/{post.id}/stats/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["likes_count"], 3)

    def test_stats_de_post_ajeno_403(self):
        post = _post(author_identity_id="otro")
        response = self.client.get(f"/api/v1/posts/{post.id}/stats/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
