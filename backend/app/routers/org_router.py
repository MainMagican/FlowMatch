from flask import Blueprint, jsonify

from app.auth import get_current_user
from app.database import db_session

bp = Blueprint("org", __name__, url_prefix="/api/org")


@bp.get("/departments")
def list_departments():
    with db_session() as conn:
        departments = conn.execute("SELECT * FROM departments ORDER BY id").fetchall()
        for d in departments:
            pods = conn.execute(
                "SELECT * FROM pods WHERE department_id = ? ORDER BY id", (d["id"],)
            ).fetchall()
            for p in pods:
                if p["lead_user_id"]:
                    p["lead"] = conn.execute(
                        "SELECT id, name, avatar_emoji, role_title FROM users WHERE id = ?",
                        (p["lead_user_id"],),
                    ).fetchone()
                else:
                    p["lead"] = None
            d["pods"] = pods
    return jsonify(departments)


@bp.get("/pods/<int:pod_id>/members")
def pod_members(pod_id):
    with db_session() as conn:
        members = conn.execute(
            "SELECT id, name, avatar_emoji, role_title FROM users WHERE pod_id = ? ORDER BY id",
            (pod_id,),
        ).fetchall()
    return jsonify(members)


def _org_tree_for(conn, subject, viewer_id):
    """Build the org-tree payload (manager, colleagues, direct reports, dept
    workflows) centered on `subject` (a users row), reusable for both 'my
    org' and 'click any person to see their team' lookups."""
    department = None
    pod = None
    manager = None
    colleagues = []

    if subject["department_id"]:
        department = conn.execute(
            "SELECT * FROM departments WHERE id = ?", (subject["department_id"],)
        ).fetchone()
    if subject["pod_id"]:
        pod = conn.execute("SELECT * FROM pods WHERE id = ?", (subject["pod_id"],)).fetchone()

    manager_id = subject["manager_id"] or (pod["lead_user_id"] if pod and pod["lead_user_id"] != subject["id"] else None)
    if manager_id:
        manager = conn.execute(
            "SELECT id, name, avatar_emoji, role_title FROM users WHERE id = ?", (manager_id,)
        ).fetchone()
        colleagues = conn.execute(
            "SELECT id, name, avatar_emoji, role_title FROM users WHERE manager_id = ? AND id != ? ORDER BY name",
            (manager_id, subject["id"]),
        ).fetchall()
    elif pod:
        colleagues = conn.execute(
            "SELECT id, name, avatar_emoji, role_title FROM users WHERE pod_id = ? AND id != ? ORDER BY name",
            (subject["pod_id"], subject["id"]),
        ).fetchall()

    direct_reports = conn.execute(
        "SELECT id, name, avatar_emoji, role_title FROM users WHERE manager_id = ? ORDER BY name",
        (subject["id"],),
    ).fetchall()

    department_workflows = []
    if subject["department_id"]:
        department_workflows = conn.execute(
            "SELECT id, name, validation_status, business_purpose FROM workflows WHERE department_id = ? ORDER BY id",
            (subject["department_id"],),
        ).fetchall()

    return {
        "subject": {
            "id": subject["id"], "name": subject["name"],
            "avatar_emoji": subject["avatar_emoji"], "role_title": subject["role_title"],
        },
        "is_self": subject["id"] == viewer_id,
        "department": department,
        "pod": pod,
        "is_pod_lead": bool(pod and pod["lead_user_id"] == subject["id"]),
        "manager": manager,
        "colleagues": colleagues,
        "direct_reports": direct_reports,
        "department_workflows": department_workflows,
    }


@bp.get("/me")
def my_org():
    """Org tree centered on the current user: their manager (real reporting
    line via manager_id, falling back to the pod lead), colleagues who share
    that manager, direct reports, and the workflows owned by their department
    - so 'who is my boss / team / dept workflows' is answerable in one call."""
    user = get_current_user()
    with db_session() as conn:
        return jsonify(_org_tree_for(conn, user, user["id"]))


@bp.get("/user/<int:user_id>")
def org_for_user(user_id):
    """Same org-tree shape as /me but centered on any other employee, so
    clicking a person's card in the tree ('their manager', 'a colleague',
    'a direct report', or a node in the full company tree) shows that
    person's own team and department instead."""
    viewer = get_current_user()
    with db_session() as conn:
        subject = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not subject:
            return jsonify({"error": "User not found"}), 404
        return jsonify(_org_tree_for(conn, subject, viewer["id"]))


@bp.get("/ai-readiness-summary")
def ai_readiness_summary():
    """Company-wide AI readiness self-evaluation benchmark (0-10 scale) used
    to draw the slim vertical benchmarker on the org tab."""
    user = get_current_user()
    with db_session() as conn:
        rows = conn.execute(
            "SELECT ai_readiness_score FROM user_preferences WHERE ai_readiness_score IS NOT NULL"
        ).fetchall()
        scores = [r["ai_readiness_score"] for r in rows]
        total_employees = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        my_pref = conn.execute(
            "SELECT ai_readiness_score FROM user_preferences WHERE user_id = ?", (user["id"],)
        ).fetchone()
        average = round(sum(scores) / len(scores), 1) if scores else None
        return jsonify({
            "average": average,
            "respondents": len(scores),
            "total_employees": total_employees,
            "my_score": my_pref["ai_readiness_score"] if my_pref else None,
        })


@bp.get("/tree")
def company_tree():
    """Full company org chart, rooted at whoever has no manager (the CEO),
    nested recursively. ~250+ nodes but a single lightweight query set - the
    frontend renders it as a collapsible tree (design.md section 6)."""
    with db_session() as conn:
        rows = conn.execute(
            "SELECT id, name, avatar_emoji, role_title, department_id, manager_id FROM users ORDER BY id"
        ).fetchall()
        dept_names = {
            d["id"]: d["name"] for d in conn.execute("SELECT id, name FROM departments").fetchall()
        }
        by_manager = {}
        nodes = {}
        for r in rows:
            node = {
                "id": r["id"], "name": r["name"], "avatar_emoji": r["avatar_emoji"],
                "role_title": r["role_title"],
                "department": dept_names.get(r["department_id"]),
                "children": [],
            }
            nodes[r["id"]] = node
            by_manager.setdefault(r["manager_id"], []).append(r["id"])

        def build(user_id):
            node = nodes[user_id]
            node["children"] = [build(child_id) for child_id in by_manager.get(user_id, [])]
            return node

        roots = [build(uid) for uid in by_manager.get(None, [])]
        return jsonify({"roots": roots, "total_employees": len(rows)})
