"""Unitarias de FeedService: creacion de posts/comentarios, embeddings,
feeds (personalizado/trending/latest/filtrado), interacciones, likes y
busqueda hibrida."""

from unittest.mock import patch

import requests
from django.test import TestCase

from apps.custom_auth.identity_principal import IdentityPrincipal
from apps.feeds.domain.entities.comment import Comment
from apps.feeds.domain.entities.feed_post import FeedPost

# Import necesario para que Django registre el modelo Poll: FeedPost.poll es
# un OneToOneField lazy hacia "feeds.Poll" que solo se resuelve si algun
# modulo importa poll.py antes de instanciar FeedPost (ver apps/feeds/models.py,
# vacio a proposito: los modelos reales viven en domain/entities/*.py).
from apps.feeds.domain.entities.poll import Poll  # noqa: F401
from apps.feeds.domain.services.feed_service import FeedService

GET_EMBEDDING = "apps.feeds.domain.services.feed_service.requests.post"


def _post(**kwargs):
    defaults = {
        "author_identity_id": "u1",
        "author_snapshot": {"id": "u1", "username": "ana"},
        "content": "hola mundo",
        "is_public": True,
    }
    defaults.update(kwargs)
    return FeedPost.objects.create(**defaults)


class TestGetEmbeddingFromMicroservice(TestCase):
    def setUp(self):
        self.service = FeedService(embedding_service_url="http://embed.local")

    def test_respuesta_200_con_vector_retorna_vector(self):
        mock_resp = type(
            "R", (), {"status_code": 200, "json": lambda self=None: {"vector": [1, 2]}}
        )()
        with patch(GET_EMBEDDING, return_value=mock_resp):
            result = self.service.get_embedding_from_microservice("hola")
        self.assertEqual(result, [1, 2])

    def test_respuesta_200_sin_vector_retorna_none(self):
        mock_resp = type(
            "R", (), {"status_code": 200, "json": lambda self=None: {}}
        )()
        with patch(GET_EMBEDDING, return_value=mock_resp):
            result = self.service.get_embedding_from_microservice("hola")
        self.assertIsNone(result)

    def test_respuesta_no_200_retorna_none(self):
        mock_resp = type(
            "R", (), {"status_code": 500, "text": "err"}
        )()
        with patch(GET_EMBEDDING, return_value=mock_resp):
            result = self.service.get_embedding_from_microservice("hola")
        self.assertIsNone(result)

    def test_excepcion_de_red_retorna_none(self):
        with patch(GET_EMBEDDING, side_effect=requests.ConnectionError("down")):
            result = self.service.get_embedding_from_microservice("hola")
        self.assertIsNone(result)

    def test_excepcion_generica_retorna_none(self):
        with patch(GET_EMBEDDING, side_effect=ValueError("boom")):
            result = self.service.get_embedding_from_microservice("hola")
        self.assertIsNone(result)


class TestCreatePost(TestCase):
    def setUp(self):
        self.service = FeedService()
        self.user = IdentityPrincipal(id="u1", username="ana")

    def test_crea_post_con_author(self):
        with patch(GET_EMBEDDING, side_effect=requests.ConnectionError("down")):
            post = self.service.create_post(author=self.user, content="contenido")
        self.assertIsNotNone(post)
        self.assertEqual(post.author_identity_id, "u1")

    def test_crea_post_con_author_id(self):
        with patch(GET_EMBEDDING, side_effect=requests.ConnectionError("down")):
            post = self.service.create_post(author_id="u9", content="contenido")
        self.assertIsNotNone(post)
        self.assertEqual(post.author_identity_id, "u9")

    def test_sin_author_ni_author_id_retorna_none(self):
        post = self.service.create_post(content="contenido")
        self.assertIsNone(post)

    def test_genera_embedding_si_microservicio_responde(self):
        mock_resp = type(
            "R",
            (),
            {"status_code": 200, "json": lambda self=None: {"vector": [0.1] * 768}},
        )()
        with patch(GET_EMBEDDING, return_value=mock_resp):
            post = self.service.create_post(author=self.user, content="contenido")
        post.refresh_from_db()
        self.assertIsNotNone(post.embedding)


