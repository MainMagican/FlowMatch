from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from app.auth import get_current_user
from app.database import db_session
from app.errors import ApiError
from app.services.audit_service import audit_event
from app.services.guided_task_assistant_service import GuidedTaskAssistantService

bp = Blueprint("workspace", __name__, url_prefix="/api/workspaces")

assistant_service = GuidedTaskAssistantService()


def _now():
    return datetime.now(timezone.utc).isoformat()


@bp.get("/by-opportunity/<int:opportunity_id>")
def get_workspace(opportunity_id):
    """Open the Guided Workspace for an Active opportunity (design.md FR23)."""
    user = get_current_user()
    with db_session() as conn:
        workspace = conn.execute(
            "SELECT * FROM workspaces WHERE opportunity_id = ? ORDER BY id DESC LIMIT 1", (opportunity_id,)
        ).fetchone()
        if not workspace:
            raise ApiError("Workspace not found - opportunity may not be active yet", 404)
        opportunity = conn.execute("SELECT * FROM opportunities WHERE id = ?", (opportunity_id,)).fetchone()
        stage = conn.execute("SELECT * FROM workflow_stages WHERE id = ?", (opportunity["stage_id"],)).fetchone() if opportunity["stage_id"] else None
        workflow = conn.execute("SELECT * FROM workflows WHERE id = ?", (opportunity["workflow_id"],)).fetchone() if opportunity["workflow_id"] else None
        guidance = assistant_service.build_guidance(opportunity, stage, workflow)
        submissions = conn.execute("SELECT * FROM submissions WHERE workspace_id = ? ORDER BY id", (workspace["id"],)).fetchall()
        return jsonify({
            "workspace": workspace,
            "opportunity": opportunity,
            "stage": stage,
            "guidance": guidance,
            "submissions": submissions,
        })


@bp.post("/<int:workspace_id>/submissions")
def submit_output(workspace_id):
    """Contributor submits a draft output for review (design.md FR25)."""
    user = get_current_user()
    body = request.get_json(force=True) or {}
    content = (body.get("content") or "").strip()
    if not content:
        raise ApiError("Submission content is required", 400)
    with db_session() as conn:
        workspace = conn.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
        if not workspace:
            raise ApiError("Workspace not found", 404)
        cur = conn.execute(
            "INSERT INTO submissions (workspace_id, user_id, content, created_at) VALUES (?, ?, ?, ?)",
            (workspace_id, user["id"], content, _now()),
        )
        submission_id = cur.lastrowid
        conn.execute("UPDATE opportunities SET status = 'submitted_for_review' WHERE id = ?", (workspace["opportunity_id"],))
        audit_event(conn, user, "submission.created", "submission", submission_id)
        submission = conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()
        return jsonify(submission), 201
