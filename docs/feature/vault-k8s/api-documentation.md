# API Documentation: Vault Config + Kubernetes Deploy

## Base URLs

| Surface | URL |
|---------|-----|
| Backlot (in-cluster Service) | `http://openmontage.openmontage.svc.cluster.local` |
| Backlot (Ingress) | `https://om.baisoln.com` |
| Backlot (pod direct) | `http://<pod-ip>:4750` |
| Vault (in-cluster) | `http://vault.vault.svc.cluster.local:8200` |
| Vault (public, Cloudflare Access) | `https://vault.baisoln.com` |
| Deploy entrypoint | `k8s-infrastructure/deploy/tier6-apps/deploy-openmontage.sh` |

## Authentication

### Vault
- Header: `X-Vault-Token: <token>`
- Runtime pods use the minted `vault_token` from `secret/t6-apps/openmontage/config` (synced into K8s Secret as `VAULT_TOKEN`).
- Seed/mint operations require an admin/root token (from `.env` `VAULT_TOKEN` or `k8s-infrastructure/deploy/vault/.vault-admin-token`).

### Backlot
- No auth on the board HTTP API in the current deploy (ClusterIP only). Do not expose without an Ingress auth layer.

## Vault HTTP Endpoints (used by the app)

### GET `/v1/secret/data/t6-apps/{slug}/config`

**Description:** Read OpenMontage app configuration (KV v2).

**Headers:**
- `X-Vault-Token` (required)
- `Accept: application/json`

**Default slug:** `openmontage` (`VAULT_APP_SLUG`)

**Success response (shape):**
```json
{
  "data": {
    "data": {
      "openai_api_key": "<redacted>",
      "elevenlabs_api_key": "<redacted>",
      "gemini_api_key": "<redacted>",
      "google_api_key": "<redacted>",
      "hf_token": "<redacted>",
      "vault_token": "<redacted>"
    }
  }
}
```

**Error responses:**
- `403 Forbidden` — token lacks capability (loader soft-fails, logs warning)
- `404 Not Found` — path not seeded

### GET `/v1/secret/data/shared/api-keys`

**Description:** Optional merge of org-wide API keys (`VAULT_LOAD_SHARED=true`).

Only keys listed in `SHARED_KEY_ALIASES` inside `lib/vault_config.py` are applied.

## Python loader API

### `load_vault_config() -> LoadVaultConfigResult`

```python
from lib.vault_config import load_vault_config

result = load_vault_config()
# result.loaded: bool
# result.path: str          # e.g. secret/data/t6-apps/openmontage/config
# result.keys_applied: list[str]
# result.skipped: list[str]
# result.error: str | None
```

**Env controls:**

| Variable | Default | Meaning |
|----------|---------|---------|
| `VAULT_HOST` | — | Primary Vault base URL |
| `VAULT_ADDR` | — | Alias for `VAULT_HOST` |
| `VAULT_TOKEN` | — | Token for X-Vault-Token |
| `VAULT_APP_SLUG` | `openmontage` | App path segment |
| `VAULT_SKIP_LOAD` | `false` | Skip entirely |
| `VAULT_LOAD_SHARED` | `true` | Also merge `shared/api-keys` |

**Behavior:**
- Empty / missing host or token → no-op (`loaded=False`)
- Non-empty existing `os.environ` values are never overwritten
- `vault_token` field from the secret payload is not re-injected as a consumer config key

## Backlot HTTP Endpoints (deployed)

### GET `/api/health`

**Description:** Liveness/readiness probe target.

**Response:**
```json
{"ok": true, "app": "backlot"}
```

### GET `/api/projects`

**Description:** List project summaries from the projects directory.

### GET `/api/project/{project_id}/state`

**Description:** Full board state for one project.

### GET `/api/project/{project_id}/events`

**Description:** SSE change feed for a project.

## Rate Limiting
None at the OpenMontage layer. Vault and upstream provider APIs enforce their own limits.

## SDKs and Examples

### Load secrets in a script
```python
from lib.env_loader import load_env
import os

load_env()
assert os.environ.get("OPENAI_API_KEY"), "missing OpenAI key from Vault/.env"
```

### Port-forward Backlot
```bash
kubectl -n openmontage port-forward svc/openmontage 4750:80
curl -s http://127.0.0.1:4750/api/health
```
