# Implementation Plan: Vault Config + Kubernetes Deploy

## Overview

Revise OpenMontage so API keys are loaded from HashiCorp Vault (cluster path `secret/data/t6-apps/openmontage/config`, with known keys also merged from `secret/data/shared/api-keys`), then package the Backlot board + tool runtime as a Docker image, push to Docker Hub, and deploy to the local Kubernetes cluster using External Secrets Operator (ESO).

## Requirements

### Functional Requirements
- Load secrets from Vault at process start (tools + Backlot).
- Follow the cluster app path convention: `secret/data/t6-apps/<app-slug>/config`.
- Prefer non-empty existing environment variables over Vault values (K8s / shell / `.env` win).
- Seed OpenMontage-relevant keys from `shared/api-keys` into the app Vault path.
- Mint a least-privilege periodic `vault_token` under policy `app-openmontage`.
- Sync Vault → Kubernetes Secret via ESO; ConfigMap holds non-secret Vault host/slug settings.
- Build and publish `docker4zerocool/openmontage` and run it in namespace `openmontage`.

### Non-Functional Requirements
- **Security:** Never log or print secret values; only key names and presence.
- **Reliability:** Soft-fail Vault load when host/token missing (local `.env`-only still works).
- **Performance:** Single HTTP GET (plus optional shared merge) at startup; no per-tool Vault round-trips.
- **Operability:** Idempotent `k8s/deploy.sh` for seed + apply.

## Implementation Phases

### Phase 1 — Vault loader (complete)
**Deliverables**
- `lib/vault_config.py` with `load_vault_config()` / `ensure_vault_config_loaded()`
- Wire into `tools/base_tool.py`, `lib/env_loader.py`, `backlot/__main__.py`
- `.env.example` Vault knobs
- Unit tests with mocked HTTP

**Test gates**
- Unit: `pytest tests/lib/test_vault_config.py` — apply, skip, existing-env-wins, shared aliases, HTTP error soft-fail

### Phase 2 — Seed Vault + mint token (complete)
**Deliverables**
- `k8s/deploy.sh --seed-only` copies mapped keys from `shared/api-keys` → `t6-apps/openmontage/config`
- Policy `app-openmontage` + orphan periodic `vault_token` patched into app config

**Test gates**
- Vault key names present on app path (no value dump)
- App token can read app path + shared paths

### Phase 3 — Container + Hub (complete)
**Deliverables**
- `Dockerfile`, `.dockerignore`
- Image `docker.io/docker4zerocool/openmontage:latest` (+ date tag)

**Test gates**
- Image builds; Hub push succeeds; container healthcheck hits `/api/health`

### Phase 4 — Kubernetes deploy (complete)
**Deliverables**
- Manifests under Deploy repo: `k8s-infrastructure/deploy/tier6-apps/manifests/openmontage/`
- Orchestrator: `k8s-infrastructure/deploy/tier6-apps/deploy-openmontage.sh`
- ESO: `k8s-infrastructure/deploy/vault/apps/openmontage/external-secret.yaml`
- App repo `k8s/README.md` points at the Deploy location (no separate checkout required to deploy)

**Test gates**
- ExternalSecret `Ready` / `SecretSynced`
- Deployment rolled out; `GET /api/health` → `{"ok":true,"app":"backlot"}`
- In-pod Vault reload applies expected env key names

### Phase 5 — Remaining keys + hardening (pending)
**Deliverables**
- Add missing provider keys to Vault when available (FAL, Kling, HeyGen, Pexels, Pixabay, Unsplash, Azure Speech, DashScope, Suno, XAI, Doubao, Runway, Replicate, Higgsfield)
- Optional Ingress
- Live Vault integration test in CI or cluster job

**Test gates**
- Integration: pod with only `VAULT_HOST` + `VAULT_TOKEN` can enable at least OpenAI / ElevenLabs / Gemini tools
- Unit suite still green; no secrets in git

## Dependencies
- Cluster Vault (`vault` namespace), ESO `ClusterSecretStore/vault-backend`
- Docker Hub credentials in `secret/shared/dockerhub`
- Admin/root Vault token for seeding (runtime uses minted app token)

## Testing Strategy

### Unit tests
- Mock Vault HTTP responses in `tests/lib/test_vault_config.py`
- Cover skip flag, alias mapping (`gemini_api_key` → `GEMINI_API_KEY` + `GOOGLE_API_KEY`), and soft failure on 403

### Integration tests
- Prefer live in-cluster Vault (`http://vault.vault.svc.cluster.local:8200`)
- Assert env key presence (not values) after `load_vault_config()`
- Optional: `kubectl exec` smoke against deployed pod

### End-to-end
- Deploy via `./k8s/deploy.sh`
- Hit Service ClusterIP or port-forward Backlot UI/health

## Rollout Plan
1. Seed Vault + mint token
2. Push image
3. Apply manifests; wait for ESO + rollout
4. Verify health + Vault load
5. (Later) Ingress if external access needed

### Rollback
- `kubectl delete -f k8s/` (or scale deployment to 0)
- Vault path can remain; rotate `vault_token` via `deploy.sh --seed-only` if compromised

### Monitoring
- Pod readiness/liveness on `/api/health`
- ESO status on `externalsecret/openmontage-secrets`
