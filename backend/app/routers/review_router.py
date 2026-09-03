from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from app.auth import get_current_user, require_role
from app.database import db_session
from app.errors import ApiError
from app.services.audit_service import audit_event

bp = Blueprint("review", __name__, url_prefix="/api/reviews")

DECISIONS = ["accepted", "changes_requested", "rejected"]


def _now():
    return datetime.now(timezone.utc).isoformat()


@bp.post("/submissions/<int:submission_id>")
def review_submission(submission_id):
    """Reviewer accepts, requests changes, or rejects-with-reason
    (design.md FR26, spec section 15.12)."""
    user = get_current_user()
    require_role(user, "reviewer")
    body = request.get_json(force=True) or {}
    decision = body.get("decision")
    if decision not in DECISIONS:
        raise ApiError("decision must be one of {}".format(DECISIONS), 400)
    if decision == "rejected" and not (body.get("reason") or "").strip():
        raise ApiError("A reason is required to reject a submission", 400)
    with db_session() as conn:
        submission = conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()
        if not submission:
            raise ApiError("Submission not found", 404)
        workspace = conn.execute("SELECT * FROM workspaces WHERE id = ?", (submission["workspace_id"],)).fetchone()
        cur = conn.execute(
            """INSERT INTO reviews (submission_id, reviewer_id, decision, reason,
                   delivered_expected_result, appropriate_for_reuse, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                submission_id, user["id"], decision, body.get("reason"),
                1 if body.get("delivered_expected_result") else 0,
                1 if body.get("appropriate_for_reuse") else 0,
                _now(),
            ),
        )
        review_id = cur.lastrowid
        new_status = {
            "accepted": "completed",
            "changes_requested": "changes_requested",
            "rejected": "closed",
        }[decision]
        conn.execute("UPDATE opportunities SET status = ? WHERE id = ?", (new_status, workspace["opportunity_id"]))
        audit_event(conn, user, "review.completed:{}".format(decision), "submission", submission_id, human_approved=True)
        review = conn.execute("SELECT * FROM reviews WHERE id = ?", (review_id,)).fetchone()
        return jsonify(review), 201
