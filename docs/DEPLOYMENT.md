# Deploying FlowMatch to Kubernetes

FlowMatch is deployed via the Atlas platform's **Kubernetes Foundation +
DevOps Helm Blueprint** chart
(https://atlas.bankingcircle.com/docs/helm-blueprint-configuration).

> Note: an earlier version of this doc described a "shuttle"-based
> deployment (SSH key + `shuttle.yaml` + `environments/dev.yaml`). Atlas
> Support confirmed shuttle has been deprecated platform-wide for ~2 years;
> the pipelines and config here have been migrated to the Helm Blueprint
> approach below. No SSH key is required.

## Status

- ✅ Kubernetes Foundation merged: `devops.platform.configuration` PR #134634
  (namespace group `flowmatch-ns-dev-*`, resource group `flowmatch-aks-dev-rg`,
  Key Vault `flowmatc-aks-kv-sps-dev`, repo `flowmatch.gitops`).
- ✅ App containerized (`backend/Dockerfile`, `frontend/Dockerfile`).
- ✅ Exported to Azure DevOps: `Commercial Digitalization` PR #134637 (merged).
- ✅ CI/CD pipelines registered in Azure DevOps as `flowmatch-backend` and
  `flowmatch-frontend`, pointing at `aind/FlowMatch/{backend,frontend}/pipelines/pipeline.yml`.
- ✅ Pipelines rewritten to use the `helm.yml` template (Helm Blueprint)
  instead of the deprecated `deploy.yml` (shuttle).
- ✅ Per-app Helm values added at
  `backend/values/dev/neu-aks-shared-dev/values.yaml` and
  `frontend/values/dev/neu-aks-shared-dev/values.yaml`.
- ⏳ First run of the new pipelines against the Helm Blueprint - pending
  verification (region/cluster segment `neu-aks-shared-dev` assumed from the
  platform's reference example; confirm against your Foundation if the
  deploy stage reports a missing values path).

## How it works

Each app's pipeline (`pipeline.yml`) has 4 stages:

1. **build** - builds and saves the Docker image as a pipeline artifact.
2. **scan** - security scan of the image (`scan.yml@templates`).
3. **push** - pushes the image to the shared platform ACR
   (`devopsplatformregistry<env>`) (`push.yml@templates`).
4. **deploy_dev** - renders the Helm Blueprint chart using
   `values/dev/neu-aks-shared-dev/values.yaml` and commits the resulting
   manifests to `flowmatch.gitops`, where ArgoCD picks them up
   (`helm.yml@templates`). No SSH key or manual git clone is involved - the
   template handles the `config-repo` checkout using the pipeline's own
   permissions.

## Remaining one-time setup

1. ✅ ACR confirmed: shared platform registry `devopsplatformregistry<env>`.
2. ✅ Both pipelines registered in Azure DevOps.
3. ⏳ Confirm the `flowmatch-aks-dev-vars` variable group (with
   `flowmatch-client-id`/`flowmatch-client-secret`) exists in
   `Commercial Digitalization` → Pipelines → Library.
4. Run each pipeline (or let the `main` branch trigger fire) to build, scan,
   push, and deploy to `dev`.
5. (Optional / access) Request Saviynt access to `flowmatch-aks-dev-rg`
   (`_READER`/`_OWNER`) for Azure Portal visibility into the resource group.

## After deployment

- Frontend: `https://flowmatch-dev.kubernetes.bankingcircle.net`
- Backend health check: `https://flowmatch-backend-dev.kubernetes.bankingcircle.net/api/health`
- Verify via ArgoCD (`https://argocd-neu-dev.kubernetes.bankingcircle.net/`)
  that the `flowmatch` apps are synced and healthy.

## SSO

Real Microsoft Entra ID SSO stays disabled until IT provides
`AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET` / `AZURE_TENANT_ID`. Under the
Helm Blueprint these would be added via `envFromKeyvault` in
`backend/values/dev/neu-aks-shared-dev/values.yaml`, referencing the
`flowmatc-aks-kv-sps-dev` Key Vault - see `docs/SSO_SETUP.md`. Until then,
the dev-mode demo login keeps working unchanged.
