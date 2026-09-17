"""Real Microsoft Entra ID (Azure AD) single sign-on for Banking Circle staff
(docs/SSO_SETUP.md).

Standard OAuth2 authorization-code flow via MSAL:
  1. Frontend calls GET /login-url, gets the Microsoft authorize URL, and
     redirects the whole browser tab there.
  2. The user signs in with their @bankingcircle.com account on
     login.microsoftonline.com.
  3. Microsoft redirects back to GET /callback with an auth code.
  4. We exchange the code for an ID token, verify the email domain, find or
     auto-provision the matching FlowMatch user, and issue our own existing
     dev-mode bearer token (app.auth.issue_token) - so every other router in
     this app keeps working completely unchanged.

Fully optional / feature-flagged: when AZURE_CLIENT_ID/SECRET/TENANT_ID are
not set (i.e. IT hasn't finished the Azure AD App Registration yet), every
route here responds 503 and the frontend falls back to the existing
dev-mode demo picker (auth_router.py). Nothing else needs to change once
those three environment variables are set - see docs/SSO_SETUP.md.
"""

import urllib.parse

from flask import Blueprint, jsonify, redirect, request

from app.auth import issue_token
from app.config import (
    AZURE_CLIENT_ID,
    AZURE_CLIENT_SECRET,
    AZURE_REDIRECT_URI,
    AZURE_TENANT_ID,
    FLOWMATCH_FRONTEND_URL,
    SSO_ALLOWED_EMAIL_DOMAIN,
)
from app.database import db_session
from app.errors import ApiError
from app.services.audit_service import audit_event

try:
    import msal
except ImportError:  # pragma: no cover - msal is in requirements.txt
    msal = None

bp = Blueprint("sso", __name__, url_prefix="/api/auth/sso")

SCOPES = ["User.Read"]


def sso_enabled():
    return bool(msal and AZURE_CLIENT_ID and AZURE_CLIENT_SECRET and AZURE_TENANT_ID)


def _msal_app():
    return msal.ConfidentialClientApplication(
        AZURE_CLIENT_ID,
        authority="https://login.microsoftonline.com/{}".format(AZURE_TENANT_ID),
        client_credential=AZURE_CLIENT_SECRET,
    )


def _redirect_with_error(message):
    return redirect("{}/?sso_error={}".format(FLOWMATCH_FRONTEND_URL, urllib.parse.quote(message)))


@bp.get("/config")
def sso_config():
    """Frontend calls this on the login screen to decide whether to show the
    'Sign in with Microsoft' button at all."""
    return jsonify({"enabled": sso_enabled(), "allowed_domain": SSO_ALLOWED_EMAIL_DOMAIN})


@bp.get("/login-url")
def login_url():
    if not sso_enabled():
        raise ApiError("Microsoft SSO is not configured on this server yet.", 503)
    app_ = _msal_app()
    url = app_.get_authorization_request_url(
        SCOPES, redirect_uri=AZURE_REDIRECT_URI, prompt="select_account",
    )
    return jsonify({"url": url})


@bp.get("/callback")
def callback():
    """Azure AD redirects here after the user signs in. This endpoint is
    hit by the browser directly (not fetch), so we respond with a redirect
    back to the frontend rather than JSON."""
    if not sso_enabled():
        raise ApiError("Microsoft SSO is not configured on this server yet.", 503)

    if request.args.get("error"):
        return _redirect_with_error(request.args.get("error_description", request.args["error"]))

    code = request.args.get("code")
    if not code:
        return _redirect_with_error("Microsoft sign-in did not return an authorization code.")

    app_ = _msal_app()
    result = app_.acquire_token_by_authorization_code(
        code, scopes=SCOPES, redirect_uri=AZURE_REDIRECT_URI,
    )
    if "error" in result:
        return _redirect_with_error(result.get("error_description", result["error"]))

    claims = result.get("id_token_claims", {}) or {}
    email = (claims.get("preferred_username") or claims.get("email") or claims.get("upn") or "").lower()
    name = claims.get("name") or email

    if not email:
        return _redirect_with_error("Microsoft did not return an email address for this account.")
    if SSO_ALLOWED_EMAIL_DOMAIN and not email.endswith("@" + SSO_ALLOWED_EMAIL_DOMAIN.lower()):
        return _redirect_with_error(
            "Only @{} accounts may sign in to FlowMatch.".format(SSO_ALLOWED_EMAIL_DOMAIN)
        )

    with db_session() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user:
            # First-ever real SSO login for this person - auto-provision a
            # minimal profile rather than blocking them. They land as a
            # plain Contributor with no department; they (or an admin) can
            # fill in the rest from the Profile/Org screens afterwards.
            user_id = conn.execute(
                """INSERT INTO users
                   (name, email, role_title, avatar_emoji, completed_trainings,
                    granted_access, profile_last_reviewed)
                   VALUES (?, ?, ?, ?, '[]', '[]', NULL)""",
                (name, email, "Employee", "🙂"),
            ).lastrowid
            conn.execute("INSERT INTO user_roles (user_id, role) VALUES (?, 'contributor')", (user_id,))
            conn.execute(
                """INSERT INTO user_preferences (user_id, opportunity_types, declared_availability,
                       ai_support_band, visibility, opted_into_discovery)
                   VALUES (?, '[]', 'Unspecified', 'Explorer', 'visible_to_org', 1)""",
                (user_id,),
            )
            audit_event(conn, None, "auth.sso_user_provisioned", "user", user_id)
            user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

        roles = [
            r["role"] for r in conn.execute(
                "SELECT role FROM user_roles WHERE user_id = ?", (user["id"],)
            ).fetchall()
        ]
        active_role = roles[0] if roles else "contributor"
        token = issue_token(user["id"], active_role)
        audit_event(conn, {"id": user["id"], "active_role": active_role}, "auth.sso_login", "user", user["id"])

    return redirect("{}/?sso_token={}".format(FLOWMATCH_FRONTEND_URL, urllib.parse.quote(token)))
