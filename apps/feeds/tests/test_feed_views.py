"""Unitarias de las vistas de feed: FeedView, UserInteractionView,
trending_posts, user_feed_stats, feed_recommendations, UserPostsView,
explain_post_trending."""

from unittest.mock import patch

import requests
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.custom_auth.identity_principal import IdentityPrincipal
from apps.feeds.domain.entities.feed_post import FeedPost

# Necesario para que Django registre "feeds.Poll".
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


class FeedViewsTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = IdentityPrincipal(id="u1", username="ana")
        self.client.force_authenticate(user=self.user)


class TestFeedViewGet(FeedViewsTestCase):
    def test_feed_latest_por_defecto_devuelve_trending_por_fallback(self):
        _post(author_identity_id="u2")
        with _no_identity():
            response = self.client.get("/api/v1/feed/?type=latest")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_count"], 1)

    def test_feed_por_author(self):
        _post(author_identity_id="u9")
        _post(author_identity_id="u1")
        with _no_identity():
            response = self.client.get("/api/v1/feed/?author=u9")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_count"], 1)

    def test_feed_por_author_con_cursor_invalido_se_ignora(self):
        _post(author_identity_id="u9")
        with _no_identity():
            response = self.client.get(
                "/api/v1/feed/?author=u9&cursor=no-es-fecha"
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_feed_trending(self):
        _post(author_identity_id="u2", engagement_score=5)
        with _no_identity():
            response = self.client.get("/api/v1/feed/?type=trending")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class TestFeedViewPost(FeedViewsTestCase):
    def test_feed_filtrado_por_tags(self):
        _post(author_identity_id="u2", tags=["ia"])
        with _no_identity():
            response = self.client.post(
                "/api/v1/feed/",
                {"feed_type": "latest", "filters": {"tags": ["ia"]}},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_count"], 1)


class TestUserInteractionView(FeedViewsTestCase):
    def test_registra_interaccion(self):
        post = _post(author_identity_id="u2")
        response = self.client.post(
            "/api/v1/interactions/",
            {"post_id": str(post.id), "interaction_type": "view"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        post.refresh_from_db()
        self.assertEqual(post.views_count, 1)


class TestTrendingPosts(FeedViewsTestCase):
    def test_trending_posts_basico(self):
        _post(author_identity_id="u2", engagement_score=3)
        with _no_identity():
            response = self.client.get("/api/v1/feed/trending/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_count"], 1)
        self.assertIn("trending_metadata", response.data["posts"][0])

    def test_trending_posts_con_time_range(self):
        _post(author_identity_id="u2")
        with _no_identity():
            response = self.client.get("/api/v1/feed/trending/?time_range=7d")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_trending_posts_limit_invalido_usa_default(self):
        _post(author_identity_id="u2")
        with _no_identity():
            response = self.client.get("/api/v1/feed/trending/?limit=no-numero")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_trending_posts_no_falla_con_post_recien_creado(self):
        """Regresion: el SQL de trending_score hacia SQRT() antes de aplicar
        GREATEST(1, ...), asi que con hours_old ~ 0 (o negativo por
        redondeo) explotaba con 'cannot take square root of a negative
        number'."""
        _post(author_identity_id="u2", engagement_score=10)
        with _no_identity():
            response = self.client.get("/api/v1/feed/trending/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class TestUserFeedStats(FeedViewsTestCase):
    def test_stats_de_usuario(self):
        _post(
            author_identity_id="u1",
            likes_count=5,
            comments_count=2,
            views_count=10,
            shares_count=1,
        )
        response = self.client.get("/api/v1/feed/stats/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_posts"], 1)
        self.assertEqual(response.data["total_likes_received"], 5)
        self.assertIsNotNone(response.data["most_liked_post"])
        self.assertIsNotNone(response.data["most_commented_post"])

    def test_stats_sin_posts(self):
        response = self.client.get("/api/v1/feed/stats/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_posts"], 0)
        self.assertIsNone(response.data["most_liked_post"])


class TestFeedRecommendations(FeedViewsTestCase):
    def test_recomendaciones_delega_en_personalized_feed(self):
        _post(author_identity_id="u2")
        with _no_identity():
            response = self.client.get("/api/v1/feed/recommendations/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("recommendations", response.data)


class TestUserPostsView(FeedViewsTestCase):
    def test_lista_posts_propios_con_paginacion(self):
        _post(author_identity_id="u1")
        _post(author_identity_id="u2")
        with _no_identity():
            response = self.client.get("/api/v1/user/posts/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_count"], 1)
        self.assertEqual(response.data["user_info"]["id"], "u1")

    def test_lista_posts_con_cursor_invalido_se_ignora(self):
        _post(author_identity_id="u1")
        with _no_identity():
            response = self.client.get("/api/v1/user/posts/?cursor=no-es-fecha")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class TestExplainPostTrending(FeedViewsTestCase):
    def test_explica_trending_de_post_existente(self):
        post = _post(author_identity_id="u1", likes_count=2)
        response = self.client.get(f"/api/v1/posts/{post.id}/explain-trending/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("algorithm_explanation", response.data)

    def test_post_inexistente_404(self):
        import uuid

        response = self.client.get(
            f"/api/v1/posts/{uuid.uuid4()}/explain-trending/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
