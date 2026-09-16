"""Tests for API-key parsing and the mutation guard."""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.app.api import deps
from api.app.api.deps import key_is_valid, require_api_key
from api.app.config import Settings


def locked(extra=None):
    return SimpleNamespace(api_keys={"s3cret"})


def test_parse_api_keys_comma_separated():
    settings = Settings(api_keys="alpha, beta ,,gamma")
    assert settings.api_keys == {"alpha", "beta", "gamma"}


def test_parse_api_keys_empty_by_default():
    settings = Settings()
    assert settings.api_keys == set()


def test_open_mode_allows_everything(monkeypatch):
    monkeypatch.setattr(deps, "settings", SimpleNamespace(api_keys=set()))
    assert key_is_valid(None) is True
    assert key_is_valid("anything") is True
    assert asyncio.run(require_api_key(None)) is None


def test_locked_mode_checks_membership(monkeypatch):
    monkeypatch.setattr(deps, "settings", locked())
    assert key_is_valid("s3cret") is True
    assert key_is_valid("wrong") is False
    assert key_is_valid(None) is False
    assert asyncio.run(require_api_key("s3cret")) is None


def test_locked_mode_rejects_with_401(monkeypatch):
    monkeypatch.setattr(deps, "settings", locked())
    for provided in (None, "wrong"):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(require_api_key(provided))
        assert exc_info.value.status_code == 401
