"""Application configuration for the FlowMatch backend.

Kept intentionally small: everything is read from environment variables with
safe defaults so the app runs out of the box in a local/demo environment with
no external credentials (per docs/DECISIONS.md #2, #3, #4).
"""

import os

# Secret used to sign dev-mode bearer tokens. In a real deployment this would
# be replaced by a real identity provider (Entra ID) - see app/auth.py.
TOKEN_SIGNING_SECRET = os.environ.get("FLOWMATCH_TOKEN_SECRET", "dev-only-not-for-production-flowmatch")

TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days

DB_PATH = os.environ.get(
    "FLOWMATCH_DB_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "flowmatch.db"),
)

# --- Microsoft Entra ID (Azure AD) SSO config (docs/SSO_SETUP.md) ---
# All optional: when unset, SSO is simply disabled and dev-mode demo login
# (auth_router.py) keeps working exactly as before. IT sets these once the
# Azure AD App Registration for FlowMatch exists in the bankingcircle.com
# tenant.
AZURE_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID")
AZURE_CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET")
AZURE_TENANT_ID = os.environ.get("AZURE_TENANT_ID")
AZURE_REDIRECT_URI = os.environ.get("AZURE_REDIRECT_URI", "http://127.0.0.1:8100/api/auth/sso/callback")
FLOWMATCH_FRONTEND_URL = os.environ.get("FLOWMATCH_FRONTEND_URL", "http://127.0.0.1:5600")
SSO_ALLOWED_EMAIL_DOMAIN = os.environ.get("SSO_ALLOWED_EMAIL_DOMAIN", "bankingcircle.com")
