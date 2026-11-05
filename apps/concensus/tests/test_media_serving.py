"""Uploaded media must be served regardless of DEBUG (the gateway proxies
/media/ to this service)."""

from pathlib import Path

import pytest
from django.conf import settings
from django.test import Client, override_settings


@pytest.fixture
def media_file():
    directory = Path(settings.MEDIA_ROOT) / "feed_posts"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "zz-test-media-serving.png"
    path.write_bytes(b"\x89PNG-test")
    yield path
    path.unlink(missing_ok=True)


@override_settings(DEBUG=False)
def test_serves_existing_file_with_debug_off(media_file):
    response = Client().get("/media/feed_posts/zz-test-media-serving.png")

    assert response.status_code == 200
    assert b"".join(response.streaming_content) == b"\x89PNG-test"


@override_settings(DEBUG=False)
def test_missing_file_is_404():
    assert Client().get("/media/feed_posts/does-not-exist.png").status_code == 404
