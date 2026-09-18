"""Unitarias de los serializers de feeds: comment_serializers,
feed_post_serializers, feed_serializers, like_serializers, poll_serializers.

Todas patchean requests.get del cliente de identidad para no golpear red real
(el helper get_identity_user_snapshot ya prueba su propio manejo de errores
en apps/custom_auth/test_identity_profile_client.py)."""

from unittest.mock import patch

import requests
from django.contrib.contenttypes.models import ContentType
from django.http import QueryDict
from django.test import RequestFactory, SimpleTestCase, TestCase

from apps.custom_auth.identity_principal import IdentityPrincipal
from apps.feeds.domain.entities.comment import Comment
from apps.feeds.domain.entities.feed_post import FeedPost
from apps.feeds.domain.entities.like import Like
from apps.feeds.domain.entities.poll import Poll, PollOption, PollVote
from apps.feeds.infrastructure.api.v1.serializers.comment_serializers import (
    CommentCreateSerializer,
    CommentDetailSerializer,
    CommentSerializer,
    CommentThreadSerializer,
)
from apps.feeds.infrastructure.api.v1.serializers.feed_post_serializers import (
    FeedPostCreateSerializer,
    FlexibleTagsField,
)
from apps.feeds.infrastructure.api.v1.serializers.feed_serializers import (
    FeedFilterSerializer,
    FeedRequestSerializer,
    UserInteractionSerializer,
)
from apps.feeds.infrastructure.api.v1.serializers.like_serializers import (
    LikeSerializer,
    LikeToggleSerializer,
)
from apps.feeds.infrastructure.api.v1.serializers.poll_serializers import (
    PollCreateSerializer,
    PollVoteSerializer,
)

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


def _request(user=None):
    req = RequestFactory().get("/")
    req.user = user or IdentityPrincipal(id="u1", username="ana")
    return req


class TestCommentSerializer(TestCase):
    def setUp(self):
        self.post = _post()

    def test_get_author(self):
        comment = Comment.objects.create(
            post=self.post,
            author_identity_id="u1",
            author_snapshot={"username": "ana"},
            content="hola",
        )
        with _no_identity():
            data = CommentSerializer(
                comment, context={"request": _request()}
            ).data
        self.assertEqual(data["author"]["username"], "ana")

    def test_get_replies_count_ignora_borrados(self):
        root = Comment.objects.create(
            post=self.post, author_identity_id="u1", content="raiz"
        )
        Comment.objects.create(
            post=self.post, author_identity_id="u2", content="r1", parent_comment=root
        )
        deleted = Comment.objects.create(
            post=self.post, author_identity_id="u3", content="r2", parent_comment=root
        )
        deleted.soft_delete()
        with _no_identity():
            data = CommentSerializer(root, context={"request": _request()}).data
        self.assertEqual(data["replies_count"], 1)

    def test_get_is_liked_sin_request(self):
        comment = Comment.objects.create(
            post=self.post, author_identity_id="u1", content="c"
        )
        serializer = CommentSerializer(comment, context={})
        self.assertFalse(serializer.data["is_liked"])

    def test_get_is_liked_true(self):
        comment = Comment.objects.create(
            post=self.post, author_identity_id="u1", content="c"
        )
        user = IdentityPrincipal(id="u1")
        ct = ContentType.objects.get_for_model(Comment)
        Like.objects.create(
            user_identity_id="u1", content_type=ct, object_id=comment.id
        )
        with _no_identity():
            data = CommentSerializer(
                comment, context={"request": _request(user)}
            ).data
        self.assertTrue(data["is_liked"])


class TestCommentCreateSerializer(TestCase):
    def test_valida_content_vacio(self):
        serializer = CommentCreateSerializer(data={"content": "   "})
        self.assertFalse(serializer.is_valid())
        self.assertIn("content", serializer.errors)

    def test_valida_content_muy_largo(self):
        serializer = CommentCreateSerializer(data={"content": "x" * 1001})
        self.assertFalse(serializer.is_valid())

    def test_content_se_limpia(self):
        serializer = CommentCreateSerializer(data={"content": "  hola  "})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["content"], "hola")

    def test_no_permite_responder_a_borrado(self):
        post = _post()
        parent = Comment.objects.create(
            post=post, author_identity_id="u1", content="c"
        )
        parent.soft_delete()
        serializer = CommentCreateSerializer(
            data={"content": "hola", "parent_comment": str(parent.id)}
        )
        self.assertFalse(serializer.is_valid())


