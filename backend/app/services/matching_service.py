"""Transparent, rules-based relevance scoring (design.md FR17, spec section 20.4).

Each relevance component is computed and returned separately - never
collapsed into a single opaque score shown to the user. If an internal
numeric total is needed for sorting, it is only ever used server-side to
order recommendations, and is never presented as an employee quality/
performance measure (design.md FR19).
"""

import json


def compute_relevance_components(conn, opportunity, user):
    """Return a list of {component_name, detail, matched} dicts."""
    components = []

    required_skills = set(json.loads(opportunity.get("required_skills") or "[]"))
    learnable_skills = set(json.loads(opportunity.get("learnable_skills") or "[]"))

    user_skill_rows = conn.execute(
        """SELECT s.name FROM user_skills us JOIN skills s ON s.id = us.skill_id
           WHERE us.user_id = ?""",
        (user["id"],),
    ).fetchall()
    user_skills = {r["name"] for r in user_skill_rows}

    goal_rows = conn.execute(
        """SELECT s.name FROM learning_goals lg JOIN skills s ON s.id = lg.skill_id
           WHERE lg.user_id = ?""",
        (user["id"],),
    ).fetchall()
    user_goals = {r["name"] for r in goal_rows}

    skill_overlap = required_skills & user_skills
    components.append({
        "component_name": "existing_skill_overlap",
        "detail": "Existing skills matching what's required: {}".format(", ".join(sorted(skill_overlap)) or "none"),
        "matched": bool(skill_overlap),
    })

    goal_overlap = learnable_skills & user_goals
    components.append({
        "component_name": "learning_goal_overlap",
        "detail": "Learning goals matching what this opportunity teaches: {}".format(", ".join(sorted(goal_overlap)) or "none"),
        "matched": bool(goal_overlap),
    })

    prefs = conn.execute("SELECT * FROM user_preferences WHERE user_id = ?", (user["id"],)).fetchone()
    preferred_types = json.loads(prefs["opportunity_types"]) if prefs else []
    type_match = opportunity["opportunity_type"] in preferred_types
    components.append({
        "component_name": "opportunity_type_preference",
        "detail": "Opportunity type '{}' is {} the user's declared preferences.".format(
            opportunity["opportunity_type"], "in" if type_match else "not in"
        ),
        "matched": type_match,
    })

    availability = prefs["declared_availability"] if prefs else "Unspecified"
    availability_ok = availability not in (None, "Unspecified", "None")
    components.append({
        "component_name": "availability_compatibility",
        "detail": "Declared availability: {}".format(availability),
        "matched": availability_ok,
    })

    return components


def internal_sort_score(components):
    """Server-side-only ordering aid. Never exposed as an employee score."""
    return sum(1 for c in components if c["matched"])
