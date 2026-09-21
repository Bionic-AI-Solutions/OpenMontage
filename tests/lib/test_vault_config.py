"""Unit tests for Vault config loader (mocked HTTP)."""

from __future__ import annotations

import json
import os
from io import BytesIO
from urllib.error import HTTPError

import pytest

from lib import vault_config


class _FakeResp:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_load_vault_config_applies_keys(monkeypatch):
    monkeypatch.setenv("VAULT_HOST", "http://vault.test:8200")
    monkeypatch.setenv("VAULT_TOKEN", "test-token")
    monkeypatch.setenv("VAULT_APP_SLUG", "openmontage")
    monkeypatch.setenv("VAULT_LOAD_SHARED", "false")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

    calls: list[str] = []

    def fake_urlopen(req, timeout=15):
        calls.append(req.full_url)
        headers = {k.lower(): v for k, v in req.header_items()}
        assert headers.get("x-vault-token") == "test-token"
        return _FakeResp(
            {
                "data": {
                    "data": {
                        "openai_api_key": "sk-test",
                        "elevenlabs_api_key": "el-test",
                        "vault_token": "should-skip",
                    }
                }
            }
        )

    monkeypatch.setattr(vault_config.urllib.request, "urlopen", fake_urlopen)

    result = vault_config.load_vault_config()
    assert result.loaded is True
    assert result.path == "secret/data/t6-apps/openmontage/config"
    assert os.environ["OPENAI_API_KEY"] == "sk-test"
    assert os.environ["ELEVENLABS_API_KEY"] == "el-test"
    assert "OPENAI_API_KEY" in result.keys_applied
    assert "vault_token" in result.skipped
    assert any("t6-apps/openmontage/config" in u for u in calls)


def test_existing_env_wins(monkeypatch):
    monkeypatch.setenv("VAULT_HOST", "http://vault.test:8200")
    monkeypatch.setenv("VAULT_TOKEN", "test-token")
    monkeypatch.setenv("VAULT_LOAD_SHARED", "false")
    monkeypatch.setenv("OPENAI_API_KEY", "already-set")

    def fake_urlopen(req, timeout=15):
        return _FakeResp({"data": {"data": {"openai_api_key": "from-vault"}}})

    monkeypatch.setattr(vault_config.urllib.request, "urlopen", fake_urlopen)
    result = vault_config.load_vault_config()
    assert os.environ["OPENAI_API_KEY"] == "already-set"
    assert "OPENAI_API_KEY" in result.skipped


def test_skip_load(monkeypatch):
    monkeypatch.setenv("VAULT_SKIP_LOAD", "true")
    monkeypatch.setenv("VAULT_HOST", "http://vault.test:8200")
    monkeypatch.setenv("VAULT_TOKEN", "test-token")
    result = vault_config.load_vault_config()
    assert result.loaded is False
    assert result.path == ""


def test_shared_api_keys_aliases(monkeypatch):
    monkeypatch.setenv("VAULT_HOST", "http://vault.test:8200")
    monkeypatch.setenv("VAULT_TOKEN", "test-token")
    monkeypatch.setenv("VAULT_LOAD_SHARED", "true")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)

    def fake_urlopen(req, timeout=15):
        url = req.full_url
        if "shared/api-keys" in url:
            return _FakeResp(
                {
                    "data": {
                        "data": {
                            "gemini_api_key": "gem-1",
                            "hf_token": "hf-1",
                            "firecrawl_api_key": "ignored",
                        }
                    }
                }
            )
        return _FakeResp({"data": {"data": {}}})

    monkeypatch.setattr(vault_config.urllib.request, "urlopen", fake_urlopen)
    result = vault_config.load_vault_config()
    assert os.environ["GEMINI_API_KEY"] == "gem-1"
    assert os.environ["GOOGLE_API_KEY"] == "gem-1"
    assert os.environ["HF_TOKEN"] == "hf-1"
    assert "GEMINI_API_KEY" in result.keys_applied


def test_http_error_soft_fails(monkeypatch):
    monkeypatch.setenv("VAULT_HOST", "http://vault.test:8200")
    monkeypatch.setenv("VAULT_TOKEN", "test-token")
    monkeypatch.setenv("VAULT_LOAD_SHARED", "false")

    def fake_urlopen(req, timeout=15):
        raise HTTPError(
            req.full_url, 403, "Forbidden", hdrs=None, fp=BytesIO(b'{"errors":["denied"]}')
        )

    monkeypatch.setattr(vault_config.urllib.request, "urlopen", fake_urlopen)
    result = vault_config.load_vault_config()
    assert result.loaded is False
    assert result.error is not None
    assert "403" in result.error