class TestUpdatePostEmbedding(TestCase):
    def setUp(self):
        self.service = FeedService()
        self.post = _post()

    def test_actualiza_embedding_exitosamente(self):
        mock_resp = type(
            "R",
            (),
            {"status_code": 200, "json": lambda self=None: {"vector": [0.1] * 768}},
        )()
        with patch(GET_EMBEDDING, return_value=mock_resp):
            ok = self.service.update_post_embedding(self.post.id)
        self.assertTrue(ok)

    def test_post_no_encontrado_retorna_false(self):
        import uuid

        ok = self.service.update_post_embedding(uuid.uuid4())
        self.assertFalse(ok)

    def test_sin_vector_retorna_false(self):
        with patch(GET_EMBEDDING, side_effect=requests.ConnectionError("down")):
            ok = self.service.update_post_embedding(self.post.id)
        self.assertFalse(ok)

    def test_generate_post_embedding_text_incluye_tags_y_campo(self):
        post = _post(
            content="c",
            tags=["IA"],
            author_snapshot={
                "id": "u1",
                "username": "ana",
                "investigation_camp": "Biologia",
            },
        )
        text = self.service._generate_post_embedding_text(post)
        self.assertIn("Tags: IA", text)
        self.assertIn("Campo: Biologia", text)


class TestGetPersonalizedFeed(TestCase):
    def test_delega_en_trending(self):
        service = FeedService()
        _post()
        posts, has_next, cursor = service.get_personalized_feed(
            user_id="u1", limit=10
        )
        self.assertIsInstance(posts, list)

    def test_con_user_object(self):
        service = FeedService()
        user = IdentityPrincipal(id="u1")
        posts, _, _ = service.get_personalized_feed(user=user, limit=10)
        self.assertIsInstance(posts, list)


class TestGetTrendingFeed(TestCase):
    def setUp(self):
        self.service = FeedService()

    def test_sin_posts_delega_a_latest(self):
        posts, has_next, cursor = self.service.get_trending_feed(limit=10)
        self.assertEqual(posts, [])
        self.assertFalse(has_next)

    def test_con_posts_ordena_por_trending(self):
        _post(engagement_score=1.0)
        _post(engagement_score=5.0)
        posts, has_next, cursor = self.service.get_trending_feed(limit=10)
        self.assertEqual(len(posts), 2)

    def test_excluye_usuario(self):
        own = _post(author_identity_id="u1")
        other = _post(author_identity_id="u2")
        posts, _, _ = self.service.get_trending_feed(limit=10, exclude_user_id="u1")
        ids = [p.id for p in posts]
        self.assertNotIn(own.id, ids)
        self.assertIn(other.id, ids)

    def test_paginacion_con_cursor(self):
        # El cursor pagina por created_at, así que para una secuencia
        # determinista el post con mayor trending_score (mostrado primero)
        # debe ser tambien el mas reciente cronologicamente.
        older = _post(engagement_score=0)
        newer = _post(engagement_score=100)
        posts, has_next, next_cursor = self.service.get_trending_feed(limit=1)
        self.assertEqual(posts, [newer])
        self.assertTrue(has_next)

        more, _, _ = self.service.get_trending_feed(limit=1, cursor=next_cursor)
        self.assertEqual(more, [older])

    def test_excepcion_delega_a_latest(self):
        with patch(
            "apps.feeds.domain.services.feed_service.FeedPost.objects.filter",
            side_effect=Exception("db error"),
        ):
            posts, has_next, cursor = self.service.get_trending_feed(limit=10)
        self.assertEqual(posts, [])


