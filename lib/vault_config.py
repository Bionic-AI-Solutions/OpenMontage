"""Load OpenMontage API keys from HashiCorp Vault KV v2.

Cluster path convention (same as other apps):
  secret/data/t6-apps/<app-slug>/config

Required env:
  VAULT_HOST   – primary (matches .env), e.g. https://vault.baisoln.com
                 In-cluster: http://vault.vault.svc.cluster.local:8200
  VAULT_TOKEN  – token with read on the app path (and shared/* if used)

Optional:
  VAULT_ADDR           – alias for VAULT_HOST
  VAULT_APP_SLUG       – defaults to "openmontage"
  VAULT_SKIP_LOAD=true – skip loading (tests / local .env-only)
  VAULT_LOAD_SHARED=true – also merge secret/data/shared/api-keys (default true)

Vault keys are stored as lowercase_snake_case and mapped to UPPER_SNAKE
process.env keys (e.g. openai_api_key → OPENAI_API_KEY). Existing non-empty
environment variables are preserved (K8s / shell / .env overrides win).
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_APP_SLUG = "openmontage"

# Keys from secret/shared/api-keys that OpenMontage tools consume, plus any
# extra env aliases to apply after the primary uppercase mapping.
SHARED_KEY_ALIASES: dict[str, tuple[str, ...]] = {
    "openai_api_key": ("OPENAI_API_KEY",),
    "elevenlabs_api_key": ("ELEVENLABS_API_KEY",),
    "gemini_api_key": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "hf_token": ("HF_TOKEN",),
    "anthropic_api_key": ("ANTHROPIC_API_KEY",),
    "openrouter_api_key": ("OPENROUTER_API_KEY",),
    # Stored uppercase in Vault (unlike most shared keys).
    "SARVAM_API_KEY": ("SARVAM_API_KEY",),
    "mcp_api_key": ("MCP_API_KEY", "GPU_AI_API_KEY"),
}

# Skip injecting these vault fields into the process environment.
_SKIP_VAULT_KEYS = frozenset({"vault_token", "placeholder"})


@dataclass
class LoadVaultConfigResult:
    loaded: bool = False
    path: str = ""
    keys_applied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    error: Optional[str] = None


def _resolve_vault_host() -> str:
    return (os.environ.get("VAULT_HOST") or os.environ.get("VAULT_ADDR") or "").strip()


def _normalize_vault_host(raw: str) -> str:
    trimmed = raw.strip().rstrip("/")
    if not trimmed:
        return trimmed
    if trimmed.lower().startswith(("http://", "https://")):
        return trimmed
    return f"https://{trimmed}"


def _to_env_key(vault_key: str) -> str:
    return vault_key.strip().upper()


def _vault_get_kv(vault_host: str, token: str, path: str) -> dict[str, object]:
    """GET a KV v2 secret. ``path`` is like ``secret/data/t6-apps/foo/config``."""
    url = f"{vault_host}/v1/{path}"
    req = urllib.request.Request(
        url,
        headers={
            "X-Vault-Token": token,
            "Accept": "application/json",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    data = payload.get("data") or {}
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        return data["data"]
    if isinstance(data, dict):
        return data
    return {}


def _apply_entries(
    data: dict[str, object],
    *,
    aliases: Optional[dict[str, tuple[str, ...]]] = None,
) -> tuple[list[str], list[str]]:
    """Apply vault key/values into os.environ. Returns (applied, skipped)."""
    keys_applied: list[str] = []
    skipped: list[str] = []

    for vault_key, value in data.items():
        if value is None:
            continue
        if vault_key in _SKIP_VAULT_KEYS:
            skipped.append(vault_key)
            continue

        as_string = value if isinstance(value, str) else str(value)
        if as_string == "":
            continue

        env_targets = list(aliases.get(vault_key, ())) if aliases else ()
        if not env_targets:
            env_targets = (_to_env_key(vault_key),)

        for env_key in env_targets:
            existing = os.environ.get(env_key)
            if existing is not None and existing != "":
                skipped.append(env_key)
                continue
            os.environ[env_key] = as_string
            keys_applied.append(env_key)

    return keys_applied, skipped


def load_vault_config() -> LoadVaultConfigResult:
    """Fetch app config from Vault and inject into ``os.environ``.

    Safe to call multiple times; later calls skip keys already set.
    """
    empty = LoadVaultConfigResult()

    if os.environ.get("VAULT_SKIP_LOAD", "").lower() in {"1", "true", "yes"}:
        return empty

    host_raw = _resolve_vault_host()
    token = os.environ.get("VAULT_TOKEN") or ""
    slug = os.environ.get("VAULT_APP_SLUG") or DEFAULT_APP_SLUG

    if not host_raw or not token:
        return empty

    vault_host = _normalize_vault_host(host_raw)
    path = f"secret/data/t6-apps/{slug}/config"
    keys_applied: list[str] = []
    skipped: list[str] = []

    try:
        data = _vault_get_kv(vault_host, token, path)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        err = f"Vault GET {path} failed ({exc.code}): {body}"
        logger.warning(err)
        return LoadVaultConfigResult(path=path, error=err)
    except Exception as exc:  # noqa: BLE001 — surface as soft failure
        err = f"Vault GET {path} failed: {exc}"
        logger.warning(err)
        return LoadVaultConfigResult(path=path, error=err)

    applied, skip = _apply_entries(data)
    keys_applied.extend(applied)
    skipped.extend(skip)

    load_shared = os.environ.get("VAULT_LOAD_SHARED", "true").lower() in {
        "1",
        "true",
        "yes",
        "",
    }
    if load_shared:
        shared_path = "secret/data/shared/api-keys"
        try:
            shared = _vault_get_kv(vault_host, token, shared_path)
            # Only apply keys we know how to map into OpenMontage env vars.
            filtered = {
                k: v for k, v in shared.items() if k in SHARED_KEY_ALIASES
            }
            applied, skip = _apply_entries(filtered, aliases=SHARED_KEY_ALIASES)
            keys_applied.extend(applied)
            skipped.extend(skip)
        except Exception as exc:  # noqa: BLE001
            logger.info("Vault shared/api-keys not merged: %s", exc)

    # Convenience alias: if GEMINI is set but GOOGLE is not, mirror it.
    gemini = os.environ.get("GEMINI_API_KEY") or ""
    if gemini and not os.environ.get("GOOGLE_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = gemini
        if "GOOGLE_API_KEY" not in keys_applied:
            keys_applied.append("GOOGLE_API_KEY")

    return LoadVaultConfigResult(
        loaded=True,
        path=path,
        keys_applied=keys_applied,
        skipped=skipped,
    )


def ensure_vault_config_loaded() -> LoadVaultConfigResult:
    """Idempotent entrypoint used at process start."""
    return load_vault_config()
