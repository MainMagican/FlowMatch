import json
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from app.auth import get_current_user, require_role
from app.database import db_session
from app.errors import ApiError
from app.services.audit_service import audit_event
from app.services.workflow_extraction_service import WorkflowExtractionService

bp = Blueprint("workflows", __name__, url_prefix="/api/workflows")

extraction_service = WorkflowExtractionService()

VALIDATION_STATES = [
    "draft",
    "ai_generated_draft",
    "needs_owner_review",
    "validated",
    "published",
    "archived",
]

# Allowed forward transitions for the validation-status state machine
# (design.md FR9). Only workflow_owner may perform validate/publish steps.
TRANSITIONS = {
    "draft": ["needs_owner_review"],
    "ai_generated_draft": ["needs_owner_review"],
    "needs_owner_review": ["validated"],
    "validated": ["published", "needs_owner_review"],
    "published": ["archived"],
    "archived": [],
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _serialize_workflow(conn, workflow):
    stages = conn.execute(
        "SELECT * FROM workflow_stages WHERE workflow_id = ? ORDER BY sequence",
        (workflow["id"],),
    ).fetchall()
    for s in stages:
        s["uncertain_fields"] = json.loads(s["uncertain_fields"] or "[]")
    workflow["stages"] = stages
    workflow["department_name"] = None
    workflow["pod_name"] = None
    if workflow["department_id"]:
        dept = conn.execute("SELECT name FROM departments WHERE id = ?", (workflow["department_id"],)).fetchone()
        workflow["department_name"] = dept["name"] if dept else None
    if workflow["pod_id"]:
        pod = conn.execute("SELECT name FROM pods WHERE id = ?", (workflow["pod_id"],)).fetchone()
        workflow["pod_name"] = pod["name"] if pod else None
    return workflow


@bp.get("")
def list_workflows():
    """List workflows. Only validated/published workflows are visible to
    users who are not the owner/reviewer (design.md FR9)."""
    user = get_current_user()
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM workflows ORDER BY id").fetchall()
        visible = [
            w for w in rows
            if w["validation_status"] in ("validated", "published")
            or w["owner_id"] == user["id"]
            or w["reviewer_id"] == user["id"]
        ]
        return jsonify([_serialize_workflow(conn, w) for w in visible])


@bp.get("/<int:workflow_id>")
def get_workflow(workflow_id):
    with db_session() as conn:
        workflow = conn.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
        if not workflow:
            raise ApiError("Workflow not found", 404)
        return jsonify(_serialize_workflow(conn, workflow))


@bp.put("/<int:workflow_id>")
def edit_workflow(workflow_id):
    """Rewrite a workflow's own name/purpose/description, or reassign it to a
    different department/team (design.md FR8)."""
    user = get_current_user()
    require_role(user, "team_lead", "workflow_owner")
    body = request.get_json(force=True) or {}
    editable_fields = ["name", "description", "business_purpose", "sensitivity", "department_id", "pod_id"]
    updates = {k: v for k, v in body.items() if k in editable_fields}
    if not updates:
        raise ApiError("No editable fields supplied", 400)
    with db_session() as conn:
        workflow = conn.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
        if not workflow:
            raise ApiError("Workflow not found", 404)
        set_clause = ", ".join("{} = ?".format(k) for k in updates)
        conn.execute(
            "UPDATE workflows SET {} WHERE id = ?".format(set_clause),
            (*updates.values(), workflow_id),
        )
        audit_event(conn, user, "workflow.edited", "workflow", workflow_id)
        refreshed = conn.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
        return jsonify(_serialize_workflow(conn, refreshed))


@bp.post("")
def create_workflow():
    """Create a workflow via one of three intake paths (design.md FR7):
    - source_type="manual": stages array supplied directly
    - source_type="pasted_text": source_text is run through the deterministic
      WorkflowExtractionService to produce an AI-generated draft
    """
    user = get_current_user()
    require_role(user, "team_lead", "workflow_owner")
    body = request.get_json(force=True) or {}
    source_type = body.get("source_type")
    if source_type not in ("manual", "pasted_text"):
        raise ApiError("source_type must be 'manual' or 'pasted_text'", 400)

    with db_session() as conn:
        cur = conn.execute(
            """INSERT INTO workflows (name, description, department_id, pod_id, business_purpose,
                   owner_id, reviewer_id, source_type, source_text, validation_status, sensitivity, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                body.get("name", "Untitled workflow"),
                body.get("description"),
                body.get("department_id") or user["department_id"],
                body.get("pod_id") or user["pod_id"],
                body.get("business_purpose"),
                body.get("owner_id", user["id"]),
                body.get("reviewer_id"),
                source_type,
                body.get("source_text"),
                "ai_generated_draft" if source_type == "pasted_text" else "draft",
                body.get("sensitivity", "unknown"),
                _now(),
            ),
        )
        workflow_id = cur.lastrowid

        if source_type == "pasted_text":
            stages = extraction_service.extract_stages(body.get("source_text", ""))
        else:
            stages = body.get("stages", [])

        for stage in stages:
            conn.execute(
                """INSERT INTO workflow_stages
                   (workflow_id, name, description, sequence, activities, responsible_role,
                    inputs, outputs, systems, handoffs, decision_points, ai_generated, uncertain_fields)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    workflow_id,
                    stage.get("name", "Stage"),
                    stage.get("description"),
                    stage.get("sequence", 1),
                    stage.get("activities"),
                    stage.get("responsible_role"),
                    stage.get("inputs"),
                    stage.get("outputs"),
                    stage.get("systems"),
                    stage.get("handoffs"),
                    stage.get("decision_points"),
                    1 if stage.get("ai_generated") else 0,
                    json.dumps(stage.get("uncertain_fields", [])),
                ),
            )
        workflow = conn.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
        audit_event(conn, user, "workflow.created", "workflow", workflow_id, ai_involved=(source_type == "pasted_text"))
        return jsonify(_serialize_workflow(conn, workflow)), 201