class TestGetLatestFeed(TestCase):
    def setUp(self):
        self.service = FeedService()

    def test_feed_vacio(self):
        posts, has_next, cursor = self.service.get_latest_feed()
        self.assertEqual(posts, [])
        self.assertFalse(has_next)

    def test_orden_por_creacion_y_paginacion(self):
        _post()
        _post()
        posts, has_next, next_cursor = self.service.get_latest_feed(limit=1)
        self.assertEqual(len(posts), 1)
        self.assertTrue(has_next)
        self.assertIsNotNone(next_cursor)

    def test_excluye_usuario(self):
        own = _post(author_identity_id="u1")
        _post(author_identity_id="u2")
        posts, _, _ = self.service.get_latest_feed(exclude_user_id="u1")
        ids = [p.id for p in posts]
        self.assertNotIn(own.id, ids)


class TestHandleUserInteraction(TestCase):
    def test_view_incrementa_contador_y_engagement(self):
        post = _post()
        service = FeedService()
        service.handle_user_interaction(
            user_id="u1", post_id=str(post.id), interaction_type="view"
        )
        post.refresh_from_db()
        self.assertEqual(post.views_count, 1)

    def test_share_incrementa_contador(self):
        post = _post()
        service = FeedService()
        service.handle_user_interaction(
            user_id="u1", post_id=str(post.id), interaction_type="share"
        )
        post.refresh_from_db()
        self.assertEqual(post.shares_count, 1)

    def test_click_no_incrementa_contadores_pero_no_falla(self):
        post = _post()
        service = FeedService()
        service.handle_user_interaction(
            user_id="u1", post_id=str(post.id), interaction_type="click"
        )
        post.refresh_from_db()
        self.assertEqual(post.views_count, 0)

    def test_post_inexistente_no_lanza(self):
        import uuid

        service = FeedService()
        service.handle_user_interaction(
            user_id="u1", post_id=str(uuid.uuid4()), interaction_type="view"
        )


class TestCreateComment(TestCase):
    def setUp(self):
        self.service = FeedService()
        self.post = _post()

    def test_crea_comentario_raiz(self):
        comment = self.service.create_comment(
            author_id="u1", post_id=self.post.id, content="hola"
        )
        self.assertIsNotNone(comment)
        self.assertEqual(comment.content, "hola")

    def test_crea_respuesta(self):
        root = self.service.create_comment(
            author_id="u1", post_id=self.post.id, content="raiz"
        )
        reply = self.service.create_comment(
            author_id="u2",
            post_id=self.post.id,
            content="respuesta",
            parent_comment_id=root.id,
        )
        self.assertEqual(reply.parent_comment_id, root.id)

    def test_maximo_de_anidacion_retorna_none(self):
        parent_id = None
        comment = None
        for _ in range(7):
            comment = self.service.create_comment(
                author_id="u1",
                post_id=self.post.id,
                content="c",
                parent_comment_id=parent_id,
            )
            if comment is None:
                break
            parent_id = comment.id
        self.assertIsNone(comment)

    def test_post_inexistente_retorna_none(self):
        import uuid

        comment = self.service.create_comment(
            author_id="u1", post_id=uuid.uuid4(), content="c"
        )
        self.assertIsNone(comment)


class TestToggleLike(TestCase):
    def test_toggle_like_en_post(self):
        post = _post()
        user = IdentityPrincipal(id="u1")
        service = FeedService()
        created = service.toggle_like(user, post)
        self.assertTrue(created)

    def test_toggle_like_excepcion_retorna_false(self):
        service = FeedService()
        user = IdentityPrincipal(id="u1")
        with patch(
            "apps.feeds.domain.services.feed_service.Like.toggle_like",
            side_effect=Exception("boom"),
        ):
            result = service.toggle_like(user, _post())
        self.assertFalse(result)

    def test_toggle_comment_like(self):
        post = _post()
        comment = Comment.objects.create(
            post=post, author_identity_id="u1", content="c"
        )
        user = IdentityPrincipal(id="u2")
        service = FeedService()
        created = service.toggle_comment_like(user, comment)
        self.assertTrue(created)

    def test_toggle_comment_like_excepcion_retorna_false(self):
        service = FeedService()
        user = IdentityPrincipal(id="u1")
        comment = Comment.objects.create(
            post=_post(), author_identity_id="u1", content="c"
        )
        with patch(
            "apps.feeds.domain.services.feed_service.Like.toggle_like",
            side_effect=Exception("boom"),
        ):
            result = service.toggle_comment_like(user, comment)
        self.assertFalse(result)


