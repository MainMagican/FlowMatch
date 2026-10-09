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
- ✅ Exported to Azure DevOps: `CommercialDigitalization` PR #134637 (merged). (Project
  was later renamed from `Commercial Digitalization` to `CommercialDigitalization`
  - no space - to work around a Helm Blueprint template bug that mishandles
  repo names containing spaces.)
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
   `CommercialDigitalization` → Pipelines → Library.
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

The dev backend values in `backend/values/dev/neu-aks-shared-dev/values.yaml`
configure the FlowMatch SSO app's client ID and tenant ID in `envVariables`.
`envFromKeyvault` maps `FLOWMATCH_SSO_CLIENT_SECRET` to the secret
`FlowMatchSSO-01102026` in Key Vault `flowmatc-aks-kv-sps-dev`. The existing
`flowmatch-client-id` and `flowmatch-client-secret` are deployment pipeline
credentials, not the SSO app credentials; leave them unchanged.

Before deploying, confirm the Key Vault secret is enabled and its expiration
matches the Entra client secret's actual expiry. IT must register the Web
redirect URI
`https://flowmatch-backend-dev.kubernetes.bankingcircle.net/api/auth/sso/callback`.
The backend's deployment identity must have permission to retrieve the secret.

These settings only take effect after they are published to the Azure DevOps
source repository and the backend pipeline deploys them. In Azure DevOps,
select `Commercial Digitalization` (definition 3515), using `main` and
`aind/FlowMatch/backend/pipelines/pipeline.yml`.
Then verify `GET /api/auth/sso/config` returns `enabled: true` and test an
actual Microsoft sign-in. The config flag checks credential presence, not
credential validity. The dev-mode demo login remains available; this mapping
does not make the application SSO-only. See `docs/SSO_SETUP.md` for the sign-in
flow and IT prerequisites.
