from flask import Blueprint, jsonify, request

from app.auth import get_current_user, require_role
from app.database import db_session
from app.errors import ApiError
from app.services.audit_service import audit_event

bp = Blueprint("reusable_assets", __name__, url_prefix="/api/reusable-assets")


@bp.post("")
def create_asset():
    """Attach a Reusable Asset to a workflow (owner-only, design.md FR22)."""
    user = get_current_user()
    require_role(user, "workflow_owner", "mentor")
    body = request.get_json(force=True) or {}
    with db_session() as conn:
        workflow = conn.execute("SELECT * FROM workflows WHERE id = ?", (body.get("workflow_id"),)).fetchone()
        if not workflow:
            raise ApiError("Workflow not found", 404)
        cur = conn.execute(
            """INSERT INTO reusable_assets
               (workflow_id, name, type, description, owner_id, approved_users, reuse_permission,
                documentation_status, dependencies, required_systems, known_constraints,
                risk_classification, review_date, transfer_contact)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                body["workflow_id"], body.get("name", "Untitled asset"), body.get("type", "template"),
                body.get("description"), user["id"], "[]", body.get("reuse_permission", "requires_review"),
                body.get("documentation_status", "draft"), body.get("dependencies"),
                body.get("required_systems"), body.get("known_constraints"),
                body.get("risk_classification", "unknown"), body.get("review_date"),
                body.get("transfer_contact"),
            ),
        )
        asset_id = cur.lastrowid
        audit_event(conn, user, "reusable_asset.created", "reusable_asset", asset_id)
        asset = conn.execute("SELECT * FROM reusable_assets WHERE id = ?", (asset_id,)).fetchone()
        return jsonify(asset), 201


@bp.get("")
def list_assets():
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM reusable_assets ORDER BY id").fetchall()
        return jsonify(rows)
