# Backlot Interactive Board — Kubernetes Deploy (om.baisoln.com)

**Date:** 2026-07-20 · **Status:** Approved by user · **Depends on:** PR #1 (interactive board), feature/vault-k8s (image + cluster wiring)

## Situation

`om.baisoln.com` already serves Backlot from the `openmontage` namespace (Kong ingress → svc `openmontage:80` → Backlot :4750; image `docker4zerocool/openmontage:20260719-full`; NFS PVC `openmontage-projects` shared with the `openmontage-workspace` exec pod). The ingress has **no auth**, and the interactive code's CSRF check is localhost-only — deployed as-is, every board write would 403.

## Decisions

| Question | Decision |
|---|---|
| Auth | **Kong basic-auth** — creds in Vault (`secret/t6-apps/openmontage/config`: `backlot_basic_auth_user`/`backlot_basic_auth_password`) → ESO ExternalSecret → `kongCredType: basic-auth` secret → KongConsumer → `basic-auth` KongPlugin on the ingress. No app-code auth. |
| CSRF origins | New env `BACKLOT_ALLOWED_ORIGINS` (comma-separated origins) merged into the localhost allowlist on `/inbox` + `/upload`. Default (unset) = localhost-only, local behavior unchanged. Set to `https://om.baisoln.com` in the Deployment. |
| Source tree for image | Merge `feature/backlot-interactive-board` into `feature/vault-k8s` in the main checkout (branches touch disjoint files; the vault-k8s Dockerfile/bootstrap are uncommitted there and required for the build). |
| Image | Build `docker4zerocool/openmontage:20260720-full` + `latest` from the merged tree; push to Docker Hub; `kubectl set image` + rollout both deployments. |
| Manifests home | `/workspace/k8s-infrastructure/deploy/tier6-apps/manifests/openmontage/` (canonical per OpenMontage `k8s/README.md`), Vault ES in `deploy/vault/apps/openmontage/`. |

## Verification (external-first)

1. `https://om.baisoln.com/api/health` — 401 without creds, 200 with.
2. `POST /api/project/<id>/inbox` with creds + `Origin: https://om.baisoln.com` → 200; `Origin: https://evil.example` → 403; no creds → 401.
3. In-cluster: exec into `openmontage-workspace`, run `scripts/backlot_simulate_run.py --interactive` on the shared PVC; approve gates from the browser at om.baisoln.com — full remote loop.

## Out of scope

SSO/auth-proxy, multi-user auth, per-stage authorization, image slimming.
