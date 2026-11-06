"""Trending ranking shared by FeedService.get_trending_feed and the
/feed/trending/ endpoint (FeedService.get_trending_in_range)."""

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.feeds.domain.entities.feed_post import FeedPost
from apps.feeds.domain.entities.poll import Poll  # noqa: F401
from apps.feeds.domain.services.feed_service import (
    TRENDING_TIME_RANGES,
    FeedService,
    annotate_trending,
)


def _post(content, hours_old, engagement, **kwargs):
    post = FeedPost.objects.create(
        author_identity_id="u1",
        author_snapshot={"id": "u1", "username": "ana"},
        content=content,
        **kwargs,
    )
    FeedPost.objects.filter(pk=post.pk).update(
        created_at=timezone.now() - timedelta(hours=hours_old),
        engagement_score=engagement,
    )
    return post


class TestGetTrendingInRange(TestCase):
    def setUp(self):
        self.service = FeedService()

    def contents(self, posts):
        return [post.content for post in posts]

    def test_orders_by_trending_score(self):
        _post("low", 2, 5.0)
        _post("high", 2, 50.0)
        _post("mid", 2, 20.0)

        posts = self.service.get_trending_in_range("24h", 10)

        self.assertEqual(self.contents(posts), ["high", "mid", "low"])

    def test_each_post_carries_the_annotations_the_view_reads(self):
        _post("only", 3, 10.0)

        post = self.service.get_trending_in_range("24h", 10)[0]

        self.assertGreater(post.trending_score, 0)
        self.assertAlmostEqual(post.hours_old, 3, delta=0.1)

    def test_the_range_limits_the_age_of_the_posts(self):
        _post("today", 2, 10.0)
        _post("this-week", 24 * 3, 10.0)
        _post("this-month", 24 * 20, 10.0)
        _post("old", 24 * 60, 10.0)

        def in_range(name):
            return set(self.contents(self.service.get_trending_in_range(name, 10)))

        self.assertEqual(in_range("24h"), {"today"})
        self.assertEqual(in_range("7d"), {"today", "this-week"})
        self.assertEqual(in_range("30d"), {"today", "this-week", "this-month"})

    def test_an_unknown_range_means_24_hours(self):
        _post("today", 2, 10.0)
        _post("this-week", 24 * 3, 10.0)

        posts = self.service.get_trending_in_range("forever", 10)

        self.assertEqual(self.contents(posts), ["today"])

    def test_private_posts_are_left_out(self):
        _post("public", 2, 10.0)
        _post("private", 2, 99.0, is_public=False)

        posts = self.service.get_trending_in_range("24h", 10)

        self.assertEqual(self.contents(posts), ["public"])

    def test_limit_is_applied(self):
        for index in range(5):
            _post(f"p{index}", 2, float(index))

        self.assertEqual(len(self.service.get_trending_in_range("24h", 3)), 3)

    def test_falls_back_to_most_recent_when_the_ranking_query_fails(self):
        _post("older", 5, 50.0)
        _post("newer", 1, 1.0)

        with patch(
            "apps.feeds.domain.services.feed_service.annotate_trending",
            side_effect=RuntimeError("sql broke"),
        ):
            posts = self.service.get_trending_in_range("24h", 10)

        self.assertEqual(self.contents(posts), ["newer", "older"])


class TestOneFormulaForBothFeeds(TestCase):
    def test_get_trending_feed_ranks_like_the_range_query(self):
        _post("low", 2, 5.0)
        _post("high", 2, 50.0)
        service = FeedService()

        feed_posts, _, _ = service.get_trending_feed(limit=10)
        range_posts = service.get_trending_in_range("24h", 10)

        self.assertEqual(
            [p.content for p in feed_posts], [p.content for p in range_posts]
        )

    def test_annotate_trending_adds_the_three_annotations(self):
        _post("x", 1, 10.0)

        post = annotate_trending(FeedPost.objects.all()).get()

        self.assertTrue(hasattr(post, "trending_score"))
        self.assertTrue(hasattr(post, "hours_old"))
        self.assertEqual(post.comments_count_real, 0)

    def test_supported_ranges(self):
        self.assertEqual(set(TRENDING_TIME_RANGES), {"24h", "7d", "30d"})
