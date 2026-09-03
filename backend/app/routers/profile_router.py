import json

from flask import Blueprint, jsonify, request

from app.auth import get_current_user
from app.database import db_session
from app.errors import ApiError

bp = Blueprint("profile", __name__, url_prefix="/api/profile")

AI_BANDS = ["Explorer", "Practitioner", "Builder", "Enabler"]
PROFICIENCIES = ["Awareness", "Working knowledge", "Independent", "Advanced", "Coach"]
GOAL_TYPES = ["learn", "practise", "master"]


def _serialize_profile(conn, user):
    skills = conn.execute(
        """SELECT s.name, us.proficiency, us.evidence FROM user_skills us
           JOIN skills s ON s.id = us.skill_id WHERE us.user_id = ?""",
        (user["id"],),
    ).fetchall()
    goals = conn.execute(
        """SELECT s.name, lg.goal_type FROM learning_goals lg
           JOIN skills s ON s.id = lg.skill_id WHERE lg.user_id = ?""",
        (user["id"],),
    ).fetchall()
    prefs = conn.execute(
        "SELECT * FROM user_preferences WHERE user_id = ?", (user["id"],)
    ).fetchone()
    if not prefs:
        prefs = {
            "opportunity_types": "[]",
            "declared_availability": "Unspecified",
            "ai_support_band": "Explorer",
            "visibility": "visible_to_org",
            "opted_into_discovery": 1,
            "ai_readiness_score": None,
        }
    department_name = None
    if user["department_id"]:
        dept = conn.execute(
            "SELECT name FROM departments WHERE id = ?", (user["department_id"],)
        ).fetchone()
        department_name = dept["name"] if dept else None
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "role_title": user["role_title"],
        "avatar_emoji": user["avatar_emoji"],
        "department_id": user["department_id"],
        "department_name": department_name,
        "skills": skills,
        "learning_goals": goals,
        "opportunity_types": json.loads(prefs["opportunity_types"]),
        "declared_availability": prefs["declared_availability"],
        "ai_support_band": prefs["ai_support_band"],
        "visibility": prefs["visibility"],
        "opted_into_discovery": bool(prefs["opted_into_discovery"]),
        "ai_readiness_score": prefs["ai_readiness_score"],
        "completed_trainings": json.loads(user["completed_trainings"]),
        "granted_access": json.loads(user["granted_access"]),
    }


@bp.get("/me")
def get_my_profile():
    user = get_current_user()
    with db_session() as conn:
        return jsonify(_serialize_profile(conn, user))


