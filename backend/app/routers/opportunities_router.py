import json
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from app.auth import get_current_user
from app.database import db_session
from app.errors import ApiError
from app.services.audit_service import audit_event

bp = Blueprint("opportunities", __name__, url_prefix="/api/opportunities")

OPPORTUNITY_STATUSES = [
    "draft", "awaiting_approval", "published", "matching", "pending_mutual_acceptance",
    "active", "submitted_for_review", "changes_requested", "completed", "withdrawn", "closed",
]

OPPORTUNITY_TYPES = [
    "shadow_for_a_day", "bounded_backlog_assistance", "ai_coaching",
    "automation_transfer", "process_discovery", "short_cross_team_project",
]

SHARE_SCOPES = ["company_wide", "department_only"]

# Statuses that are only worth showing to the drafter and the people who can
# approve it - a raw draft isn't "for grabs" yet (this session's ask: anyone
# can draft, but a Team Lead/manager must approve/publish before it's visible
# more broadly).
UNAPPROVED_STATUSES = {"draft", "awaiting_approval"}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _serialize(row):
    row["required_skills"] = json.loads(row["required_skills"] or "[]")
    row["learnable_skills"] = json.loads(row["learnable_skills"] or "[]")
    row["reusable_assets"] = json.loads(row["reusable_assets"] or "[]")
    return row


def _resolve_manager_id(conn, user_row):
    """Same fallback used in org_router/matches_router: explicit manager_id
    first, else the user's pod lead (if that isn't themselves)."""
    if not user_row:
        return None
    if user_row["manager_id"]:
        return user_row["manager_id"]
    if user_row["pod_id"]:
        pod = conn.execute("SELECT lead_user_id FROM pods WHERE id = ?", (user_row["pod_id"],)).fetchone()
        if pod and pod["lead_user_id"] and pod["lead_user_id"] != user_row["id"]:
            return pod["lead_user_id"]
    return None


def _opportunity_department_id(conn, opp):
    """Department the opportunity 'belongs to', for department_only sharing:
    prefer the source workflow's department, else fall back to the owner's."""
    if opp["workflow_id"]:
        wf = conn.execute("SELECT department_id FROM workflows WHERE id = ?", (opp["workflow_id"],)).fetchone()
        if wf and wf["department_id"]:
            return wf["department_id"]
    owner = conn.execute("SELECT department_id FROM users WHERE id = ?", (opp["owner_id"],)).fetchone()
    return owner["department_id"] if owner else None


def _approver_id(conn, opp):
    """Who can approve/publish this opportunity: the named reviewer if set,
    else the owner's manager/team lead."""
    if opp["reviewer_id"]:
        return opp["reviewer_id"]
    owner = conn.execute("SELECT * FROM users WHERE id = ?", (opp["owner_id"],)).fetchone()
    return _resolve_manager_id(conn, owner)


def _can_publish(conn, user, opp):
    """Only a Team Lead/workflow_owner (broad legacy permission), the named
    reviewer, or the drafter's own resolved manager may approve/publish an
    opportunity - approval stays tied to a real relationship, not just
    'anyone with a role' (this session's ask)."""
    if user["active_role"] in ("team_lead", "workflow_owner", "administrator"):
        return True
    if opp["reviewer_id"] == user["id"]:
        return True
    owner = conn.execute("SELECT * FROM users WHERE id = ?", (opp["owner_id"],)).fetchone()
    return _resolve_manager_id(conn, owner) == user["id"]


def _can_view(conn, user, opp):
    """Drafts/awaiting-approval opportunities are only visible to the
    drafter and whoever can approve them. Published+ opportunities are
    visible to everyone unless marked department_only, in which case only
    people in the same department (plus the owner/reviewer/approver) see it."""
    if opp["owner_id"] == user["id"] or opp["reviewer_id"] == user["id"]:
        return True
    if opp["status"] in UNAPPROVED_STATUSES:
        return _approver_id(conn, opp) == user["id"]
    if opp["share_scope"] == "department_only":
        opp_dept = _opportunity_department_id(conn, opp)
        return opp_dept is not None and opp_dept == user["department_id"]
    return True


