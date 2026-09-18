from django.http import QueryDict
from django.test import SimpleTestCase, TestCase

from apps.feeds.domain.entities.feed_post import FeedPost
from apps.feeds.infrastructure.api.v1.serializers.feed_post_serializers import (
    FlexibleTagsField,
)
from apps.feeds.infrastructure.api.v1.views.feed_post_views import (
    _filter_queryset_by_tags,
    _parse_search_tags,
    _post_matches_any_tag,
)


class TagParameterTests(SimpleTestCase):
    def test_accepts_repeated_and_comma_separated_tags(self):
        params = QueryDict('tags=IA,Gateway&tags=%23DataScience&tags=ia')

        self.assertEqual(
            _parse_search_tags(params),
            ['ia', 'gateway', 'datascience'],
        )

    def test_matches_tags_case_insensitively(self):
        post = FeedPost(tags=['IA', 'Microservicios'])

        self.assertTrue(_post_matches_any_tag(post, ['ia']))
        self.assertFalse(_post_matches_any_tag(post, ['gateway']))

    def test_serializer_cleans_hashes_and_case_insensitive_duplicates(self):
        field = FlexibleTagsField()

        self.assertEqual(
            field.to_internal_value([' #IA ', 'ia', 'MachineLearning']),
            ['IA', 'MachineLearning'],
        )


class TagQueryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ia_post = FeedPost.objects.create(
            author_identity_id='researcher-1',
            content='Post about artificial intelligence',
            tags=['IA', 'Microservicios'],
        )
        cls.gateway_post = FeedPost.objects.create(
            author_identity_id='researcher-2',
            content='Post about gateways',
            tags=['Gateway'],
        )

    def test_json_tags_are_filtered_case_insensitively(self):
        queryset = _filter_queryset_by_tags(
            FeedPost.objects.filter(is_public=True),
            ['ia'],
        )

        self.assertEqual(list(queryset.values_list('id', flat=True)), [self.ia_post.id])

    def test_multiple_tags_use_any_match_semantics(self):
        queryset = _filter_queryset_by_tags(
            FeedPost.objects.filter(is_public=True),
            ['ia', 'gateway'],
        )

        self.assertSetEqual(
            set(queryset.values_list('id', flat=True)),
            {self.ia_post.id, self.gateway_post.id},
        )
