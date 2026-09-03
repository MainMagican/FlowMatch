"""Dev-mode identity for FlowMatch (docs/DECISIONS.md #3).

There is no real enterprise identity provider available in this sandbox, so
users "log in" by picking one of the seeded demo personas and one of the
roles assigned to that persona. A signed bearer token records which user+role
is acting, so every subsequent request is authorized server-side (never only
hidden in the UI - design.md FR2-3).

To swap in real SSO later: replace `login()` with a real OIDC/Entra ID token
exchange, keep `verify_token` / `get_current_user` / `require_role` as-is.
"""

import hashlib
import hmac
import time

from flask import request

from app.config import TOKEN_SIGNING_SECRET, TOKEN_TTL_SECONDS
from app.database import db_session
from app.errors import ApiError

ALL_ROLES = [
    "contributor",
    "team_lead",
    "workflow_owner",
    "reviewer",
    "mentor",
    "administrator",
]


def _sign(payload):
    return hmac.new(TOKEN_SIGNING_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()


def issue_token(user_id, role):
    expiry = int(time.time()) + TOKEN_TTL_SECONDS
    payload = "{}:{}:{}".format(user_id, role, expiry)
    signature = _sign(payload)
    return "{}:{}".format(payload, signature)


def verify_token(token):
    try:
        user_id_str, role, expiry_str, signature = token.split(":")
    except ValueError:
        raise ApiError("Invalid token", 401)
    payload = "{}:{}:{}".format(user_id_str, role, expiry_str)
    expected = _sign(payload)
    if not hmac.compare_digest(expected, signature):
        raise ApiError("Invalid token", 401)
    if int(expiry_str) < int(time.time()):
        raise ApiError("Token expired", 401)
    return int(user_id_str), role


def get_current_user():
    """Return (user_row, active_role) for the current request, or raise ApiError."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise ApiError("Missing or invalid Authorization header", 401)
    token = header[len("Bearer "):]
    user_id, role = verify_token(token)
    with db_session() as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            raise ApiError("User not found", 401)
        roles = [r["role"] for r in conn.execute(
            "SELECT role FROM user_roles WHERE user_id = ?", (user_id,)
        ).fetchall()]
    if role not in roles:
        raise ApiError("Role not held by this user", 403)
    user["active_role"] = role
    user["roles"] = roles
    return user


def require_role(user, *allowed_roles):
    if user["active_role"] not in allowed_roles:
        raise ApiError(
            "This action requires one of: {}".format(", ".join(allowed_roles)), 403
        )