@bp.put("/me")
def update_my_profile():
    user = get_current_user()
    body = request.get_json(force=True) or {}
    with db_session() as conn:
        if "skills" in body:
            conn.execute("DELETE FROM user_skills WHERE user_id = ?", (user["id"],))
            for entry in body["skills"]:
                name = entry["name"].strip()
                proficiency = entry.get("proficiency", "Awareness")
                if proficiency not in PROFICIENCIES:
                    raise ApiError("Invalid proficiency: {}".format(proficiency), 400)
                skill_row = conn.execute("SELECT id FROM skills WHERE name = ?", (name,)).fetchone()
                if not skill_row:
                    conn.execute("INSERT INTO skills (name, is_custom) VALUES (?, 1)", (name,))
                    skill_id = conn.execute("SELECT id FROM skills WHERE name = ?", (name,)).fetchone()["id"]
                else:
                    skill_id = skill_row["id"]
                conn.execute(
                    "INSERT INTO user_skills (user_id, skill_id, proficiency, evidence) VALUES (?, ?, ?, ?)",
                    (user["id"], skill_id, proficiency, entry.get("evidence")),
                )
        if "learning_goals" in body:
            conn.execute("DELETE FROM learning_goals WHERE user_id = ?", (user["id"],))
            for entry in body["learning_goals"]:
                name = entry["name"].strip()
                goal_type = entry.get("goal_type", "learn")
                if goal_type not in GOAL_TYPES:
                    raise ApiError("Invalid goal_type: {}".format(goal_type), 400)
                skill_row = conn.execute("SELECT id FROM skills WHERE name = ?", (name,)).fetchone()
                if not skill_row:
                    conn.execute("INSERT INTO skills (name, is_custom) VALUES (?, 1)", (name,))
                    skill_id = conn.execute("SELECT id FROM skills WHERE name = ?", (name,)).fetchone()["id"]
                else:
                    skill_id = skill_row["id"]
                conn.execute(
                    "INSERT INTO learning_goals (user_id, skill_id, goal_type) VALUES (?, ?, ?)",
                    (user["id"], skill_id, goal_type),
                )
        ai_band = body.get("ai_support_band")
        if ai_band and ai_band not in AI_BANDS:
            raise ApiError("Invalid ai_support_band: {}".format(ai_band), 400)
        ai_readiness_score = body.get("ai_readiness_score")
        if ai_readiness_score is not None:
            try:
                ai_readiness_score = int(ai_readiness_score)
            except (TypeError, ValueError):
                raise ApiError("ai_readiness_score must be an integer 0-10", 400)
            if not (0 <= ai_readiness_score <= 10):
                raise ApiError("ai_readiness_score must be between 0 and 10", 400)
        conn.execute(
            """INSERT INTO user_preferences (user_id, opportunity_types, declared_availability,
                   ai_support_band, visibility, opted_into_discovery, ai_readiness_score)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                   opportunity_types = excluded.opportunity_types,
                   declared_availability = excluded.declared_availability,
                   ai_support_band = excluded.ai_support_band,
                   visibility = excluded.visibility,
                   opted_into_discovery = excluded.opted_into_discovery,
                   ai_readiness_score = COALESCE(excluded.ai_readiness_score, user_preferences.ai_readiness_score)
            """,
            (
                user["id"],
                json.dumps(body.get("opportunity_types", [])),
                body.get("declared_availability", "Unspecified"),
                ai_band or "Explorer",
                body.get("visibility", "visible_to_org"),
                1 if body.get("opted_into_discovery", True) else 0,
                ai_readiness_score,
            ),
        )
        refreshed = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
        return jsonify(_serialize_profile(conn, refreshed))


@bp.get("/skills-catalogue")
def skills_catalogue():
    with db_session() as conn:
        skills = conn.execute("SELECT name, is_custom FROM skills ORDER BY name").fetchall()
    return jsonify(skills)


@bp.get("/skills-overview")
def skills_overview():
    """Company-wide snapshot of skills people already have vs. what they want
    to learn - lets anyone browsing opportunities see the talent pool and the
    demand for growth at a glance (design.md: skills/learning-goal discovery)."""
    with db_session() as conn:
        available = conn.execute(
            """SELECT s.name, COUNT(*) as people_count,
                      SUM(CASE WHEN us.proficiency IN ('Advanced', 'Coach') THEN 1 ELSE 0 END) as expert_count
               FROM user_skills us
               JOIN skills s ON s.id = us.skill_id
               GROUP BY s.id
               ORDER BY people_count DESC, s.name
               LIMIT 25"""
        ).fetchall()
        wanted = conn.execute(
            """SELECT s.name, COUNT(*) as people_count
               FROM learning_goals lg
               JOIN skills s ON s.id = lg.skill_id
               GROUP BY s.id
               ORDER BY people_count DESC, s.name
               LIMIT 25"""
        ).fetchall()
        totals = conn.execute(
            """SELECT (SELECT COUNT(DISTINCT user_id) FROM user_skills) as people_with_skills,
                      (SELECT COUNT(DISTINCT user_id) FROM learning_goals) as people_with_goals,
                      (SELECT COUNT(*) FROM users) as total_people"""
        ).fetchone()
        return jsonify({
            "available_skills": available,
            "wanted_skills": wanted,
            "totals": totals,
        })