class TestGetFilteredFeed(TestCase):
    def setUp(self):
        self.service = FeedService()
        self.user = IdentityPrincipal(id="u1")

    def test_feed_type_por_defecto(self):
        _post(tags=["ia"])
        posts, has_next, cursor = self.service.get_filtered_feed(
            user=self.user, feed_type="default", filters={}
        )
        self.assertEqual(len(posts), 1)

    def test_filtra_por_tags(self):
        match = _post(tags=["ia"])
        _post(tags=["otro"])
        posts, _, _ = self.service.get_filtered_feed(
            user=self.user, feed_type="default", filters={"tags": ["ia"]}
        )
        self.assertEqual([p.id for p in posts], [match.id])

    def test_filtra_por_author_ids(self):
        match = _post(author_identity_id="5")
        _post(author_identity_id="9")
        posts, _, _ = self.service.get_filtered_feed(
            user=self.user, feed_type="default", filters={"author_ids": [5]}
        )
        self.assertEqual([p.id for p in posts], [match.id])

    def test_filtra_por_fechas(self):
        from django.utils import timezone

        _post()
        posts, _, _ = self.service.get_filtered_feed(
            user=self.user,
            feed_type="default",
            filters={"date_from": timezone.now() - timezone.timedelta(days=1)},
        )
        self.assertEqual(len(posts), 1)

    def test_feed_type_trending(self):
        _post(engagement_score=1.0)
        posts, _, _ = self.service.get_filtered_feed(
            user=self.user, feed_type="trending", filters={}
        )
        self.assertIsInstance(posts, list)

    def test_feed_type_personalized(self):
        _post()
        posts, _, _ = self.service.get_filtered_feed(
            user=self.user, feed_type="personalized", filters={}
        )
        self.assertIsInstance(posts, list)

    def test_excepcion_retorna_vacio(self):
        with patch(
            "apps.feeds.domain.services.feed_service.FeedPost.objects.filter",
            side_effect=Exception("boom"),
        ):
            posts, has_next, cursor = self.service.get_filtered_feed(
                user=self.user, feed_type="default", filters={}
            )
        self.assertEqual(posts, [])
        self.assertFalse(has_next)


class TestPreprocessSearchQuery(TestCase):
    def test_normaliza_espacios(self):
        service = FeedService()
        self.assertEqual(service._preprocess_search_query("  a   b  "), "a b")

    def test_vacio(self):
        service = FeedService()
        self.assertEqual(service._preprocess_search_query(""), "")
        self.assertEqual(service._preprocess_search_query(None), "")


class TestSearchPostsBySimilarity(TestCase):
    def setUp(self):
        self.service = FeedService()

    def test_query_vacio_retorna_lista_vacia(self):
        result = self.service.search_posts_by_similarity("  ")
        self.assertEqual(result, [])

    def test_sin_embedding_del_microservicio_fallback_a_texto(self):
        _post(content="hola desde texto plano suficientemente largo para pasar filtros")
        with patch(GET_EMBEDDING, side_effect=requests.ConnectionError("down")):
            result = self.service.search_posts_by_similarity("hola")
        self.assertIsInstance(result, list)

    def test_excepcion_general_fallback_a_texto(self):
        _post(content="contenido de respaldo bastante largo para superar el filtro")
        mock_resp = type(
            "R",
            (),
            {
                "status_code": 200,
                "json": lambda self=None: {"vector": [0.1] * 768, "processed_text": "x"},
            },
        )()
        with (
            patch(
                "apps.feeds.domain.services.feed_service.requests.post",
                return_value=mock_resp,
            ),
            patch(
                "apps.feeds.domain.services.feed_service.RawSQL",
                side_effect=Exception("boom"),
            ),
        ):
            result = self.service.search_posts_by_similarity("contenido")
        self.assertIsInstance(result, list)