@bp.put("/<int:workflow_id>/stages/<int:stage_id>")
def edit_stage(workflow_id, stage_id):
    """Owner/lead edits a stage - used to correct AI-drafted fields (design.md FR8)."""
    user = get_current_user()
    require_role(user, "team_lead", "workflow_owner")
    body = request.get_json(force=True) or {}
    editable_fields = [
        "name", "description", "activities", "responsible_role", "inputs", "outputs",
        "systems", "handoffs", "decision_points", "effort", "frequency", "backlog_status",
        "bottleneck", "automation_maturity", "existing_automation", "sensitivity", "controls",
        "access_requirements", "suitable_shadowing", "suitable_bounded_help",
        "suitable_process_discovery", "suitable_automation_reuse", "required_reviewer_id",
    ]
    updates = {k: v for k, v in body.items() if k in editable_fields}
    if not updates:
        raise ApiError("No editable fields supplied", 400)
    with db_session() as conn:
        stage = conn.execute("SELECT * FROM workflow_stages WHERE id = ? AND workflow_id = ?", (stage_id, workflow_id)).fetchone()
        if not stage:
            raise ApiError("Stage not found", 404)
        set_clause = ", ".join("{} = ?".format(k) for k in updates)
        conn.execute(
            "UPDATE workflow_stages SET {} WHERE id = ?".format(set_clause),
            (*updates.values(), stage_id),
        )
        # Once a human edits a field, remove it from the AI-uncertain list.
        uncertain = json.loads(stage["uncertain_fields"] or "[]")
        uncertain = [f for f in uncertain if f not in updates]
        conn.execute(
            "UPDATE workflow_stages SET uncertain_fields = ? WHERE id = ?",
            (json.dumps(uncertain), stage_id),
        )
        refreshed = conn.execute("SELECT * FROM workflow_stages WHERE id = ?", (stage_id,)).fetchone()
        refreshed["uncertain_fields"] = json.loads(refreshed["uncertain_fields"] or "[]")
        return jsonify(refreshed)


