"""Unitarias de los modelos de dominio de feeds: FeedPost, Comment, Like,
Poll/PollOption/PollVote y PostFile."""

from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone

from apps.custom_auth.identity_principal import IdentityPrincipal
from apps.feeds.domain.entities.comment import Comment
from apps.feeds.domain.entities.feed_post import FeedPost
from apps.feeds.domain.entities.like import Like
from apps.feeds.domain.entities.poll import Poll, PollOption, PollVote
from apps.feeds.domain.entities.post_file import PostFile


def _post(**kwargs):
    defaults = {
        "author_identity_id": "u1",
        "author_snapshot": {"id": "u1", "username": "ana"},
        "content": "hola mundo",
    }
    defaults.update(kwargs)
    return FeedPost.objects.create(**defaults)


class TestFeedPost(TestCase):
    def test_author_getter_setter(self):
        post = _post()
        self.assertEqual(post.author.username, "ana")

        user = IdentityPrincipal(id="u2", username="beto")
        post.author = user
        self.assertEqual(post.author_identity_id, "u2")
        self.assertEqual(post.author_snapshot["username"], "beto")

    def test_str_usa_username_o_identity_id(self):
        post = _post(content="x" * 60)
        self.assertTrue(str(post).startswith("ana - "))
        self.assertTrue(str(post).endswith("..."))

    def test_update_engagement_score_recien_creado(self):
        post = _post(likes_count=2, comments_count=1, shares_count=1, views_count=10)
        post.update_engagement_score()
        self.assertGreater(post.engagement_score, 0)

    def test_get_files_get_images_get_documents(self):
        post = _post()
        PostFile.objects.create(
            post=post,
            file_type="image",
            file_size=100,
            original_filename="a.png",
        )
        PostFile.objects.create(
            post=post,
            file_type="document",
            file_size=200,
            original_filename="b.pdf",
        )
        self.assertEqual(post.get_files().count(), 2)
        self.assertEqual(post.get_images().count(), 1)
        self.assertEqual(post.get_documents().count(), 1)

    def test_explain_trending_score_estructura(self):
        post = _post(likes_count=5, comments_count=2, shares_count=1, views_count=20)
        explanation = post.explain_trending_score()
        self.assertEqual(explanation["post_id"], str(post.id))
        self.assertEqual(explanation["likes"], 5)
        self.assertIn("trending_score", explanation)


class TestComment(TestCase):
    def setUp(self):
        self.post = _post()

    def test_author_getter_setter(self):
        comment = Comment.objects.create(
            post=self.post, author_identity_id="u1", content="c1"
        )
        self.assertEqual(comment.author.id, "u1")

        user = IdentityPrincipal(id="u3", username="carla")
        comment.author = user
        self.assertEqual(comment.author_identity_id, "u3")

    def test_str_con_y_sin_parent(self):
        root = Comment.objects.create(
            post=self.post,
            author_identity_id="u1",
            author_snapshot={"username": "ana"},
            content="raiz",
        )
        self.assertIn("Comentario de", str(root))

        reply = Comment.objects.create(
            post=self.post,
            author_identity_id="u2",
            author_snapshot={"username": "beto"},
            parent_comment=root,
            content="respuesta",
        )
        self.assertIn("Respuesta de", str(reply))

    def test_get_level_get_thread_root_can_reply(self):
        root = Comment.objects.create(
            post=self.post, author_identity_id="u1", content="raiz"
        )
        child = Comment.objects.create(
            post=self.post, author_identity_id="u2", content="hijo", parent_comment=root
        )
        grandchild = Comment.objects.create(
            post=self.post,
            author_identity_id="u3",
            content="nieto",
            parent_comment=child,
        )

        self.assertEqual(root.get_level(), 0)
        self.assertEqual(child.get_level(), 1)
        self.assertEqual(grandchild.get_level(), 2)
        self.assertEqual(grandchild.get_thread_root(), root)
        self.assertTrue(root.can_reply(max_depth=5))
        self.assertFalse(grandchild.can_reply(max_depth=2))

    def test_get_all_descendants(self):
        root = Comment.objects.create(
            post=self.post, author_identity_id="u1", content="raiz"
        )
        child = Comment.objects.create(
            post=self.post, author_identity_id="u2", content="hijo", parent_comment=root
        )
        grandchild = Comment.objects.create(
            post=self.post,
            author_identity_id="u3",
            content="nieto",
            parent_comment=child,
        )
        descendants = root.get_all_descendants()
        self.assertEqual(set(descendants), {child, grandchild})

    def test_save_actualiza_contador_del_post_y_del_padre(self):
        root = Comment.objects.create(
            post=self.post, author_identity_id="u1", content="raiz"
        )
        self.post.refresh_from_db()
        self.assertEqual(self.post.comments_count, 1)

        Comment.objects.create(
            post=self.post, author_identity_id="u2", content="hijo", parent_comment=root
        )
        root.refresh_from_db()
        self.post.refresh_from_db()
        self.assertEqual(root.replies_count, 1)
        self.assertEqual(self.post.comments_count, 2)

    def test_soft_delete(self):
        root = Comment.objects.create(
            post=self.post, author_identity_id="u1", content="raiz"
        )
        child = Comment.objects.create(
            post=self.post, author_identity_id="u2", content="hijo", parent_comment=root
        )

        child.soft_delete()
        child.refresh_from_db()
        root.refresh_from_db()
        self.post.refresh_from_db()

        self.assertTrue(child.is_deleted)
        self.assertEqual(child.content, "[Comentario eliminado]")
        self.assertEqual(root.replies_count, 0)
        self.assertEqual(self.post.comments_count, 1)

    def test_get_display_content(self):
        comment = Comment.objects.create(
            post=self.post, author_identity_id="u1", content="visible"
        )
        self.assertEqual(comment.get_display_content(), "visible")

        comment.is_deleted = True
        self.assertEqual(comment.get_display_content(), "[Comentario eliminado]")


