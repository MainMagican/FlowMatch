import json
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from app.auth import get_current_user
from app.database import db_session
from app.errors import ApiError
from app.services.audit_service import audit_event
from app.services.eligibility_service import check_eligibility
from app.services.match_explanation_service import MatchExplanationService
from app.services.matching_service import compute_relevance_components, internal_sort_score
from app.routers.opportunities_router import _serialize as serialize_opportunity

bp = Blueprint("matches", __name__, url_prefix="/api/matches")

explanation_service = MatchExplanationService()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _resolve_manager_id(conn, user):
    """Same fallback as GET /api/org/me: explicit manager_id first, else the
    user's pod lead (if that isn't themselves)."""
    if user["manager_id"]:
        return user["manager_id"]
    if user["pod_id"]:
        pod = conn.execute("SELECT lead_user_id FROM pods WHERE id = ?", (user["pod_id"],)).fetchone()
        if pod and pod["lead_user_id"] and pod["lead_user_id"] != user["id"]:
            return pod["lead_user_id"]
    return None


@bp.get("/recommendations")
def list_recommendations():
    """Eligibility-filtered, explainable recommendations for the current
    contributor (design.md FR16-19). Ineligible opportunities are excluded
    entirely, never shown with a caveat."""
    user = get_current_user()
    with db_session() as conn:
        opportunities = conn.execute("SELECT * FROM opportunities WHERE status = 'published'").fetchall()
        results = []
        for opp in opportunities:
            eligible, reasons = check_eligibility(conn, opp, user)
            if not eligible:
                # Recorded so the "blocked match" demo path is auditable, but
                # NOT returned to the contributor as a recommendation.
                continue
            components = compute_relevance_components(conn, opp, user)
            cur = conn.execute(
                "INSERT INTO match_recommendations (opportunity_id, user_id, created_at) VALUES (?, ?, ?)",
                (opp["id"], user["id"], _now()),
            )
            match_id = cur.lastrowid
            for c in components:
                conn.execute(
                    "INSERT INTO match_explanation_components (match_id, component_name, detail, matched) VALUES (?, ?, ?, ?)",
                    (match_id, c["component_name"], c["detail"], 1 if c["matched"] else 0),
                )
            explanation = explanation_service.build_explanation(opp, components, reasons)
            audit_event(conn, user, "match.recommendation_generated", "opportunity", opp["id"], ai_involved=True)
            results.append({
                "match_id": match_id,
                "opportunity": serialize_opportunity(dict(opp)),
                "explanation": explanation,
                "_sort_score": internal_sort_score(components),
            })
        results.sort(key=lambda r: r["_sort_score"], reverse=True)
        for r in results:
            del r["_sort_score"]
        return jsonify(results)


@bp.get("/eligibility-check/<int:opportunity_id>")
def eligibility_check(opportunity_id):
    """Debug/demo endpoint: explicitly show why a given user is or isn't
    eligible for an opportunity - used to demonstrate the blocked-match path."""
    user = get_current_user()
    with db_session() as conn:
        opp = conn.execute("SELECT * FROM opportunities WHERE id = ?", (opportunity_id,)).fetchone()
        if not opp:
            raise ApiError("Opportunity not found", 404)
        eligible, reasons = check_eligibility(conn, opp, user)
        return jsonify({"eligible": eligible, "reasons": reasons})


@bp.post("/<int:opportunity_id>/express-interest")
def express_interest(opportunity_id):
    """Anyone eligible can grab/shadow a published opportunity - this is the
    platform's core 'help/learn' action, so it isn't gated behind a specific
    role. Real fitness is enforced by check_eligibility() below, not by
    which role the person happened to log in as."""
    user = get_current_user()
    with db_session() as conn:
        opp = conn.execute("SELECT * FROM opportunities WHERE id = ?", (opportunity_id,)).fetchone()
        if not opp:
            raise ApiError("Opportunity not found", 404)
        eligible, reasons = check_eligibility(conn, opp, user)
        if not eligible:
            raise ApiError("You are not eligible for this opportunity", 403, reasons=reasons)
        conn.execute(
            "INSERT INTO expressions_of_interest (opportunity_id, user_id, status, created_at) VALUES (?, ?, 'accepted_by_contributor', ?)",
            (opportunity_id, user["id"], _now()),
        )
        conn.execute("UPDATE opportunities SET status = 'pending_mutual_acceptance' WHERE id = ?", (opportunity_id,))
        audit_event(conn, user, "match.accepted_by_contributor", "opportunity", opportunity_id)
        return jsonify({"status": "pending_mutual_acceptance"})


@bp.post("/<int:opportunity_id>/decline")
def decline_interest(opportunity_id):
    user = get_current_user()
    with db_session() as conn:
        conn.execute(
            "INSERT INTO expressions_of_interest (opportunity_id, user_id, status, created_at) VALUES (?, ?, 'declined', ?)",
            (opportunity_id, user["id"], _now()),
        )
        audit_event(conn, user, "match.declined", "opportunity", opportunity_id)
        return jsonify({"status": "declined"})


