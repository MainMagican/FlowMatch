from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from app.auth import get_current_user
from app.database import db_session
from app.errors import ApiError
from app.services.audit_service import audit_event

bp = Blueprint("feedback", __name__, url_prefix="/api/feedback")


def _now():
    return datetime.now(timezone.utc).isoformat()


@bp.post("/opportunities/<int:opportunity_id>")
def record_feedback(opportunity_id):
    """Contributor records a learning-feedback note (design.md FR27).
    This NEVER writes a rating/score field - only a free-text note."""
    user = get_current_user()
    body = request.get_json(force=True) or {}
    note = (body.get("note") or "").strip()
    if not note:
        raise ApiError("A learning-feedback note is required", 400)
    with db_session() as conn:
        cur = conn.execute(
            "INSERT INTO learning_feedback (opportunity_id, user_id, note, created_at) VALUES (?, ?, ?, ?)",
            (opportunity_id, user["id"], note, _now()),
        )
        feedback_id = cur.lastrowid
        audit_event(conn, user, "learning_feedback.recorded", "opportunity", opportunity_id)
        feedback = conn.execute("SELECT * FROM learning_feedback WHERE id = ?", (feedback_id,)).fetchone()
        return jsonify(feedback), 201


@bp.get("/opportunities/<int:opportunity_id>")
def list_feedback(opportunity_id):
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM learning_feedback WHERE opportunity_id = ? ORDER BY id", (opportunity_id,)
        ).fetchall()
        return jsonify(rows)
