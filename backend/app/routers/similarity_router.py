from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from app.auth import get_current_user
from app.database import db_session
from app.errors import ApiError
from app.services.audit_service import audit_event
from app.services.workflow_similarity_service import WorkflowSimilarityService

bp = Blueprint("similarity", __name__, url_prefix="/api/similarity")

similarity_service = WorkflowSimilarityService()


def _now():
    return datetime.now(timezone.utc).isoformat()


@bp.post("/compare")
def compare_stages():
    """Compare two published stages and, if an asset exists on either side,
    surface a reuse recommendation (design.md FR21-22)."""
    user = get_current_user()
    body = request.get_json(force=True) or {}
    stage_a_id = body.get("stage_a_id")
    stage_b_id = body.get("stage_b_id")
    with db_session() as conn:
        stage_a = conn.execute("SELECT * FROM workflow_stages WHERE id = ?", (stage_a_id,)).fetchone()
        stage_b = conn.execute("SELECT * FROM workflow_stages WHERE id = ?", (stage_b_id,)).fetchone()
        if not stage_a or not stage_b:
            raise ApiError("Both stages must exist", 404)

        workflow_a = conn.execute("SELECT * FROM workflows WHERE id = ?", (stage_a["workflow_id"],)).fetchone()
        workflow_b = conn.execute("SELECT * FROM workflows WHERE id = ?", (stage_b["workflow_id"],)).fetchone()
        for wf in (workflow_a, workflow_b):
            if wf["validation_status"] not in ("validated", "published"):
                raise ApiError("Both workflows must be validated/published to compare", 400)

        result = similarity_service.compare_stages(stage_a, stage_b)

        assets_a = conn.execute("SELECT * FROM reusable_assets WHERE workflow_id = ?", (workflow_a["id"],)).fetchall()
        assets_b = conn.execute("SELECT * FROM reusable_assets WHERE workflow_id = ?", (workflow_b["id"],)).fetchall()
        reuse_candidates = assets_a + assets_b

        cur = conn.execute(
            """INSERT INTO workflow_similarities
               (stage_a_id, stage_b_id, shared_characteristics, differences, confidence,
                requires_owner_confirmation, recommendation, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                stage_a_id, stage_b_id, ", ".join(result["shared_characteristics"]),
                ", ".join(result["differences"]), result["confidence"], 1,
                result["recommendation"], _now(),
            ),
        )
        similarity_id = cur.lastrowid
        audit_event(conn, user, "similarity.compared", "workflow_similarity", similarity_id, ai_involved=True)

        return jsonify({
            "id": similarity_id,
            "stage_a": stage_a,
            "stage_b": stage_b,
            **result,
            "reusable_assets_found": reuse_candidates,
            "reuse_recommendations": (
                ["Review existing solution", "Contact the solution owner", "Arrange a coaching session",
                 "Create an automation-transfer opportunity"]
                if reuse_candidates else []
            ),
        })


@bp.get("")
def list_similarities():
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM workflow_similarities ORDER BY id").fetchall()
        return jsonify(rows)


@bp.get("/auto-scan")
def auto_scan():
    """AI-assisted sweep across every validated/published workflow's stages,
    flagging pairs (especially cross-department ones) that look similar so
    departments can discover overlapping/duplicated work without knowing any
    stage IDs up front (design.md FR21-22). Deterministic heuristic, not a
    real ML model (docs/DECISIONS.md #4) - always requires owner confirmation.
    """
    user = get_current_user()
    with db_session() as conn:
        stages = conn.execute(
            """SELECT ws.*, w.name AS workflow_name, w.department_id, w.pod_id,
                      d.name AS department_name, p.name AS pod_name
               FROM workflow_stages ws
               JOIN workflows w ON w.id = ws.workflow_id
               LEFT JOIN departments d ON d.id = w.department_id
               LEFT JOIN pods p ON p.id = w.pod_id
               WHERE w.validation_status IN ('validated', 'published')
               ORDER BY ws.id"""
        ).fetchall()

        existing = conn.execute(
            "SELECT stage_a_id, stage_b_id FROM workflow_similarities"
        ).fetchall()
        already_recorded = {frozenset((r["stage_a_id"], r["stage_b_id"])) for r in existing}

        matches = []
        for i in range(len(stages)):
            for j in range(i + 1, len(stages)):
                stage_a, stage_b = stages[i], stages[j]
                if stage_a["workflow_id"] == stage_b["workflow_id"]:
                    continue  # only interested in cross-workflow overlap
                result = similarity_service.compare_stages(stage_a, stage_b)
                if result["confidence"] == "low":
                    continue
                cross_department = stage_a["department_id"] != stage_b["department_id"]
                pair_key = frozenset((stage_a["id"], stage_b["id"]))
                if pair_key not in already_recorded:
                    cur = conn.execute(
                        """INSERT INTO workflow_similarities
                           (stage_a_id, stage_b_id, shared_characteristics, differences, confidence,
                            requires_owner_confirmation, recommendation, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            stage_a["id"], stage_b["id"], ", ".join(result["shared_characteristics"]),
                            ", ".join(result["differences"]), result["confidence"], 1,
                            result["recommendation"], _now(),
                        ),
                    )
                    already_recorded.add(pair_key)
                    audit_event(conn, user, "similarity.auto_flagged", "workflow_similarity", cur.lastrowid, ai_involved=True)

                matches.append({
                    "stage_a": {
                        "id": stage_a["id"], "name": stage_a["name"],
                        "workflow_id": stage_a["workflow_id"], "workflow_name": stage_a["workflow_name"],
                        "department_name": stage_a["department_name"], "pod_name": stage_a["pod_name"],
                    },
                    "stage_b": {
                        "id": stage_b["id"], "name": stage_b["name"],
                        "workflow_id": stage_b["workflow_id"], "workflow_name": stage_b["workflow_name"],
                        "department_name": stage_b["department_name"], "pod_name": stage_b["pod_name"],
                    },
                    "confidence": result["confidence"],
                    "match_percentage": result["match_percentage"],
                    "explanation": result["explanation"],
                    "cross_department": cross_department,
                    "shared_characteristics": result["shared_characteristics"],
                    "recommendation": result["recommendation"],
                })

        rank = {"medium-high": 0, "low-medium": 1}
        matches.sort(key=lambda m: (rank.get(m["confidence"], 2), not m["cross_department"]))

        return jsonify({
            "scanned_stages": len(stages),
            "matches_found": len(matches),
            "cross_department_matches": sum(1 for m in matches if m["cross_department"]),
            "matches": matches,
        })