@bp.post("/<int:opportunity_id>/approve")
def approve_interest(opportunity_id):
    """Opportunity owner approves an accepted expression of interest,
    completing mutual acceptance (design.md FR20) and opening a workspace.
    Gated by actual ownership of the opportunity, not by active_role - an
    owner shouldn't be blocked from approving their own opportunity just
    because they logged in under a different held role."""
    user = get_current_user()
    with db_session() as conn:
        opp = conn.execute("SELECT * FROM opportunities WHERE id = ?", (opportunity_id,)).fetchone()
        if not opp:
            raise ApiError("Opportunity not found", 404)
        if opp["owner_id"] != user["id"]:
            raise ApiError("Only the opportunity owner can approve", 403)
        eoi = conn.execute(
            "SELECT * FROM expressions_of_interest WHERE opportunity_id = ? AND status = 'accepted_by_contributor' ORDER BY id DESC LIMIT 1",
            (opportunity_id,),
        ).fetchone()
        if not eoi:
            raise ApiError("No pending expression of interest to approve", 400)
        conn.execute("UPDATE expressions_of_interest SET status = 'approved_by_owner' WHERE id = ?", (eoi["id"],))
        conn.execute("UPDATE opportunities SET status = 'active' WHERE id = ?", (opportunity_id,))
        conn.execute("INSERT INTO workspaces (opportunity_id, created_at) VALUES (?, ?)", (opportunity_id, _now()))
        audit_event(conn, user, "match.approved_by_owner", "opportunity", opportunity_id, human_approved=True)
        return jsonify({"status": "active"})


@bp.get("/my-manager")
def my_manager():
    """Who's your team lead/manager for this opportunity flow - shown on the
    opportunity page so a contributor knows exactly who they're flagging."""
    user = get_current_user()
    with db_session() as conn:
        manager_id = _resolve_manager_id(conn, user)
        if not manager_id:
            return jsonify({"manager": None})
        manager = conn.execute(
            "SELECT id, name, avatar_emoji, role_title FROM users WHERE id = ?", (manager_id,)
        ).fetchone()
        return jsonify({"manager": manager})


@bp.post("/<int:opportunity_id>/request-tl-support")
def request_tl_support(opportunity_id):
    """Contributor sends their manager/team-lead a heads-up that they want to
    shadow or take this opportunity, so the TL can see their team's interest
    even when the TL isn't the opportunity owner. Visibility only - does not
    replace the opportunity owner's formal approval (design.md FR20)."""
    user = get_current_user()
    body = request.get_json(force=True) or {}
    with db_session() as conn:
        opp = conn.execute("SELECT * FROM opportunities WHERE id = ?", (opportunity_id,)).fetchone()
        if not opp:
            raise ApiError("Opportunity not found", 404)
        manager_id = _resolve_manager_id(conn, user)
        if not manager_id:
            raise ApiError("You don't have a manager/team lead on record to notify", 400)
        cur = conn.execute(
            """INSERT INTO manager_requests (opportunity_id, contributor_id, manager_id, note, status, created_at)
               VALUES (?, ?, ?, ?, 'pending', ?)""",
            (opportunity_id, user["id"], manager_id, body.get("note"), _now()),
        )
        audit_event(conn, user, "match.tl_support_requested", "opportunity", opportunity_id)
        request_row = conn.execute("SELECT * FROM manager_requests WHERE id = ?", (cur.lastrowid,)).fetchone()
        return jsonify(request_row), 201


@bp.get("/team-requests")
def list_team_requests():
    """A team lead's queue of their direct reports' expressed interest in
    opportunities - so a manager can actually see who on their team wants to
    shadow or take something on, regardless of who owns the opportunity."""
    user = get_current_user()
    with db_session() as conn:
        rows = conn.execute(
            """SELECT mr.*, u.name as contributor_name, u.avatar_emoji as contributor_avatar,
                      u.role_title as contributor_role_title,
                      o.title as opportunity_title, o.status as opportunity_status,
                      o.opportunity_type as opportunity_type
               FROM manager_requests mr
               JOIN users u ON u.id = mr.contributor_id
               JOIN opportunities o ON o.id = mr.opportunity_id
               WHERE mr.manager_id = ?
               ORDER BY mr.status ASC, mr.id DESC""",
            (user["id"],),
        ).fetchall()
        return jsonify(rows)


@bp.post("/team-requests/<int:request_id>/acknowledge")
def acknowledge_team_request(request_id):
    """Team lead acknowledges they've seen a team member's request."""
    user = get_current_user()
    with db_session() as conn:
        req = conn.execute("SELECT * FROM manager_requests WHERE id = ?", (request_id,)).fetchone()
        if not req:
            raise ApiError("Request not found", 404)
        if req["manager_id"] != user["id"]:
            raise ApiError("Only the addressed manager can acknowledge this request", 403)
        conn.execute("UPDATE manager_requests SET status = 'acknowledged' WHERE id = ?", (request_id,))
        audit_event(conn, user, "match.tl_support_acknowledged", "opportunity", req["opportunity_id"], human_approved=True)
        refreshed = conn.execute("SELECT * FROM manager_requests WHERE id = ?", (request_id,)).fetchone()
        return jsonify(refreshed)
