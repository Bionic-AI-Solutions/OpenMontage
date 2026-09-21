# OpenMontage Kubernetes deploy — moved

**Canonical deploy lives in the Deploy / cluster repo:**

```text
k8s-infrastructure/deploy/tier6-apps/
  deploy-openmontage.sh
  manifests/openmontage/          # namespace, ESO, ConfigMap, PVC, Deployment, Ingress
deploy/vault/apps/openmontage/    # ExternalSecret (ESO ← Vault)
```

Deploy without this OpenMontage checkout:

```bash
cd /path/to/Deploy/k8s-infrastructure/deploy
export VAULT_TOKEN=<admin-token>   # or VAULT_ROOT_TOKEN in env/.env
./tier6-apps/deploy-openmontage.sh
```

- Image: `docker.io/docker4zerocool/openmontage:latest`
- Vault: `secret/t6-apps/openmontage/config`
- Docs: `docs/feature/vault-k8s/` (app-side feature pack)

The YAML/scripts previously in this folder were relocated so cluster setup is self-contained.
Use `SKIP_INGRESS=true` for ClusterIP-only deploys.