def publish_validation_reasons(opportunity):
    """Return a list of human-readable reasons an opportunity cannot be
    published (design.md FR14). Empty list means publishable."""
    reasons = []
    if not opportunity.get("owner_id"):
        reasons.append("No named opportunity owner is set.")
    if not opportunity.get("reviewer_id"):
        reasons.append("No named reviewer is set.")
    if not (opportunity.get("definition_of_done") or "").strip():
        reasons.append("Definition of done is missing.")
    if not opportunity.get("sensitivity") or opportunity.get("sensitivity") == "unknown":
        reasons.append("Sensitivity classification is unknown.")
    if opportunity.get("mandatory_training") and not opportunity.get("required_authorization"):
        # If training is mandatory, required_authorization/access must also be stated explicitly.
        pass
    if opportunity.get("required_authorization") is None:
        reasons.append("Required access/authorization is undefined.")
    return reasons


@bp.get("/teach-matches")
def teach_matches():
    """For the current user: each skill they already have, cross-matched
    against colleagues who listed it as a learning goal - so 'I'm ready to
    help colleagues learn a skill I have' is a one-look, one-click flow
    instead of manually drafting an opportunity against workflow/stage IDs."""
    user = get_current_user()
    with db_session() as conn:
        my_skills = conn.execute(
            """SELECT s.id, s.name, us.proficiency FROM user_skills us
               JOIN skills s ON s.id = us.skill_id WHERE us.user_id = ?""",
            (user["id"],),
        ).fetchall()
        results = []
        for skill in my_skills:
            learners = conn.execute(
                """SELECT u.id, u.name, u.avatar_emoji, u.role_title, d.name as department_name
                   FROM learning_goals lg
                   JOIN users u ON u.id = lg.user_id
                   LEFT JOIN departments d ON d.id = u.department_id
                   WHERE lg.skill_id = ? AND lg.user_id != ?
                   ORDER BY u.name""",
                (skill["id"], user["id"]),
            ).fetchall()
            if learners:
                results.append({
                    "skill_id": skill["id"],
                    "skill_name": skill["name"],
                    "my_proficiency": skill["proficiency"],
                    "learners_count": len(learners),
                    "sample_learners": learners[:5],
                })
        results.sort(key=lambda r: r["learners_count"], reverse=True)
        return jsonify(results)


