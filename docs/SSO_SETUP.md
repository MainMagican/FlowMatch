# Setting up Microsoft Entra ID (Azure AD) SSO for FlowMatch

FlowMatch already has the full SSO code built and ready
(`backend/app/routers/sso_router.py` + a "Sign in with Microsoft" button on
the login screen). It's currently **disabled** because it needs three
values that only an Azure AD admin (Application Administrator / Global
Admin) can create. Once IT provides these, SSO turns on automatically with
no further code changes required.

## What IT needs to do

### Option A — Azure CLI (fastest, run by someone with app-registration rights)

```powershell
# 1. Create the App Registration (single-tenant, so only bankingcircle.com accounts can sign in)
az ad app create `
  --display-name "FlowMatch" `
  --sign-in-audience "AzureADMyOrg" `
  --web-redirect-uris "http://127.0.0.1:8100/api/auth/sso/callback"

# Note the "appId" from the output above -> this is AZURE_CLIENT_ID

# 2. Create a client secret for it (needed so the backend can exchange the auth code)
az ad app credential reset --id <APP_ID_FROM_STEP_1> --append --years 2
# Note the "password" from the output -> this is AZURE_CLIENT_SECRET (shown only once - save it securely)

# 3. Grant the Microsoft Graph "User.Read" delegated permission (usually already default) and admin-consent it
az ad app permission admin-consent --id <APP_ID_FROM_STEP_1>
```

Also note your **Tenant ID** (Banking Circle's is `1eef4a4d-f7cc-4e1e-9345-5db4051d2bc1` /
`saxopayments.com`, confirmed via `az account show`).

### Option B — Azure Portal (click-through)

1. **Entra ID** → **App registrations** → **New registration**
   - Name: `FlowMatch`
   - Supported account types: *Accounts in this organizational directory only (Banking Circle only - Single tenant)*
   - Redirect URI: **Web** → `http://127.0.0.1:8100/api/auth/sso/callback`
2. Copy the **Application (client) ID** and **Directory (tenant) ID** from the Overview page.
3. **Certificates & secrets** → **New client secret** → copy the secret **value** immediately (it's hidden afterwards).
4. **API permissions** → confirm `Microsoft Graph > User.Read` (delegated) is present → **Grant admin consent**.

> When FlowMatch moves off `127.0.0.1` to a real internal hostname, add that
> URL's `/api/auth/sso/callback` as an additional Redirect URI on the same
> App Registration.

## What to hand back

- **Client ID** (Application ID)
- **Client Secret** (the value, not the secret ID)
- **Tenant ID**

## How to plug them in

Set these environment variables before starting the backend
(`backend/app/main.py` / `python -m app.main`):

```powershell
$env:AZURE_CLIENT_ID = "<client id>"
$env:AZURE_CLIENT_SECRET = "<client secret>"
$env:AZURE_TENANT_ID = "<tenant id>"
# Optional overrides (defaults shown):
$env:AZURE_REDIRECT_URI = "http://127.0.0.1:8100/api/auth/sso/callback"
$env:FLOWMATCH_FRONTEND_URL = "http://127.0.0.1:5600"
$env:SSO_ALLOWED_EMAIL_DOMAIN = "bankingcircle.com"

cd backend
pip install -r requirements.txt   # installs msal
python -m app.main
```

Then reload the frontend — the login screen will automatically show a
**"Sign in with Microsoft"** button once `GET /api/auth/sso/config` reports
`enabled: true`.

## How it behaves

- Only `@bankingcircle.com` accounts (configurable via
  `SSO_ALLOWED_EMAIL_DOMAIN`) can sign in - anyone else is rejected with a
  clear error on the login screen.
- The first time someone signs in with Microsoft, FlowMatch auto-creates a
  minimal profile for them (name + email from Azure AD, role = Contributor,
  no department yet) - they can fill in the rest afterwards from the
  Profile/Org screens, or an Administrator can assign them a department/pod.
- If a matching seeded/synthetic demo user already has that exact email, SSO
  signs into that existing account instead of creating a duplicate.
- The dev-mode demo picker (pick any of the 239 seeded personas) keeps
  working side-by-side underneath the Microsoft button, so local development
  and demos aren't disrupted.
