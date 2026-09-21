# Usage Guide: Vault Config + Kubernetes Deploy

## Prerequisites
- `kubectl` context pointing at the local cluster
- Access to Vault admin token (for seed/mint only)
- Docker logged in as `docker4zerocool` (for image push)
- ESO `ClusterSecretStore/vault-backend` already installed

## Getting Started

### 1. Configure local `.env` (Vault access only)

```bash
cp .env.example .env
# Set:
#   VAULT_HOST=https://vault.baisoln.com   # or in-cluster / port-forward URL
#   VAULT_TOKEN=<admin-or-app-token>
#   VAULT_APP_SLUG=openmontage
#   VAULT_LOAD_SHARED=true
```

Public Vault is behind Cloudflare Access. For local verification prefer:

```bash
kubectl -n vault port-forward svc/vault 8200:8200
# then VAULT_HOST=http://127.0.0.1:8200
```

### 2. Seed Vault + deploy (from the Deploy / cluster repo)

Canonical manifests and deploy script live in **Deploy** (`k8s-infrastructure`), not this application repo:

```bash
cd k8s-infrastructure/deploy
export VAULT_TOKEN=<admin-token>   # or VAULT_ROOT_TOKEN in env/.env
./tier6-apps/deploy-openmontage.sh

# ClusterIP only (skip Kong / DNS):
SKIP_INGRESS=true ./tier6-apps/deploy-openmontage.sh
```

See `k8s-infrastructure/deploy/tier6-apps/manifests/openmontage/README.md`.

### 3. Verify

```bash
kubectl get pods,externalsecret,svc -n openmontage
kubectl -n openmontage port-forward svc/openmontage 4750:80
curl -s http://127.0.0.1:4750/api/health
# → {"ok":true,"app":"backlot"}
```

Confirm keys loaded (names/presence only):

```bash
POD=$(kubectl get pod -n openmontage -l app=openmontage -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n openmontage "$POD" -- python -c "
from lib.vault_config import load_vault_config
import os
r = load_vault_config()
print(r.path, sorted(r.keys_applied))
print('OPENAI set:', bool(os.environ.get('OPENAI_API_KEY')))
"
```

### 4. Rebuild / republish image

```bash
docker build -t docker4zerocool/openmontage:latest .
docker push docker4zerocool/openmontage:latest
kubectl -n openmontage rollout restart deployment/openmontage
```

## Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `VAULT_HOST` | Vault base URL (primary) | `http://vault.vault.svc.cluster.local:8200` |
| `VAULT_ADDR` | Alias for `VAULT_HOST` | same |
| `VAULT_TOKEN` | Token for Vault API | (from ESO / `.env`) |
| `VAULT_APP_SLUG` | App path slug | `openmontage` |
| `VAULT_SKIP_LOAD` | Disable Vault overlay | `true` for unit tests |
| `VAULT_LOAD_SHARED` | Merge `shared/api-keys` | `true` |
| `BACKLOT_HOST` | Bind address | `0.0.0.0` in k8s |
| `BACKLOT_PORT` | Listen port | `4750` |

### Configuration Files
- `k8s/02-configmap.yaml` — non-secret runtime knobs
- `k8s/01-externalsecret.yaml` — which Vault properties sync into the pod Secret
- `.env` / `.env.example` — local developer Vault access

### Vault paths
- App: `secret/t6-apps/openmontage/config`
- Shared keys: `secret/shared/api-keys`
- Docker Hub: `secret/shared/dockerhub`

## Common Use Cases

### Use Case 1 — Local agent with Vault keys
1. Port-forward Vault or use a token that can reach the API.
2. Set `VAULT_HOST` + `VAULT_TOKEN` in `.env`.
3. Import any tool (or call `load_env()`); keys appear in `os.environ`.

### Use Case 2 — Cluster-only Backlot board
1. `./k8s/deploy.sh`
2. Port-forward the Service and open `http://127.0.0.1:4750/`.

### Use Case 3 — Add a new provider key
1. Put the value in Vault (prefer app path or `shared/api-keys` if org-wide).
2. If using a new shared key name, add it to `SHARED_KEY_ALIASES` in `lib/vault_config.py` and to the ExternalSecret template.
3. Re-run `./k8s/deploy.sh --seed-only` (if copying into app path) and force ESO sync:

```bash
kubectl -n openmontage annotate externalsecret openmontage-secrets \
  force-sync=$(date +%s) --overwrite
kubectl -n openmontage rollout restart deployment/openmontage
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Vault GET 302/403 via public URL | Cloudflare Access | Use in-cluster URL or port-forward |
| `loaded: False`, empty path | Missing `VAULT_HOST` / `VAULT_TOKEN` | Check ConfigMap + Secret |
| ExternalSecret not Ready | Vault path/property missing | Re-seed; check `kubectl describe externalsecret -n openmontage` |
| ImagePullBackOff | Hub pull secret | Ensure `dockerhub-pull-secret` synced |
| Tools still unavailable | Key not in Vault | Seed missing provider key; restart pod |

## FAQ

**Why `t6-apps` instead of `t5-apps`?**  
This cluster stores application configs under `secret/t6-apps/<slug>/config`. `t5-gateway/` is a different tree. OpenMontage follows the same convention as socialx and other apps.

**Do tools call Vault on every request?**  
No. Secrets are loaded once at process start into `os.environ`.

**Can I keep using a local `.env` with API keys?**  
Yes. Non-empty env values always win over Vault.

## Support
- Feature docs: `docs/feature/vault-k8s/`
- Deploy script: `k8s-infrastructure/deploy/tier6-apps/deploy-openmontage.sh`
- Manifests: `k8s-infrastructure/deploy/tier6-apps/manifests/openmontage/`
- Loader source (app repo): `lib/vault_config.py`
