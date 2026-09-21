# Technical Architecture: Vault Config + Kubernetes Deploy

## Architecture Overview

```
┌─────────────────┐     GET /v1/secret/data/...      ┌──────────────────────┐
│ OpenMontage pod │ ───────────────────────────────► │ Vault (in-cluster)   │
│ Backlot + tools │                                  │ KV v2 mount: secret  │
└────────┬────────┘                                  └──────────┬───────────┘
         │ envFrom (ConfigMap + Secret)                         │
         │                                                      │
         ▼                                                      │
┌─────────────────┐     ExternalSecret (ESO)                    │
│ ConfigMap       │ ◄───────────────────────────────────────────┤
│ (VAULT_HOST…)   │                                             │
│ K8s Secret      │ ◄── t6-apps/openmontage/config + shared/* ──┘
│ (VAULT_TOKEN +  │
│  API keys)      │
└─────────────────┘
```

At process start:

1. Load local `.env` (if present; empty values ignored for overlay purposes).
2. `load_vault_config()` reads `secret/data/t6-apps/<slug>/config`.
3. Optionally merges mapped keys from `secret/data/shared/api-keys`.
4. Tools read `os.environ` as before (`OPENAI_API_KEY`, etc.).

## Components

### Vault loader (`lib/vault_config.py`)
- **Purpose:** Fetch KV v2 secrets and inject into `os.environ`.
- **Technologies:** stdlib `urllib` + JSON (no extra dependency).
- **Interfaces:** `load_vault_config()` → `LoadVaultConfigResult`.

### Startup wiring
- `tools/base_tool.py` — dotenv then Vault (all tool imports).
- `lib/env_loader.py` — same for callers using `load_env()`.
- `backlot/__main__.py` — bootstrap before serve/open; bind host from `BACKLOT_HOST`.

### Seed / deploy script (Deploy repo)
- **Path:** `k8s-infrastructure/deploy/tier6-apps/deploy-openmontage.sh`
- **Manifests:** `k8s-infrastructure/deploy/tier6-apps/manifests/openmontage/`
- **ESO:** `k8s-infrastructure/deploy/vault/apps/openmontage/external-secret.yaml`
- **Purpose:** Copy shared keys into app path, write policy, mint token, apply manifests.
- **Runs Vault CLI inside `vault-0` via `kubectl exec`** (bypasses Cloudflare Access on the public hostname).
- No OpenMontage application checkout is required to deploy (image pulled from Docker Hub).

### Container
- **Image:** `docker.io/docker4zerocool/openmontage:latest`
- **Entry:** `python -m backlot serve --host 0.0.0.0 --port 4750`
- **Health:** `GET /api/health`

### Kubernetes
| Resource | Name | Role |
|----------|------|------|
| Namespace | `openmontage` | Isolation |
| ExternalSecret | `openmontage-secrets` | Sync Vault → Secret |
| ExternalSecret | `dockerhub-pull-secret` | Pull credentials |
| ConfigMap | `openmontage-config` | `VAULT_HOST`, slug, ports |
| PVC | `openmontage-projects` | Persistent `projects/` |
| Deployment | `openmontage` | Backlot runtime |
| Service | `openmontage` | ClusterIP :80 → :4750 |
| Ingress | `openmontage` | Kong → `om.baisoln.com` |

## Data Flow

1. **Seed (admin):** `shared/api-keys` → patch/put `t6-apps/openmontage/config` + mint `vault_token`.
2. **ESO:** reads Vault via `ClusterSecretStore/vault-backend` every 5m → `openmontage-secrets`.
3. **Pod start:** envFrom ConfigMap + Secret; app may re-fetch Vault with `VAULT_TOKEN` for keys not mirrored into the K8s Secret.
4. **Tool call:** reads env (e.g. `OPENAI_API_KEY`) — unchanged tool contracts.

## Vault Path Design

| Path | Contents |
|------|----------|
| `secret/t6-apps/openmontage/config` | App keys + `vault_token` (lowercase_snake_case) |
| `secret/shared/api-keys` | Org-wide API keys (read-only for app token) |
| `secret/shared/dockerhub` | Hub username / PAT / email for pull secret |

**Note:** Cluster standard is `t6-apps`, not `t5-apps`. There is a `t5-gateway/` tree for gateway secrets; application configs live under `t6-apps/`.

### Shared → OpenMontage env mapping

| Vault key (`shared/api-keys`) | Env vars |
|-------------------------------|----------|
| `openai_api_key` | `OPENAI_API_KEY` |
| `elevenlabs_api_key` | `ELEVENLABS_API_KEY` |
| `gemini_api_key` | `GEMINI_API_KEY`, `GOOGLE_API_KEY` |
| `hf_token` | `HF_TOKEN` |
| `anthropic_api_key` | `ANTHROPIC_API_KEY` |
| `openrouter_api_key` | `OPENROUTER_API_KEY` |

## Security Considerations
- Runtime token is least-privilege (`app-openmontage`): CRUD on own path, read on `shared/*`, renew-self.
- Admin/root token used only for seed/mint from operator workstation / deploy script.
- Secrets never written into git; `.env` is gitignored.
- Public Vault URL requires Cloudflare Access; pods use in-cluster DNS.

## Performance Considerations
- One (or two) Vault GETs at process start.
- ESO offloads sync of the K8s Secret so cold pods still get keys if Vault is briefly unreachable after sync.
- PVC for projects avoids losing board state across restarts.

## Technology Stack
- Python 3.11 (container), FastAPI/uvicorn (Backlot)
- HashiCorp Vault KV v2
- External Secrets Operator
- Docker Hub (`docker4zerocool`)
- Kubernetes (local cluster)
