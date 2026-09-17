# Deploying FlowMatch to Kubernetes

FlowMatch is deployed via the Atlas platform's Kubernetes Foundation + Helm
Blueprint ("3 YAML approach": https://atlas.bankingcircle.com/kubernetes-foundation).

## Status

- ✅ Kubernetes Foundation merged: `devops.platform.configuration` PR #134634
  (namespace `flowmatch`, 20 CPU / 20Gi quota, owner `aind`).
- ✅ App containerized (`backend/Dockerfile`, `frontend/Dockerfile`) and
  deployment config added (`shuttle.yaml` + `environments/dev.yaml` per app).
- ✅ Exported to Azure DevOps: `Commercial Digitalization` PR #134637.
- ⏳ CI/CD pipelines drafted (`backend/pipelines/pipeline.yml`,
  `frontend/pipelines/pipeline.yml`) - **not yet registered in Azure DevOps**.

## Remaining one-time setup (manual, in Azure DevOps)

1. ✅ **SSH key for shuttle**: RSA 4096 key pair generated. Public key added
   to Azure DevOps user SSH keys. Private key uploaded as a **Secure File**
   named `id_shuttle_ado` in the `Commercial Digitalization` project's
   Pipeline Library.
2. ✅ **ACR (container registry) name confirmed** by Atlas Support: it's the
   shared platform registry `devopsplatformregistry<env>` (e.g.
   `devopsplatformregistrydev`), not a per-app registry. Both pipelines
   updated accordingly.
3. ⏳ **Register both pipelines** in Azure DevOps (Pipelines → New pipeline →
   point at `aind/FlowMatch/backend/pipelines/pipeline.yml` and
   `aind/FlowMatch/frontend/pipelines/pipeline.yml` in this repo).
4. ⏳ Once merged and the Foundation exists, the `flowmatch-aks-dev-vars`
   variable group (with `flowmatch-client-id`/`flowmatch-client-secret`) and
   the `flowmatch.gitops` repo should already exist automatically. The
   `flowmatch.gitops` repo is confirmed to exist; please verify the variable
   group manually in `Commercial Digitalization` → Pipelines → Library (my
   API session's PAT lacks scope/has expired for that check).
5. Run each pipeline once (or let the `main` branch trigger fire) to build,
   scan, push, and deploy to `dev`.

## After deployment

- Frontend: `https://flowmatch-dev.kubernetes.bankingcircle.net`
- Backend health check: `https://flowmatch-backend-dev.kubernetes.bankingcircle.net/api/health`
- Verify with: `kubectl get ns flowmatch-dev` and check the ArgoCD project
  for `flowmatch`.

## SSO

Real Microsoft Entra ID SSO stays disabled until IT provides
`AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET` / `AZURE_TENANT_ID` as Key
Vault-backed secrets in `backend/environments/dev.yaml` - see
`docs/SSO_SETUP.md`. Until then, the dev-mode demo login keeps working
unchanged.
