"""The pgvector queries receive the embedding as a query parameter and still rank
by similarity (as opposed to silently falling back to text search)."""

from unittest.mock import MagicMock

from django.test import TestCase

from apps.feeds.domain.entities.feed_post import FeedPost
from apps.feeds.domain.entities.poll import Poll  # noqa: F401
from apps.feeds.domain.services.feed_service import FeedService
from apps.jobs.domain.entities.company import Company
from apps.jobs.domain.entities.jobs import Jobs
from apps.jobs.domain.services.jobs_service import JobsService
from apps.shared.embedding_client import TextVector


def vector(hot):
    """A 768-d vector with a single non-zero component."""
    values = [0.0] * 768
    values[hot] = 1.0
    return values


class TestFeedSearchUsesTheVector(TestCase):
    def setUp(self):
        self.embeddings = MagicMock()
        self.service = FeedService(embeddings=self.embeddings)

    def post(self, content, hot):
        post = FeedPost.objects.create(
            author_identity_id="u1",
            author_snapshot={"id": "u1", "username": "ana"},
            content=content,
            is_public=True,
        )
        FeedPost.objects.filter(pk=post.pk).update(embedding=vector(hot))
        return post

    def test_ranks_by_cosine_similarity_to_the_query_vector(self):
        near = self.post("Machine learning para diagnostico medico", hot=3)
        self.post("Despliegue continuo con Docker y Kubernetes", hot=500)
        self.embeddings.vectorize.return_value = TextVector(vector(3), "machine")

        posts = self.service.search_posts_by_similarity("machine learning", limit=5)

        self.assertEqual([p.id for p in posts], [near.id])
        self.assertAlmostEqual(posts[0].similarity, 1.0, places=3)
        self.assertGreater(posts[0].relevance_score, 0)

    def test_a_quote_in_the_text_cannot_break_the_query(self):
        near = self.post("Machine learning para diagnostico medico", hot=3)
        self.embeddings.vectorize.return_value = TextVector(vector(3), "it's")

        posts = self.service.search_posts_by_similarity("l'amour; DROP TABLE x --")

        self.assertEqual(FeedPost.objects.filter(pk=near.pk).count(), 1)
        self.assertIsInstance(posts, list)


class TestJobSemanticSearchUsesTheVector(TestCase):
    def test_orders_jobs_by_similarity_to_the_query_vector(self):
        company = Company.objects.create_user(
            username="empresa@example.com", password="x12345678", company_name="E"
        )
        near = Jobs.objects.create(company=company, title="Near", description="d")
        far = Jobs.objects.create(company=company, title="Far", description="d")
        Jobs.objects.filter(pk=near.pk).update(embedding=vector(7))
        Jobs.objects.filter(pk=far.pk).update(embedding=vector(300))
        embeddings = MagicMock()
        embeddings.embed.return_value = vector(7)

        jobs = list(JobsService(embeddings=embeddings).semantic_search_jobs("query"))

        self.assertEqual([j.title for j in jobs][0], "Near")
        self.assertTrue(hasattr(jobs[0], "similarity"))