class TestLike(TestCase):
    def setUp(self):
        self.post = _post()
        self.user = IdentityPrincipal(id="u1", username="ana")

    def test_user_getter_setter(self):
        like, _ = Like.toggle_like(self.user, self.post)
        self.assertEqual(like.user.id, "u1")

        other = IdentityPrincipal(id="u2", username="beto")
        like.user = other
        self.assertEqual(like.user_identity_id, "u2")

    def test_str(self):
        like, _ = Like.toggle_like(self.user, self.post)
        self.assertIn("likes", str(like))

    def test_toggle_like_crea_y_elimina(self):
        like, created = Like.toggle_like(self.user, self.post)
        self.assertTrue(created)
        self.assertIsNotNone(like)
        self.post.refresh_from_db()
        self.assertEqual(self.post.likes_count, 1)

        like2, created2 = Like.toggle_like(self.user, self.post)
        self.assertFalse(created2)
        self.assertIsNone(like2)
        self.post.refresh_from_db()
        self.assertEqual(self.post.likes_count, 0)

    def test_toggle_like_actualiza_engagement_score_en_post(self):
        self.post.engagement_score = 0
        self.post.save(update_fields=["engagement_score"])
        Like.toggle_like(self.user, self.post)
        self.post.refresh_from_db()
        self.assertGreater(self.post.engagement_score, 0)

    def test_get_user_likes_for_objects_vacio(self):
        self.assertEqual(Like.get_user_likes_for_objects(self.user, []), {})

    def test_get_user_likes_for_objects(self):
        Like.toggle_like(self.user, self.post)
        result = Like.get_user_likes_for_objects(self.user, [self.post])
        self.assertIn(str(self.post.id), result)

    def test_get_likes_count_for_objects_vacio(self):
        self.assertEqual(Like.get_likes_count_for_objects([]), {})

    def test_get_likes_count_for_objects(self):
        Like.toggle_like(self.user, self.post)
        other_user = IdentityPrincipal(id="u2", username="beto")
        Like.toggle_like(other_user, self.post)

        counts = Like.get_likes_count_for_objects([self.post])
        self.assertEqual(counts[str(self.post.id)], 2)

    def test_get_likes_count_for_objects_incluye_comentarios(self):
        comment = Comment.objects.create(
            post=self.post, author_identity_id="u1", content="c"
        )
        Like.toggle_like(self.user, self.post)
        Like.toggle_like(self.user, comment)

        counts = Like.get_likes_count_for_objects([self.post, comment])
        self.assertEqual(counts[str(self.post.id)], 1)
        self.assertEqual(counts[str(comment.id)], 1)


