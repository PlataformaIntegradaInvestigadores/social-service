"""Uploaded media must be served regardless of DEBUG (the gateway proxies
/media/ to this service), but safely and only for the public directories."""

from pathlib import Path

import pytest
from django.conf import settings
from django.test import Client, override_settings


@pytest.fixture
def make_media():
    created = []

    def _make(directory, name, content):
        folder = Path(settings.MEDIA_ROOT) / directory
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / name
        path.write_bytes(content)
        created.append(path)
        return path

    yield _make
    for path in created:
        path.unlink(missing_ok=True)


@override_settings(DEBUG=False)
def test_serves_image_with_debug_off_and_hardened_headers(make_media):
    make_media("feed_posts", "zz-test-media.png", b"\x89PNG-test")

    response = Client().get("/media/feed_posts/zz-test-media.png")

    assert response.status_code == 200
    assert b"".join(response.streaming_content) == b"\x89PNG-test"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert "sandbox" in response["Content-Security-Policy"]
    assert "attachment" not in response.get("Content-Disposition", "")


@override_settings(DEBUG=False)
def test_company_logos_are_public(make_media):
    make_media("company_logos", "zz-test-logo.png", b"\x89PNG-logo")

    assert Client().get("/media/company_logos/zz-test-logo.png").status_code == 200


@override_settings(DEBUG=False)
def test_non_image_is_forced_to_download(make_media):
    make_media("feed_posts", "zz-test-media.html", b"<script>1</script>")

    response = Client().get("/media/feed_posts/zz-test-media.html")

    assert response.status_code == 200
    assert response["Content-Disposition"] == "attachment"
    assert response["X-Content-Type-Options"] == "nosniff"


@override_settings(DEBUG=False)
def test_missing_file_is_404():
    assert Client().get("/media/feed_posts/does-not-exist.png").status_code == 404


@override_settings(DEBUG=False)
def test_resumes_are_not_public(make_media):
    make_media("resumes", "zz-test-cv.pdf", b"%PDF-private")

    assert Client().get("/media/resumes/zz-test-cv.pdf").status_code == 404
