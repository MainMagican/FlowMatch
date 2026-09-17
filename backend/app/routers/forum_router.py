"""Open Questions Forum (this session's feature request #2): anyone can ask
a question like "who in the CEPOS team can give me an API key?" and the
system scans colleagues' team membership, skills, and workflow systems
mentioned in the text to suggest who is likely able to help."""

import json
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from app.auth import get_current_user
from app.database import db_session
from app.errors import ApiError
from app.services.audit_service import audit_event
from app.services.forum_suggestion_service import suggest_people_for_question

bp = Blueprint("forum", __name__, url_prefix="/api/forum")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _with_author(conn, row):
    row["author"] = conn.execute(
        "SELECT id, name, avatar_emoji, role_title FROM users WHERE id = ?", (row["author_id"],)
    ).fetchone()
    return row


@bp.get("/questions")
def list_questions():
    get_current_user()
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM forum_questions ORDER BY id DESC").fetchall()
        result = []
        for r in rows:
            entry = _with_author(conn, r)
            entry["answer_count"] = conn.execute(
                "SELECT COUNT(*) as c FROM forum_answers WHERE question_id = ?", (r["id"],)
            ).fetchone()["c"]
            entry["suggested_count"] = conn.execute(
                "SELECT COUNT(*) as c FROM forum_question_suggestions WHERE question_id = ?", (r["id"],)
            ).fetchone()["c"]
            result.append(entry)
        return jsonify(result)


@bp.post("/questions")
def create_question():
    """Ask a question. The system immediately (and transparently) scans for
    colleagues who might know the answer, based on team/skill/system
    mentions in the text - see forum_suggestion_service."""
    user = get_current_user()
    body = request.get_json(force=True) or {}
    title = (body.get("title") or "").strip()
    if not title:
        raise ApiError("A question title is required.", 400)
    with db_session() as conn:
        cur = conn.execute(
            """INSERT INTO forum_questions (title, body, author_id, status, created_at)
               VALUES (?, ?, ?, 'open', ?)""",
            (title, body.get("body"), user["id"], _now()),
        )
        question_id = cur.lastrowid
        audit_event(conn, user, "forum.question_asked", "forum_question", question_id, ai_involved=True)

        suggestions = suggest_people_for_question(conn, title, body.get("body"))
        for s in suggestions:
            if s["user_id"] == user["id"]:
                continue  # never suggest the asker to themselves
            conn.execute(
                """INSERT INTO forum_question_suggestions (question_id, user_id, reasons, created_at)
                   VALUES (?, ?, ?, ?)""",
                (question_id, s["user_id"], json.dumps(s["reasons"]), _now()),
            )

        question = conn.execute("SELECT * FROM forum_questions WHERE id = ?", (question_id,)).fetchone()
        return jsonify(_with_author(conn, question)), 201


@bp.get("/questions/<int:question_id>")
def get_question(question_id):
    get_current_user()
    with db_session() as conn:
        question = conn.execute("SELECT * FROM forum_questions WHERE id = ?", (question_id,)).fetchone()
        if not question:
            raise ApiError("Question not found", 404)
        entry = _with_author(conn, question)

        answers = conn.execute(
            "SELECT * FROM forum_answers WHERE question_id = ? ORDER BY id", (question_id,)
        ).fetchall()
        for a in answers:
            a["user"] = conn.execute(
                "SELECT id, name, avatar_emoji, role_title FROM users WHERE id = ?", (a["user_id"],)
            ).fetchone()
        entry["answers"] = answers

        suggestions = conn.execute(
            "SELECT * FROM forum_question_suggestions WHERE question_id = ? ORDER BY id", (question_id,)
        ).fetchall()
        for s in suggestions:
            s["reasons"] = json.loads(s["reasons"] or "[]")
            s["user"] = conn.execute(
                "SELECT id, name, avatar_emoji, role_title, department_id FROM users WHERE id = ?",
                (s["user_id"],),
            ).fetchone()
            if s["user"] and s["user"].get("department_id"):
                dept = conn.execute(
                    "SELECT name FROM departments WHERE id = ?", (s["user"]["department_id"],)
                ).fetchone()
                s["user"]["department_name"] = dept["name"] if dept else None
        entry["suggestions"] = suggestions
        return jsonify(entry)


@bp.post("/questions/<int:question_id>/answers")
def add_answer(question_id):
    user = get_current_user()
    body = request.get_json(force=True) or {}
    text = (body.get("body") or "").strip()
    if not text:
        raise ApiError("Answer body is required.", 400)
    with db_session() as conn:
        question = conn.execute("SELECT * FROM forum_questions WHERE id = ?", (question_id,)).fetchone()
        if not question:
            raise ApiError("Question not found", 404)
        cur = conn.execute(
            """INSERT INTO forum_answers (question_id, user_id, body, created_at)
               VALUES (?, ?, ?, ?)""",
            (question_id, user["id"], text, _now()),
        )
        conn.execute("UPDATE forum_questions SET status = 'answered' WHERE id = ?", (question_id,))
        audit_event(conn, user, "forum.answer_posted", "forum_answer", cur.lastrowid)
        answer = conn.execute("SELECT * FROM forum_answers WHERE id = ?", (cur.lastrowid,)).fetchone()
        answer["user"] = conn.execute(
            "SELECT id, name, avatar_emoji, role_title FROM users WHERE id = ?", (user["id"],)
        ).fetchone()
        return jsonify(answer), 201


@bp.post("/questions/<int:question_id>/close")
def close_question(question_id):
    user = get_current_user()
    with db_session() as conn:
        question = conn.execute("SELECT * FROM forum_questions WHERE id = ?", (question_id,)).fetchone()
        if not question:
            raise ApiError("Question not found", 404)
        if question["author_id"] != user["id"] and "administrator" not in user["roles"]:
            raise ApiError("Only the asker can close this question.", 403)
        conn.execute("UPDATE forum_questions SET status = 'closed' WHERE id = ?", (question_id,))
        audit_event(conn, user, "forum.question_closed", "forum_question", question_id)
        refreshed = conn.execute("SELECT * FROM forum_questions WHERE id = ?", (question_id,)).fetchone()
        return jsonify(_with_author(conn, refreshed))
