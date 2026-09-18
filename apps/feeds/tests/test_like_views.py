"""Unitarias de las vistas de likes: LikeToggleView, UserLikesView,
like_post, like_comment, post_likes, comment_likes."""

from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.custom_auth.identity_principal import IdentityPrincipal
from apps.feeds.domain.entities.comment import Comment
from apps.feeds.domain.entities.feed_post import FeedPost
from apps.feeds.domain.entities.like import Like

# Necesario para que Django registre "feeds.Poll".
from apps.feeds.domain.entities.poll import Poll  # noqa: F401


def _post(**kwargs):
    defaults = {
        "author_identity_id": "u1",
        "author_snapshot": {"id": "u1", "username": "ana"},
        "content": "hola",
    }
    defaults.update(kwargs)
    return FeedPost.objects.create(**defaults)


class LikeViewsTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = IdentityPrincipal(id="u1", username="ana")
        self.client.force_authenticate(user=self.user)
        self.post = _post()


class TestLikeToggleView(LikeViewsTestCase):
    def test_toggle_like_en_post(self):
        response = self.client.post(
            "/api/v1/likes/toggle/",
            {"content_type": "feedpost", "object_id": str(self.post.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["liked"])

    def test_toggle_like_en_comentario_borrado_400(self):
        comment = Comment.objects.create(
            post=self.post, author_identity_id="u1", content="c"
        )
        comment.soft_delete()
        response = self.client.post(
            "/api/v1/likes/toggle/",
            {"content_type": "comment", "object_id": str(comment.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_toggle_like_en_comentario(self):
        comment = Comment.objects.create(
            post=self.post, author_identity_id="u1", content="c"
        )
        response = self.client.post(
            "/api/v1/likes/toggle/",
            {"content_type": "comment", "object_id": str(comment.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["liked"])


class TestUserLikesView(LikeViewsTestCase):
    def test_lista_likes_del_usuario(self):
        Like.toggle_like(self.user, self.post)
        response = self.client.get("/api/v1/likes/user/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_filtra_por_content_type_feedpost(self):
        comment = Comment.objects.create(
            post=self.post, author_identity_id="u1", content="c"
        )
        Like.toggle_like(self.user, self.post)
        Like.toggle_like(self.user, comment)
        response = self.client.get("/api/v1/likes/user/?content_type=feedpost")
        self.assertEqual(len(response.data), 1)

    def test_filtra_por_content_type_comment(self):
        comment = Comment.objects.create(
            post=self.post, author_identity_id="u1", content="c"
        )
        Like.toggle_like(self.user, self.post)
        Like.toggle_like(self.user, comment)
        response = self.client.get("/api/v1/likes/user/?content_type=comment")
        self.assertEqual(len(response.data), 1)


class TestLikePost(LikeViewsTestCase):
    def test_post_toggle(self):
        response = self.client.post(f"/api/v1/posts/{self.post.id}/like/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["liked"])

    def test_delete_sin_like_previo(self):
        response = self.client.delete(f"/api/v1/posts/{self.post.id}/like/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Post was not liked")

    def test_delete_con_like_previo(self):
        Like.toggle_like(self.user, self.post)
        response = self.client.delete(f"/api/v1/posts/{self.post.id}/like/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["liked"])
        self.post.refresh_from_db()
        self.assertEqual(self.post.likes_count, 0)


class TestLikeComment(LikeViewsTestCase):
    def setUp(self):
        super().setUp()
        self.comment = Comment.objects.create(
            post=self.post, author_identity_id="u1", content="c"
        )

    def test_no_se_puede_dar_like_a_borrado(self):
        self.comment.soft_delete()
        response = self.client.post(f"/api/v1/comments/{self.comment.id}/like/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_toggle(self):
        response = self.client.post(f"/api/v1/comments/{self.comment.id}/like/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["liked"])

    def test_delete_con_like_previo(self):
        Like.toggle_like(self.user, self.comment)
        response = self.client.delete(f"/api/v1/comments/{self.comment.id}/like/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["liked"])


class TestPostLikes(LikeViewsTestCase):
    def test_lista_likes_de_post(self):
        Like.toggle_like(self.user, self.post)
        response = self.client.get(f"/api/v1/posts/{self.post.id}/likes/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_count"], 1)


class TestCommentLikes(LikeViewsTestCase):
    def test_comentario_borrado_404(self):
        comment = Comment.objects.create(
            post=self.post, author_identity_id="u1", content="c"
        )
        comment.soft_delete()
        response = self.client.get(f"/api/v1/comments/{comment.id}/likes/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_lista_likes_de_comentario(self):
        comment = Comment.objects.create(
            post=self.post, author_identity_id="u1", content="c"
        )
        Like.toggle_like(self.user, comment)
        response = self.client.get(f"/api/v1/comments/{comment.id}/likes/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_count"], 1)
