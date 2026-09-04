from flask import Blueprint, jsonify, request

from app.auth import get_current_user, require_role
from app.database import db_session
from app.errors import ApiError
from app.services.audit_service import audit_event

bp = Blueprint("backlog", __name__, url_prefix="/api/backlog")

BACKLOG_STATUSES = ["no_current_need", "monitoring", "assistance_requested", "critical_internal_need"]


@bp.put("/stages/<int:stage_id>")
def set_backlog_signal(stage_id):
    """Team Lead declares a backlog signal on a stage (design.md FR12).

    This is an owner-declared operational signal, not an independently
    verified fact - spec section 11.1.
    """
    user = get_current_user()
    require_role(user, "team_lead", "workflow_owner")
    body = request.get_json(force=True) or {}
    status = body.get("backlog_status")
    if status not in BACKLOG_STATUSES:
        raise ApiError("Invalid backlog_status", 400)
    with db_session() as conn:
        stage = conn.execute("SELECT * FROM workflow_stages WHERE id = ?", (stage_id,)).fetchone()
        if not stage:
            raise ApiError("Stage not found", 404)
        workflow = conn.execute("SELECT * FROM workflows WHERE id = ?", (stage["workflow_id"],)).fetchone()
        # Backlog signals are an operational statement about your own team's
        # capacity - only people in the workflow's own department (or its
        # owner) may declare one, even if the workflow is visible org-wide.
        is_own_department = workflow and user["department_id"] and workflow["department_id"] == user["department_id"]
        is_owner = workflow and workflow["owner_id"] == user["id"]
        if "administrator" not in user["roles"] and not is_own_department and not is_owner:
            raise ApiError("You can only signal backlog need for your own department's workflows.", 403)
        conn.execute("UPDATE workflow_stages SET backlog_status = ? WHERE id = ?", (status, stage_id))
        audit_event(conn, user, "backlog.signal_set", "workflow_stage", stage_id)
        refreshed = conn.execute("SELECT * FROM workflow_stages WHERE id = ?", (stage_id,)).fetchone()
        return jsonify(refreshed)


@bp.get("/dashboard")
def backlog_dashboard():
    """List stages with a declared backlog need, plus any open opportunities
    already published from them (spec section 15.7)."""
    with db_session() as conn:
        stages = conn.execute(
            """SELECT ws.*, w.name as workflow_name FROM workflow_stages ws
               JOIN workflows w ON w.id = ws.workflow_id
               WHERE ws.backlog_status != 'no_current_need'
               ORDER BY ws.id"""
        ).fetchall()
        for s in stages:
            s["opportunities"] = conn.execute(
                "SELECT id, title, status FROM opportunities WHERE stage_id = ?", (s["id"],)
            ).fetchall()
        return jsonify(stages)
