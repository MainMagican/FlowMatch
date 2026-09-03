import json

from flask import Blueprint, jsonify, request

from app.auth import get_current_user, issue_token
from app.database import db_session
from app.errors import ApiError

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.get("/demo-users")
def list_demo_users():
    """List every seeded persona + roles, so the login screen can offer a picker
    (docs/DECISIONS.md #3 - no passwords, no real SSO in this MVP)."""
    with db_session() as conn:
        users = conn.execute(
            """
            SELECT u.id, u.name, u.email, u.avatar_emoji, u.role_title,
                   d.name as department_name, p.name as pod_name
            FROM users u
            LEFT JOIN departments d ON d.id = u.department_id
            LEFT JOIN pods p ON p.id = u.pod_id
            ORDER BY u.id
            """
        ).fetchall()
        for u in users:
            roles = conn.execute(
                "SELECT role FROM user_roles WHERE user_id = ?", (u["id"],)
            ).fetchall()
            u["roles"] = [r["role"] for r in roles]
    return jsonify(users)


@bp.post("/login")
def login():
    body = request.get_json(force=True, silent=True) or {}
    user_id = body.get("user_id")
    role = body.get("role")
    if not user_id or not role:
        raise ApiError("user_id and role are required", 400)
    with db_session() as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            raise ApiError("Unknown user_id", 404)
        held_roles = [
            r["role"] for r in conn.execute(
                "SELECT role FROM user_roles WHERE user_id = ?", (user_id,)
            ).fetchall()
        ]
    if role not in held_roles:
        raise ApiError("This user does not hold the '{}' role".format(role), 403)
    token = issue_token(user_id, role)
    return jsonify({"token": token, "user": {**user, "active_role": role, "roles": held_roles}})


@bp.get("/me")
def me():
    user = get_current_user()
    return jsonify(user)