@bp.post("")
def create_opportunity():
    """Anyone can draft an opportunity (this session's ask). It only becomes
    visible for grabs once a Team Lead/manager approves and publishes it -
    see _can_view/_can_publish."""
    user = get_current_user()
    body = request.get_json(force=True) or {}
    if body.get("opportunity_type") not in OPPORTUNITY_TYPES:
        raise ApiError("Invalid opportunity_type", 400)
    share_scope = body.get("share_scope", "company_wide")
    if share_scope not in SHARE_SCOPES:
        raise ApiError("Invalid share_scope", 400)
    with db_session() as conn:
        reviewer_id = body.get("reviewer_id")
        if reviewer_id is None:
            # Default the reviewer to the drafter's own manager/team lead,
            # so there's always someone who can approve this draft.
            reviewer_id = _resolve_manager_id(conn, user)
        cur = conn.execute(
            """INSERT INTO opportunities
               (workflow_id, stage_id, title, problem_statement, opportunity_type, desired_outcome,
                definition_of_done, expected_deliverable, estimated_effort, required_skills,
                learnable_skills, required_ai_band, required_systems, required_authorization,
                mandatory_training, sensitivity, approved_ai_assistance, reusable_assets,
                owner_id, reviewer_id, mentor_available, escalation_points, start_conditions,
                participation_boundary, status, share_scope, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                body.get("workflow_id"), body.get("stage_id"), body.get("title", "Untitled opportunity"),
                body.get("problem_statement"), body.get("opportunity_type"), body.get("desired_outcome"),
                body.get("definition_of_done"), body.get("expected_deliverable"), body.get("estimated_effort"),
                json.dumps(body.get("required_skills", [])), json.dumps(body.get("learnable_skills", [])),
                body.get("required_ai_band"), body.get("required_systems"), body.get("required_authorization"),
                body.get("mandatory_training"), body.get("sensitivity", "unknown"),
                body.get("approved_ai_assistance"), json.dumps(body.get("reusable_assets", [])),
                body.get("owner_id", user["id"]), reviewer_id,
                1 if body.get("mentor_available") else 0, body.get("escalation_points"),
                body.get("start_conditions"), body.get("participation_boundary"),
                "draft", share_scope, _now(),
            ),
        )
        opp_id = cur.lastrowid
        audit_event(conn, user, "opportunity.created", "opportunity", opp_id)
        opp = conn.execute("SELECT * FROM opportunities WHERE id = ?", (opp_id,)).fetchone()
        return jsonify(_serialize(opp)), 201


@bp.get("")
def list_opportunities():
    user = get_current_user()
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM opportunities ORDER BY id").fetchall()
        visible = [r for r in rows if _can_view(conn, user, r)]
        return jsonify([_serialize(r) for r in visible])


@bp.get("/pending-my-approval")
def pending_my_approval():
    """Everything currently waiting on the current user to approve:
    1) Drafts/awaiting-approval opportunities where they're the approver
       (named reviewer, or the drafter's resolved manager).
    2) Opportunities they own that are pending_mutual_acceptance - i.e.
       someone expressed interest and is waiting on the owner (not the
       reviewer/manager) to accept them.
    Both surface in the same notification bell since both are 'something
    needs your approval' moments, even though different roles/relationships
    grant them."""
    user = get_current_user()
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM opportunities WHERE status IN ('draft', 'awaiting_approval') ORDER BY id"
        ).fetchall()
        mine = [r for r in rows if r["owner_id"] != user["id"] and _approver_id(conn, r) == user["id"]]
        result = []
        for r in mine:
            owner = conn.execute(
                "SELECT id, name, avatar_emoji, role_title FROM users WHERE id = ?", (r["owner_id"],)
            ).fetchone()
            entry = _serialize(r)
            entry["owner"] = owner
            entry["approval_kind"] = "draft_review"
            result.append(entry)

        interest_rows = conn.execute(
            "SELECT * FROM opportunities WHERE status = 'pending_mutual_acceptance' AND owner_id = ? ORDER BY id",
            (user["id"],),
        ).fetchall()
        for r in interest_rows:
            eoi = conn.execute(
                "SELECT * FROM expressions_of_interest WHERE opportunity_id = ? AND status = 'accepted_by_contributor' ORDER BY id DESC LIMIT 1",
                (r["id"],),
            ).fetchone()
            contributor = (
                conn.execute(
                    "SELECT id, name, avatar_emoji, role_title FROM users WHERE id = ?", (eoi["user_id"],)
                ).fetchone()
                if eoi else None
            )
            entry = _serialize(r)
            entry["contributor"] = contributor
            entry["approval_kind"] = "interest_approval"
            result.append(entry)
        return jsonify(result)


@bp.get("/my-drafts")
def my_drafts():
    """The current user's own draft/awaiting-approval opportunities, with
    the resolved approver attached - so a drafter can see 'pending with your
    TL <name>' instead of wondering where their request went."""
    user = get_current_user()
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM opportunities WHERE owner_id = ? AND status IN ('draft', 'awaiting_approval') ORDER BY id",
            (user["id"],),
        ).fetchall()
        result = []
        for r in rows:
            approver_id = _approver_id(conn, r)
            approver = (
                conn.execute(
                    "SELECT id, name, avatar_emoji, role_title FROM users WHERE id = ?", (approver_id,)
                ).fetchone()
                if approver_id else None
            )
            entry = _serialize(r)
            entry["approver"] = approver
            result.append(entry)
        return jsonify(result)


@bp.get("/<int:opportunity_id>")
def get_opportunity(opportunity_id):
    user = get_current_user()
    with db_session() as conn:
        row = conn.execute("SELECT * FROM opportunities WHERE id = ?", (opportunity_id,)).fetchone()
        if not row:
            raise ApiError("Opportunity not found", 404)
        if not _can_view(conn, user, row):
            raise ApiError("You don't have access to this opportunity", 403)
        opp = _serialize(row)
        approver_id = _approver_id(conn, row)
        opp["approver"] = (
            conn.execute(
                "SELECT id, name, avatar_emoji, role_title FROM users WHERE id = ?", (approver_id,)
            ).fetchone()
            if approver_id else None
        )
        opp["owner"] = (
            conn.execute(
                "SELECT id, name, avatar_emoji, role_title FROM users WHERE id = ?", (row["owner_id"],)
            ).fetchone()
            if row["owner_id"] else None
        )
        opp["can_current_user_publish"] = _can_publish(conn, user, row)
        return jsonify(opp)


