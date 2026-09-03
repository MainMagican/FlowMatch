from flask import Blueprint, jsonify

from app.auth import get_current_user, require_role
from app.database import db_session

bp = Blueprint("audit", __name__, url_prefix="/api/audit")


@bp.get("")
def list_audit_events():
    """Role-appropriate audit feed (design.md FR28). Administrators see all
    metadata; other roles only see their own actions - never exposing
    unnecessary business content (spec section 15.13)."""
    user = get_current_user()
    with db_session() as conn:
        if user["active_role"] == "administrator":
            rows = conn.execute("SELECT * FROM audit_events ORDER BY id DESC LIMIT 200").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM audit_events WHERE actor_user_id = ? ORDER BY id DESC LIMIT 200",
                (user["id"],),
            ).fetchall()
        return jsonify(rows)