class TestCommentDetailSerializer(TestCase):
    def test_get_replies_respeta_profundidad_maxima(self):
        post = _post()
        root = Comment.objects.create(
            post=post, author_identity_id="u1", content="raiz"
        )
        lvl1 = Comment.objects.create(
            post=post, author_identity_id="u2", content="l1", parent_comment=root
        )
        lvl2 = Comment.objects.create(
            post=post, author_identity_id="u3", content="l2", parent_comment=lvl1
        )
        Comment.objects.create(
            post=post, author_identity_id="u4", content="l3", parent_comment=lvl2
        )
        with _no_identity():
            data = CommentDetailSerializer(
                lvl2, context={"request": _request()}
            ).data
        # lvl2.get_level() == 2 < 3, entonces si expone replies (bloqueadas
        # solo en level >= 3)
        self.assertIsInstance(data["replies"], list)


class TestCommentThreadSerializer(TestCase):
    def test_get_replies_usa_get_level_no_thread_depth(self):
        """Regresion: get_replies usaba obj.thread_depth (atributo
        inexistente en Comment) y lanzaba AttributeError en cualquier
        respuesta con CommentThreadSerializer."""
        post = _post()
        root = Comment.objects.create(
            post=post, author_identity_id="u1", content="raiz"
        )
        Comment.objects.create(
            post=post, author_identity_id="u2", content="hijo", parent_comment=root
        )
        with _no_identity():
            data = CommentThreadSerializer(
                root, context={"request": _request()}
            ).data
        self.assertEqual(len(data["replies"]), 1)

    def test_get_user_has_liked(self):
        post = _post()
        comment = Comment.objects.create(
            post=post, author_identity_id="u1", content="c"
        )
        user = IdentityPrincipal(id="u9")
        ct = ContentType.objects.get_for_model(Comment)
        Like.objects.create(
            user_identity_id="u9", content_type=ct, object_id=comment.id
        )
        with _no_identity():
            data = CommentThreadSerializer(
                comment, context={"request": _request(user)}
            ).data
        self.assertTrue(data["user_has_liked"])

    def test_get_user_has_liked_sin_auth(self):
        post = _post()
        comment = Comment.objects.create(
            post=post, author_identity_id="u1", content="c"
        )
        serializer = CommentThreadSerializer(comment, context={})
        self.assertFalse(serializer.data["user_has_liked"])


class TestFlexibleTagsField(SimpleTestCase):
    def test_none_o_vacio(self):
        field = FlexibleTagsField()
        self.assertEqual(field.to_internal_value(None), [])
        self.assertEqual(field.to_internal_value(""), [])

    def test_json_array_string(self):
        field = FlexibleTagsField()
        self.assertEqual(field.to_internal_value('["IA", "ML"]'), ["IA", "ML"])

    def test_json_invalido_con_comillas_escapadas(self):
        field = FlexibleTagsField()
        result = field.to_internal_value('[\\"IA\\"]')
        self.assertEqual(result, ["IA"])

    def test_json_totalmente_invalido_falla(self):
        field = FlexibleTagsField()
        with self.assertRaises(Exception):
            field.to_internal_value("[not valid")

    def test_lista_no_string_falla(self):
        field = FlexibleTagsField()
        with self.assertRaises(Exception):
            field.to_internal_value(123)

    def test_item_no_string_falla(self):
        field = FlexibleTagsField()
        with self.assertRaises(Exception):
            field.to_internal_value([1, 2])

    def test_to_representation(self):
        field = FlexibleTagsField()
        self.assertEqual(field.to_representation(None), [])
        self.assertEqual(field.to_representation(["a"]), ["a"])


