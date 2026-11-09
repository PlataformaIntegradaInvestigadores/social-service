"""ALLOWED_HOSTS must be explicit unless DEBUG is on."""

import importlib
from unittest.mock import patch

import pytest
from django.core.exceptions import ImproperlyConfigured

from project import settings as project_settings


def _reload():
    # load_dotenv would read a developer's local .env and hide what the test sets.
    with patch("dotenv.load_dotenv"):
        return importlib.reload(project_settings)


@pytest.fixture(autouse=True)
def restore_settings_module(monkeypatch):
    yield
    monkeypatch.undo()
    importlib.reload(project_settings)


def test_hosts_are_required_when_debug_is_off(monkeypatch):
    monkeypatch.setenv("DEBUG", "False")
    monkeypatch.delenv("ALLOWED_HOSTS", raising=False)

    with pytest.raises(ImproperlyConfigured, match="ALLOWED_HOSTS"):
        _reload()


def test_an_empty_value_counts_as_missing(monkeypatch):
    monkeypatch.setenv("DEBUG", "False")
    monkeypatch.setenv("ALLOWED_HOSTS", " , ")

    with pytest.raises(ImproperlyConfigured):
        _reload()


def test_debug_accepts_any_host_when_none_is_configured(monkeypatch):
    monkeypatch.setenv("DEBUG", "True")
    monkeypatch.delenv("ALLOWED_HOSTS", raising=False)

    assert _reload().ALLOWED_HOSTS == ["*"]


def test_configured_hosts_are_used_as_given(monkeypatch):
    monkeypatch.setenv("DEBUG", "False")
    monkeypatch.setenv("ALLOWED_HOSTS", "a.example.com, b.example.com")

    assert _reload().ALLOWED_HOSTS == ["a.example.com", "b.example.com"]