@bp.post("/<int:workflow_id>/stages")
def add_stage(workflow_id):
    """Add a new step to an existing workflow (design.md FR8 - editing/
    extending workflows). Appended at the end unless a sequence is given."""
    user = get_current_user()
    require_role(user, "team_lead", "workflow_owner")
    body = request.get_json(force=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        raise ApiError("Stage name is required", 400)
    with db_session() as conn:
        workflow = conn.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
        if not workflow:
            raise ApiError("Workflow not found", 404)
        max_seq = conn.execute(
            "SELECT COALESCE(MAX(sequence), 0) as m FROM workflow_stages WHERE workflow_id = ?", (workflow_id,)
        ).fetchone()["m"]
        sequence = body.get("sequence") or (max_seq + 1)
        cur = conn.execute(
            """INSERT INTO workflow_stages
               (workflow_id, name, description, sequence, activities, responsible_role,
                backlog_status, automation_maturity, sensitivity, ai_generated, uncertain_fields)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                workflow_id, name, body.get("description"), sequence,
                body.get("activities"), body.get("responsible_role"),
                "no_current_need", body.get("automation_maturity", "manual"),
                body.get("sensitivity", "low"), 0, "[]",
            ),
        )
        audit_event(conn, user, "workflow.stage_added", "workflow", workflow_id)
        stage = conn.execute("SELECT * FROM workflow_stages WHERE id = ?", (cur.lastrowid,)).fetchone()
        stage["uncertain_fields"] = json.loads(stage["uncertain_fields"] or "[]")
        return jsonify(stage), 201


@bp.delete("/<int:workflow_id>/stages/<int:stage_id>")
def delete_stage(workflow_id, stage_id):
    """Remove a step from a workflow (design.md FR8)."""
    user = get_current_user()
    require_role(user, "team_lead", "workflow_owner")
    with db_session() as conn:
        stage = conn.execute(
            "SELECT * FROM workflow_stages WHERE id = ? AND workflow_id = ?", (stage_id, workflow_id)
        ).fetchone()
        if not stage:
            raise ApiError("Stage not found", 404)
        conn.execute("DELETE FROM workflow_stages WHERE id = ?", (stage_id,))
        audit_event(conn, user, "workflow.stage_removed", "workflow", workflow_id)
        return jsonify({"deleted": True, "id": stage_id})


@bp.post("/<int:workflow_id>/transition")
def transition_workflow(workflow_id):
    """Move a workflow through the validation lifecycle (design.md FR9).

    Only the workflow_owner role may validate or publish; server-side check
    (not just hidden UI), per design.md FR3/spec section 16.
    """
    user = get_current_user()
    body = request.get_json(force=True) or {}
    target = body.get("target_status")
    if target not in VALIDATION_STATES:
        raise ApiError("Invalid target_status", 400)
    with db_session() as conn:
        workflow = conn.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
        if not workflow:
            raise ApiError("Workflow not found", 404)
        current = workflow["validation_status"]
        if target not in TRANSITIONS.get(current, []):
            raise ApiError(
                "Cannot move workflow from '{}' to '{}'".format(current, target), 400
            )
        if target in ("validated", "published") and workflow["owner_id"] != user["id"]:
            raise ApiError("Only the workflow owner can validate/publish this workflow", 403)
        require_role(user, "workflow_owner", "team_lead")
        conn.execute(
            "UPDATE workflows SET validation_status = ?, last_reviewed_at = ? WHERE id = ?",
            (target, _now(), workflow_id),
        )
        audit_event(
            conn, user, "workflow.{}".format(target), "workflow", workflow_id,
            human_approved=True,
        )
        refreshed = conn.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
        return jsonify(_serialize_workflow(conn, refreshed))
