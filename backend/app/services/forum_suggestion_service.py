"""Transparent, rules-based "who might know this" suggestion engine for the
Open Questions Forum (this session's feature request #2).

Same explainability principle as matching_service/match_explanation_service:
every suggested person comes with plain-language reasons, never a bare
opaque score. Deterministic substring matching - not a call to an external
LLM (docs/DECISIONS.md #4).
"""


def suggest_people_for_question(conn, title, body):
    """Scan departments/pods, skills, and workflow systems mentioned in the
    question text, and return a ranked list of
    [{user_id, reasons: [str, ...]}], most-matched first."""
    text = "{} {}".format(title or "", body or "").lower()
    reasons_by_user = {}

    def add_reason(user_id, reason):
        if not user_id:
            return
        reasons_by_user.setdefault(user_id, []).append(reason)

    # 1. Team/department or pod mentioned by name (e.g. "who in the CEPOS
    # team can...") -> everyone in that team is a plausible person to ask.
    departments = conn.execute("SELECT id, name FROM departments").fetchall()
    for dept in departments:
        name = (dept["name"] or "").strip()
        if name and name.lower() in text:
            members = conn.execute(
                "SELECT id FROM users WHERE department_id = ?", (dept["id"],)
            ).fetchall()
            for m in members:
                add_reason(m["id"], "Works in the '{}' team, mentioned in the question".format(name))

    pods = conn.execute("SELECT id, name FROM pods").fetchall()
    for pod in pods:
        name = (pod["name"] or "").strip()
        if name and name.lower() in text:
            members = conn.execute(
                "SELECT id FROM users WHERE pod_id = ?", (pod["id"],)
            ).fetchall()
            for m in members:
                add_reason(m["id"], "Works in the '{}' pod, mentioned in the question".format(name))

    # 2. A skill/tool name mentioned (e.g. "API key", "Power Automate") ->
    # people who list that skill, ranked by how many matched skills they hold.
    skills = conn.execute("SELECT id, name FROM skills").fetchall()
    for skill in skills:
        name = (skill["name"] or "").strip()
        if name and name.lower() in text:
            holders = conn.execute(
                "SELECT user_id, proficiency FROM user_skills WHERE skill_id = ?", (skill["id"],)
            ).fetchall()
            for h in holders:
                add_reason(
                    h["user_id"],
                    "Has the '{}' skill ({}), mentioned in the question".format(name, h["proficiency"]),
                )

    # 3. A system/tool named in a workflow step (e.g. "Reporting system",
    # "Power Automate") -> that workflow's owner is a likely contact.
    stage_rows = conn.execute(
        """SELECT ws.systems, w.owner_id, w.name as workflow_name
           FROM workflow_stages ws JOIN workflows w ON w.id = ws.workflow_id
           WHERE ws.systems IS NOT NULL AND ws.systems != ''"""
    ).fetchall()
    for row in stage_rows:
        systems = (row["systems"] or "").strip()
        if systems and systems.lower() in text and row["owner_id"]:
            add_reason(
                row["owner_id"],
                "Owns the '{}' workflow, which uses '{}'".format(row["workflow_name"], systems),
            )

    ranked = sorted(reasons_by_user.items(), key=lambda kv: len(kv[1]), reverse=True)
    return [{"user_id": user_id, "reasons": reasons} for user_id, reasons in ranked[:5]]