class TestPoll(TestCase):
    def test_total_votes_y_str(self):
        poll = Poll.objects.create(question="Q1")
        opt1 = PollOption.objects.create(poll=poll, text="A", order=0)
        opt2 = PollOption.objects.create(poll=poll, text="B", order=1)
        opt1.votes_count = 3
        opt1.save(update_fields=["votes_count"])
        opt2.votes_count = 2
        opt2.save(update_fields=["votes_count"])

        self.assertEqual(poll.total_votes, 5)
        self.assertTrue(str(poll).startswith("Poll:"))

    def test_is_expired(self):
        poll = Poll.objects.create(question="Q1")
        self.assertFalse(poll.is_expired)

        poll.expires_at = timezone.now() - timedelta(hours=1)
        self.assertTrue(poll.is_expired)

        poll.expires_at = timezone.now() + timedelta(hours=1)
        self.assertFalse(poll.is_expired)

    def test_poll_option_str(self):
        poll = Poll.objects.create(question="Q1")
        opt = PollOption.objects.create(poll=poll, text="A", order=0)
        self.assertIn("A", str(opt))


class TestPollVote(TestCase):
    def setUp(self):
        self.poll = Poll.objects.create(question="Q1")
        self.option = PollOption.objects.create(poll=self.poll, text="A", order=0)
        self.user = IdentityPrincipal(id="u1", username="ana")

    def test_user_getter_setter(self):
        vote = PollVote.objects.create(
            user_identity_id="u1",
            user_snapshot={"username": "ana"},
            poll=self.poll,
            option=self.option,
        )
        self.assertEqual(vote.user.username, "ana")

        other = IdentityPrincipal(id="u2", username="beto")
        vote.user = other
        self.assertEqual(vote.user_identity_id, "u2")

    def test_str(self):
        vote = PollVote.objects.create(
            user_identity_id="u1",
            user_snapshot={"username": "ana"},
            poll=self.poll,
            option=self.option,
        )
        self.assertIn("voted for A", str(vote))

    def test_save_actualiza_votes_count(self):
        PollVote.objects.create(
            user_identity_id="u1", poll=self.poll, option=self.option
        )
        self.option.refresh_from_db()
        self.assertEqual(self.option.votes_count, 1)

    def test_delete_actualiza_votes_count(self):
        vote = PollVote.objects.create(
            user_identity_id="u1", poll=self.poll, option=self.option
        )
        vote.delete()
        self.option.refresh_from_db()
        self.assertEqual(self.option.votes_count, 0)


class TestPostFile(TestCase):
    def setUp(self):
        self.post = _post()

    def test_str_get_file_extension(self):
        pf = PostFile.objects.create(
            post=self.post,
            file_type="document",
            file_size=1234,
            original_filename="report.PDF",
        )
        self.assertIn("report.PDF", str(pf))
        self.assertEqual(pf.get_file_extension(), ".pdf")

    def test_is_image_is_document(self):
        img = PostFile.objects.create(
            post=self.post, file_type="image", file_size=1, original_filename="a.png"
        )
        doc = PostFile.objects.create(
            post=self.post,
            file_type="document",
            file_size=1,
            original_filename="a.pdf",
        )
        self.assertTrue(img.is_image())
        self.assertFalse(img.is_document())
        self.assertTrue(doc.is_document())
        self.assertFalse(doc.is_image())

    def test_get_file_size_mb(self):
        pf = PostFile.objects.create(
            post=self.post,
            file_type="document",
            file_size=2 * 1024 * 1024,
            original_filename="a.pdf",
        )
        self.assertEqual(pf.get_file_size_mb(), 2.0)

    def test_save_autodetecta_tipo_por_extension(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        for filename, expected in [
            ("a.jpg", "image"),
            ("a.pdf", "document"),
            ("a.mp4", "video"),
            ("a.mp3", "audio"),
            ("a.xyz", "other"),
        ]:
            pf = PostFile(
                post=self.post,
                file=SimpleUploadedFile(filename, b"data"),
            )
            pf.save()
            self.assertEqual(pf.file_type, expected)
            self.assertEqual(pf.original_filename, filename)
            self.assertEqual(pf.file_size, 4)


class TestLikeContentTypes(TestCase):
    def test_like_apunta_a_content_type_correcto(self):
        post = _post()
        user = IdentityPrincipal(id="u1", username="ana")
        like, _ = Like.toggle_like(user, post)
        ct = ContentType.objects.get_for_model(FeedPost)
        self.assertEqual(like.content_type, ct)
        self.assertEqual(like.content_object, post)