# Fields the drafter or an approver may fix up before/while approving a
# draft - deliberately scoped to the fields that publish_validation_reasons()
# actually checks (plus a few closely related ones), so "fix the mandatory
# fields, then approve" is a single smooth flow instead of a dead end.
EDITABLE_DRAFT_FIELDS = [
    "title", "problem_statement", "desired_outcome", "definition_of_done",
    "expected_deliverable", "estimated_effort", "sensitivity",
    "required_authorization", "share_scope", "reviewer_id",
]


@bp.put("/<int:opportunity_id>")
def update_opportunity(opportunity_id):
    """Let the owner or whoever can approve this opportunity patch its
    mandatory fields (definition of done, sensitivity, required
    authorization, etc.) directly - so an approver who spots a gap can fix
    it and publish in one place, rather than being stuck on a hard error."""
    user = get_current_user()
    body = request.get_json(force=True) or {}
    with db_session() as conn:
        opp = conn.execute("SELECT * FROM opportunities WHERE id = ?", (opportunity_id,)).fetchone()
        if not opp:
            raise ApiError("Opportunity not found", 404)
        if opp["owner_id"] != user["id"] and not _can_publish(conn, user, opp):
            raise ApiError("Only the drafter or an approver can edit this opportunity", 403)
        if "share_scope" in body and body["share_scope"] not in SHARE_SCOPES:
            raise ApiError("Invalid share_scope", 400)
        updates = {k: body[k] for k in EDITABLE_DRAFT_FIELDS if k in body}
        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE opportunities SET {set_clause} WHERE id = ?",
                (*updates.values(), opportunity_id),
            )
            audit_event(conn, user, "opportunity.edited", "opportunity", opportunity_id)
        refreshed = conn.execute("SELECT * FROM opportunities WHERE id = ?", (opportunity_id,)).fetchone()
        return jsonify(_serialize(refreshed))


@bp.post("/<int:opportunity_id>/publish")
def publish_opportunity(opportunity_id):
    """Publish (approve) an opportunity, or block with structured reasons
    (design.md FR14). Only the named reviewer, the drafter's resolved
    manager, or a broad Team Lead/workflow_owner/administrator may approve."""
    user = get_current_user()
    with db_session() as conn:
        opp = conn.execute("SELECT * FROM opportunities WHERE id = ?", (opportunity_id,)).fetchone()
        if not opp:
            raise ApiError("Opportunity not found", 404)
        if not _can_publish(conn, user, opp):
            raise ApiError("Only your Team Lead/manager can approve and publish this opportunity", 403)
        reasons = publish_validation_reasons(opp)
        if reasons:
            audit_event(conn, user, "opportunity.publish_blocked", "opportunity", opportunity_id)
            raise ApiError("Opportunity cannot be published yet", 422, reasons=reasons)
        conn.execute("UPDATE opportunities SET status = 'published' WHERE id = ?", (opportunity_id,))
        audit_event(conn, user, "opportunity.published", "opportunity", opportunity_id, human_approved=True)
        refreshed = conn.execute("SELECT * FROM opportunities WHERE id = ?", (opportunity_id,)).fetchone()
        return jsonify(_serialize(refreshed))


@bp.post("/<int:opportunity_id>/status")
def set_status(opportunity_id):
    """Generic status transition for the remaining lifecycle states
    (design.md FR15) - used by the matching/workspace/review flows."""
    user = get_current_user()
    body = request.get_json(force=True) or {}
    target = body.get("status")
    if target not in OPPORTUNITY_STATUSES:
        raise ApiError("Invalid status", 400)
    with db_session() as conn:
        opp = conn.execute("SELECT * FROM opportunities WHERE id = ?", (opportunity_id,)).fetchone()
        if not opp:
            raise ApiError("Opportunity not found", 404)
        conn.execute("UPDATE opportunities SET status = ? WHERE id = ?", (target, opportunity_id))
        audit_event(conn, user, "opportunity.status_changed:{}".format(target), "opportunity", opportunity_id)
        refreshed = conn.execute("SELECT * FROM opportunities WHERE id = ?", (opportunity_id,)).fetchone()
        return jsonify(_serialize(refreshed))
