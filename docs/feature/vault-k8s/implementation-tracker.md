# Feature: Vault Config + Kubernetes Deploy

## Status: In Progress
## Priority: High

### Progress Checklist
- [x] Requirements gathering
- [x] Technical design
- [x] API / interface design (Vault loader contract)
- [x] Implementation — Vault runtime loader (`lib/vault_config.py`)
- [x] Implementation — wire loader into tool/backlot startup
- [x] Implementation — seed `secret/t6-apps/openmontage/config`
- [x] Implementation — mint `app-openmontage` Vault policy + `vault_token`
- [x] Implementation — Dockerfile + Docker Hub push
- [x] Implementation — k8s manifests (namespace, ESO, ConfigMap, PVC, Deployment, Service)
- [x] Relocate deploy unit to Deploy repo (`k8s-infrastructure/deploy/tier6-apps/…`)
- [x] Deploy to local cluster (`openmontage` namespace)
- [x] Unit tests (`tests/lib/test_vault_config.py`)
- [ ] Integration tests against live Vault (in-cluster)
- [x] Documentation (implementation-plan, tracker, architecture, API, usage)
- [ ] Ingress / public URL (optional)
- [ ] Seed remaining provider keys not in `shared/api-keys` (FAL, Kling, HeyGen, Pexels, …)
- [ ] Commit + PR (awaiting user approval)

### Timeline
- Start Date: 2026-07-19
- Target Completion: 2026-07-20
- Actual Completion:

### Blockers/Issues
- Public `https://vault.baisoln.com` is behind Cloudflare Access; local/dev reads must use in-cluster Vault (`http://vault.vault.svc.cluster.local:8200`) or `kubectl port-forward`.
- Cluster convention is `t6-apps/<slug>/config` (not `t5-apps`). Documented accordingly.
- Many OpenMontage provider keys from `.env.example` are not yet present under `secret/shared/api-keys`; only the overlapping shared keys were seeded.
