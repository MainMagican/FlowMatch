"""Case Studies (this session's feature request #1): people share what
they automated so colleagues can see what AI/automation can do for them,
then "ping" the author to ask for help setting up something similar."""

import json
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from app.auth import get_current_user
from app.database import db_session
from app.errors import ApiError
from app.services.audit_service import audit_event

bp = Blueprint("case_studies", __name__, url_prefix="/api/case-studies")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _serialize(row):
    row["tools_used"] = json.loads(row["tools_used"] or "[]")
    return row


def _with_author(conn, row):
    row["author"] = conn.execute(
        "SELECT id, name, avatar_emoji, role_title FROM users WHERE id = ?", (row["author_id"],)
    ).fetchone()
    if row.get("department_id"):
        dept = conn.execute("SELECT name FROM departments WHERE id = ?", (row["department_id"],)).fetchone()
        row["department_name"] = dept["name"] if dept else None
    if row.get("workflow_id"):
        wf = conn.execute("SELECT name FROM workflows WHERE id = ?", (row["workflow_id"],)).fetchone()
        row["workflow_name"] = wf["name"] if wf else None
    return row


@bp.get("")
def list_case_studies():
    get_current_user()  # any signed-in user can browse case studies
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM case_studies ORDER BY id DESC").fetchall()
        return jsonify([_with_author(conn, _serialize(r)) for r in rows])


@bp.post("")
def create_case_study():
    user = get_current_user()
    body = request.get_json(force=True) or {}
    title = (body.get("title") or "").strip()
    what_automated = (body.get("what_automated") or "").strip()
    if not title or not what_automated:
        raise ApiError("Title and a description of what was automated are required.", 400)
    with db_session() as conn:
        cur = conn.execute(
            """INSERT INTO case_studies
               (title, author_id, department_id, workflow_id, what_automated, tools_used,
                impact, ai_involved, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                title, user["id"], user.get("department_id"), body.get("workflow_id"),
                what_automated, json.dumps(body.get("tools_used", [])), body.get("impact"),
                1 if body.get("ai_involved", True) else 0, _now(),
            ),
        )
        case_id = cur.lastrowid
        audit_event(conn, user, "case_study.created", "case_study", case_id, ai_involved=bool(body.get("ai_involved", True)))
        row = conn.execute("SELECT * FROM case_studies WHERE id = ?", (case_id,)).fetchone()
        return jsonify(_with_author(conn, _serialize(row))), 201


@bp.get("/<int:case_id>")
def get_case_study(case_id):
    user = get_current_user()
    with db_session() as conn:
        row = conn.execute("SELECT * FROM case_studies WHERE id = ?", (case_id,)).fetchone()
        if not row:
            raise ApiError("Case study not found", 404)
        entry = _with_author(conn, _serialize(row))
        if row["author_id"] == user["id"]:
            # Only the author sees who has pinged them, and their contact details.
            pings = conn.execute(
                "SELECT * FROM case_study_pings WHERE case_study_id = ? ORDER BY id DESC", (case_id,)
            ).fetchall()
            for p in pings:
                p["requester"] = conn.execute(
                    "SELECT id, name, avatar_emoji, role_title, email FROM users WHERE id = ?",
                    (p["requester_id"],),
                ).fetchone()
            entry["pings"] = pings
        return jsonify(entry)


@bp.post("/<int:case_id>/ping")
def ping_case_study(case_id):
    """A reader asks the author for help setting up the same/similar
    automation - a lightweight request, not a full opportunity draft."""
    user = get_current_user()
    body = request.get_json(force=True) or {}
    with db_session() as conn:
        case = conn.execute("SELECT * FROM case_studies WHERE id = ?", (case_id,)).fetchone()
        if not case:
            raise ApiError("Case study not found", 404)
        if case["author_id"] == user["id"]:
            raise ApiError("You can't ping your own case study.", 400)
        cur = conn.execute(
            """INSERT INTO case_study_pings (case_study_id, requester_id, note, status, created_at)
               VALUES (?, ?, ?, 'pending', ?)""",
            (case_id, user["id"], body.get("note"), _now()),
        )
        audit_event(conn, user, "case_study.pinged", "case_study", case_id)
        ping = conn.execute("SELECT * FROM case_study_pings WHERE id = ?", (cur.lastrowid,)).fetchone()
        return jsonify(ping), 201


@bp.post("/<int:case_id>/pings/<int:ping_id>/acknowledge")
def acknowledge_ping(case_id, ping_id):
    user = get_current_user()
    with db_session() as conn:
        case = conn.execute("SELECT * FROM case_studies WHERE id = ?", (case_id,)).fetchone()
        if not case:
            raise ApiError("Case study not found", 404)
        if case["author_id"] != user["id"]:
            raise ApiError("Only the case study author can acknowledge a ping.", 403)
        conn.execute("UPDATE case_study_pings SET status = 'acknowledged' WHERE id = ? AND case_study_id = ?", (ping_id, case_id))
        audit_event(conn, user, "case_study.ping_acknowledged", "case_study_ping", ping_id)
        ping = conn.execute("SELECT * FROM case_study_pings WHERE id = ?", (ping_id,)).fetchone()
        if not ping:
            raise ApiError("Ping not found", 404)
        return jsonify(ping)


@bp.get("/my/pings-sent")
def my_pings_sent():
    """Pings the current user has sent out, so they can track what they're
    waiting on a reply for."""
    user = get_current_user()
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM case_study_pings WHERE requester_id = ? ORDER BY id DESC", (user["id"],)
        ).fetchall()
        for r in rows:
            r["case_study"] = conn.execute(
                "SELECT id, title FROM case_studies WHERE id = ?", (r["case_study_id"],)
            ).fetchone()
        return jsonify(rows)