class TestFeedPostCreateSerializer(TestCase):
    def test_validate_content_vacio(self):
        serializer = FeedPostCreateSerializer(data={"content": ""})
        self.assertFalse(serializer.is_valid())

    def test_validate_content_muy_largo(self):
        serializer = FeedPostCreateSerializer(data={"content": "x" * 5001})
        self.assertFalse(serializer.is_valid())

    def test_validate_files_limite_cantidad(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        files = [SimpleUploadedFile(f"{i}.txt", b"x") for i in range(11)]
        serializer = FeedPostCreateSerializer(
            data={"content": "c", "files": files}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("files", serializer.errors)

    def test_validate_files_limite_tamano_individual(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        big = SimpleUploadedFile("a.txt", b"x" * (11 * 1024 * 1024))
        serializer = FeedPostCreateSerializer(data={"content": "c", "files": [big]})
        self.assertFalse(serializer.is_valid())

    def test_validate_poll_data_vacio_retorna_none(self):
        serializer = FeedPostCreateSerializer(data={"content": "c", "poll_data": ""})
        self.assertTrue(serializer.is_valid())
        self.assertIsNone(serializer.validated_data.get("poll_data"))

    def test_validate_poll_data_json_invalido(self):
        serializer = FeedPostCreateSerializer(
            data={"content": "c", "poll_data": "{not json"}
        )
        self.assertFalse(serializer.is_valid())

    def test_validate_poll_data_campos_faltantes(self):
        serializer = FeedPostCreateSerializer(
            data={"content": "c", "poll_data": '{"question": "Q?"}'}
        )
        self.assertFalse(serializer.is_valid())

    def test_validate_poll_data_muy_pocas_opciones(self):
        serializer = FeedPostCreateSerializer(
            data={
                "content": "c",
                "poll_data": '{"question": "Q?", "options": ["a"]}',
            }
        )
        self.assertFalse(serializer.is_valid())

    def test_create_sin_archivos_ni_poll(self):
        user = IdentityPrincipal(id="u1", username="ana")
        serializer = FeedPostCreateSerializer(data={"content": "hola"})
        serializer.is_valid(raise_exception=True)
        serializer.validated_data["author"] = user
        with _no_identity():
            post = serializer.save()
        self.assertEqual(post.author_identity_id, "u1")

    def test_create_con_poll(self):
        user = IdentityPrincipal(id="u1", username="ana")
        serializer = FeedPostCreateSerializer(
            data={
                "content": "hola",
                "poll_data": '{"question": "Q?", "options": ["a", "b"]}',
            }
        )
        serializer.is_valid(raise_exception=True)
        serializer.validated_data["author"] = user
        with _no_identity():
            post = serializer.save()
        self.assertIsNotNone(post.poll)
        self.assertEqual(post.poll.options.count(), 2)

    def test_determine_file_type_por_content_type(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        serializer = FeedPostCreateSerializer()
        f = SimpleUploadedFile("a.bin", b"x", content_type="image/png")
        self.assertEqual(serializer._determine_file_type(f), "image")

    def test_determine_file_type_por_extension(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        serializer = FeedPostCreateSerializer()
        f = SimpleUploadedFile("a.mp3", b"x", content_type=None)
        f.content_type = None
        self.assertEqual(serializer._determine_file_type(f), "audio")

    def test_determine_file_type_desconocido(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        serializer = FeedPostCreateSerializer()
        f = SimpleUploadedFile("a.xyz", b"x", content_type=None)
        f.content_type = None
        self.assertEqual(serializer._determine_file_type(f), "other")


class TestFeedPostSerializer(TestCase):
    def test_get_files_omite_archivos_faltantes(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from apps.feeds.domain.entities.post_file import PostFile
        from apps.feeds.infrastructure.api.v1.serializers.feed_post_serializers import (
            FeedPostSerializer,
        )

        post = _post()
        pf = PostFile.objects.create(
            post=post, file=SimpleUploadedFile("a.png", b"data")
        )
        # Borrar el archivo directamente del storage simula que la fila en
        # BD sigue apuntando a un archivo que ya no existe.
        pf.file.storage.delete(pf.file.name)

        with _no_identity():
            data = FeedPostSerializer(post, context={"request": _request()}).data
        self.assertEqual(data["files"], [])

    def test_get_comments_count_usa_anotacion_si_existe(self):
        from apps.feeds.infrastructure.api.v1.serializers.feed_post_serializers import (
            FeedPostSerializer,
        )

        post = _post()
        post.comments_count_real = 7
        with _no_identity():
            data = FeedPostSerializer(post, context={"request": _request()}).data
        self.assertEqual(data["comments_count"], 7)


class TestFeedRequestSerializer(SimpleTestCase):
    def test_type_tiene_prioridad_sobre_feed_type(self):
        serializer = FeedRequestSerializer(
            data={"feed_type": "latest", "type": "trending"}
        )
        serializer.is_valid(raise_exception=True)
        self.assertEqual(serializer.validated_data["feed_type"], "trending")
        self.assertNotIn("type", serializer.validated_data)

    def test_default_personalized(self):
        serializer = FeedRequestSerializer(data={})
        serializer.is_valid(raise_exception=True)
        self.assertEqual(serializer.validated_data["feed_type"], "personalized")

    def test_cursor_invalido(self):
        serializer = FeedRequestSerializer(data={"cursor": ""})
        self.assertFalse(serializer.is_valid())


class TestUserInteractionSerializer(TestCase):
    def test_post_id_inexistente(self):
        import uuid

        serializer = UserInteractionSerializer(
            data={"post_id": str(uuid.uuid4()), "interaction_type": "view"}
        )
        self.assertFalse(serializer.is_valid())

    def test_metadata_no_dict(self):
        post = _post()
        qd = QueryDict(mutable=True)
        serializer = UserInteractionSerializer(
            data={
                "post_id": str(post.id),
                "interaction_type": "view",
                "metadata": "no-dict",
            }
        )
        self.assertFalse(serializer.is_valid())

    def test_metadata_muy_grande(self):
        post = _post()
        serializer = UserInteractionSerializer(
            data={
                "post_id": str(post.id),
                "interaction_type": "view",
                "metadata": {"x": "y" * 1001},
            }
        )
        self.assertFalse(serializer.is_valid())

    def test_valido(self):
        post = _post()
        serializer = UserInteractionSerializer(
            data={"post_id": str(post.id), "interaction_type": "view"}
        )
        self.assertTrue(serializer.is_valid())


class TestFeedFilterSerializer(SimpleTestCase):
    def test_tags_vacios_invalidos(self):
        serializer = FeedFilterSerializer(data={"tags": ["  "]})
        self.assertFalse(serializer.is_valid())

    def test_demasiados_tags(self):
        serializer = FeedFilterSerializer(data={"tags": [str(i) for i in range(11)]})
        self.assertFalse(serializer.is_valid())

    def test_normaliza_tags(self):
        serializer = FeedFilterSerializer(data={"tags": [" IA "]})
        serializer.is_valid(raise_exception=True)
        self.assertEqual(serializer.validated_data["tags"], ["ia"])

    def test_date_from_mayor_a_date_to_invalido(self):
        serializer = FeedFilterSerializer(
            data={"date_from": "2026-02-01T00:00:00Z", "date_to": "2026-01-01T00:00:00Z"}
        )
        self.assertFalse(serializer.is_valid())


class TestLikeSerializer(TestCase):
    def test_get_content_object_trunca_texto_largo(self):
        post = _post(content="x" * 200)
        user = IdentityPrincipal(id="u1")
        like, _ = Like.toggle_like(user, post)
        data = LikeSerializer(like).data
        self.assertTrue(data["content_object"].startswith("FeedPost:"))
        self.assertTrue(data["content_object"].endswith("..."))

    def test_get_content_object_sin_atributo_content(self):
        poll = Poll.objects.create(question="Q1")
        user = IdentityPrincipal(id="u1")
        ct = ContentType.objects.get_for_model(Poll)
        like = Like.objects.create(
            user_identity_id="u1", content_type=ct, object_id=poll.id
        )
        data = LikeSerializer(like).data
        self.assertIn("Poll", data["content_object"])


class TestLikeToggleSerializer(TestCase):
    def test_content_type_invalido(self):
        import uuid

        serializer = LikeToggleSerializer(
            data={"content_type": "bogus", "object_id": str(uuid.uuid4())}
        )
        self.assertFalse(serializer.is_valid())

    def test_feedpost_inexistente_no_lanza_nameerror(self):
        """Regresion: el except capturaba (FeedPost.DoesNotExist,
        Comment.DoesNotExist) pero solo una de las dos clases estaba
        importada en cada rama, lanzando NameError en vez de
        ValidationError."""
        import uuid

        serializer = LikeToggleSerializer(
            data={"content_type": "feedpost", "object_id": str(uuid.uuid4())}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)

    def test_comment_inexistente_no_lanza_nameerror(self):
        import uuid

        serializer = LikeToggleSerializer(
            data={"content_type": "comment", "object_id": str(uuid.uuid4())}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)

    def test_comment_borrado_invalido(self):
        post = _post()
        comment = Comment.objects.create(
            post=post, author_identity_id="u1", content="c"
        )
        comment.soft_delete()
        serializer = LikeToggleSerializer(
            data={"content_type": "comment", "object_id": str(comment.id)}
        )
        self.assertFalse(serializer.is_valid())

    def test_valido(self):
        post = _post()
        serializer = LikeToggleSerializer(
            data={"content_type": "feedpost", "object_id": str(post.id)}
        )
        self.assertTrue(serializer.is_valid())


class TestPollCreateSerializer(TestCase):
    def test_pregunta_vacia(self):
        serializer = PollCreateSerializer(data={"question": " ", "options": ["a", "b"]})
        self.assertFalse(serializer.is_valid())

    def test_opciones_duplicadas_se_filtran(self):
        serializer = PollCreateSerializer(
            data={"question": "Q?", "options": ["a", "A", "b"]}
        )
        serializer.is_valid(raise_exception=True)
        self.assertEqual(serializer.validated_data["options"], ["a", "b"])

    def test_menos_de_dos_opciones_validas(self):
        serializer = PollCreateSerializer(
            data={"question": "Q?", "options": ["a", "a"]}
        )
        self.assertFalse(serializer.is_valid())

    def test_create(self):
        serializer = PollCreateSerializer(
            data={"question": "Q?", "options": ["a", "b"]}
        )
        serializer.is_valid(raise_exception=True)
        poll = serializer.save()
        self.assertEqual(poll.options.count(), 2)


class TestPollVoteSerializer(TestCase):
    def setUp(self):
        self.poll = Poll.objects.create(question="Q1")
        self.option = PollOption.objects.create(poll=self.poll, text="A", order=0)
        self.user = IdentityPrincipal(id="u1", username="ana")

    def test_opcion_de_encuesta_inactiva(self):
        self.poll.is_active = False
        self.poll.save()
        serializer = PollVoteSerializer(
            data={"option": str(self.option.id)},
            context={"request": _request(self.user)},
        )
        self.assertFalse(serializer.is_valid())

    def test_opcion_de_encuesta_expirada(self):
        from django.utils import timezone

        self.poll.expires_at = timezone.now() - timezone.timedelta(hours=1)
        self.poll.save()
        serializer = PollVoteSerializer(
            data={"option": str(self.option.id)},
            context={"request": _request(self.user)},
        )
        self.assertFalse(serializer.is_valid())

    def test_ya_voto_encuesta_no_multiple(self):
        PollVote.objects.create(
            user_identity_id="u1", poll=self.poll, option=self.option
        )
        serializer = PollVoteSerializer(
            data={"option": str(self.option.id)},
            context={"request": _request(self.user)},
        )
        self.assertFalse(serializer.is_valid())

    def test_multiple_choice_no_repite_misma_opcion(self):
        self.poll.is_multiple_choice = True
        self.poll.save()
        PollVote.objects.create(
            user_identity_id="u1", poll=self.poll, option=self.option
        )
        serializer = PollVoteSerializer(
            data={"option": str(self.option.id)},
            context={"request": _request(self.user)},
        )
        self.assertFalse(serializer.is_valid())

    def test_create_asigna_usuario_y_poll(self):
        serializer = PollVoteSerializer(
            data={"option": str(self.option.id)},
            context={"request": _request(self.user)},
        )
        serializer.is_valid(raise_exception=True)
        vote = serializer.save()
        self.assertEqual(vote.user_identity_id, "u1")
        self.assertEqual(vote.poll_id, self.poll.id)
