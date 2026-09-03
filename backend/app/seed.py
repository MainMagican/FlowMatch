"""Synthetic demo seed data implementing the spec section 19 scenario:
Customer Operations <-> Business Improvement, one blocked publish, one
blocked match (docs/DECISIONS.md #5).

Run directly: `python -m app.seed` (also invoked automatically by main.py
via init_db(), but seeding is idempotent-guarded by checking if data exists).
"""

import json
from datetime import datetime, timezone

from app.database import db_session, init_db

SKILL_CATALOGUE = [
    "Excel", "Advanced Excel", "SQL", "Python", "Data analysis", "Process mapping",
    "Business analysis", "Requirements writing", "Testing", "Quality assurance",
    "Prompt engineering", "Copilot usage", "Agent design", "Automation design",
    "Power Automate", "Power Apps", "Documentation", "Facilitation",
    "Change management", "Workflow optimization", "Data visualization",
]


def _now():
    return datetime.now(timezone.utc).isoformat()


def already_seeded(conn):
    row = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()
    return row["c"] > 0


def seed():
    init_db()
    with db_session() as conn:
        if already_seeded(conn):
            return

        for name in SKILL_CATALOGUE:
            conn.execute("INSERT OR IGNORE INTO skills (name, is_custom) VALUES (?, 0)", (name,))

        def skill_id(name):
            return conn.execute("SELECT id FROM skills WHERE name = ?", (name,)).fetchone()["id"]

        dept_customer_ops = conn.execute(
            "INSERT INTO departments (name, description) VALUES (?, ?)",
            ("Customer Operations", "Handles customer-facing operational processes."),
        ).lastrowid
        dept_biz_improvement = conn.execute(
            "INSERT INTO departments (name, description) VALUES (?, ?)",
            ("Business Improvement", "Drives process improvement and automation adoption."),
        ).lastrowid
        dept_shared = conn.execute(
            "INSERT INTO departments (name, description) VALUES (?, ?)",
            ("Shared Services", "Cross-functional support roles."),
        ).lastrowid

        pod_exception_reporting = conn.execute(
            "INSERT INTO pods (name, department_id, description) VALUES (?, ?, ?)",
            ("Exception Reporting", dept_customer_ops, "Prepares weekly operational exception reports."),
        ).lastrowid
        pod_automation_enablement = conn.execute(
            "INSERT INTO pods (name, department_id, description) VALUES (?, ?, ?)",
            ("Automation Enablement", dept_biz_improvement, "Builds and coaches reusable automations."),
        ).lastrowid
        pod_general_support = conn.execute(
            "INSERT INTO pods (name, department_id, description) VALUES (?, ?, ?)",
            ("General Support", dept_shared, "Cross-department contributors and reviewers."),
        ).lastrowid

        def create_user(name, email, dept_id, pod_id, role_title, avatar, roles,
                         completed_trainings=None, granted_access=None):
            user_id = conn.execute(
                """INSERT INTO users (name, email, department_id, pod_id, role_title, avatar_emoji,
                       completed_trainings, granted_access, profile_last_reviewed)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    name, email, dept_id, pod_id, role_title, avatar,
                    json.dumps(completed_trainings or []), json.dumps(granted_access or []), _now(),
                ),
            ).lastrowid
            for role in roles:
                conn.execute("INSERT INTO user_roles (user_id, role) VALUES (?, ?)", (user_id, role))
            return user_id

        priya = create_user(
            "Priya Sharma", "priya.sharma@flowmatch.demo", dept_customer_ops, pod_exception_reporting,
            "Team Lead, Customer Operations", "🧭", ["team_lead"],
            granted_access=["customer_ops_workspace_view"],
        )
        jordan = create_user(
            "Jordan Lee", "jordan.lee@flowmatch.demo", dept_customer_ops, pod_exception_reporting,
            "Workflow Owner, Customer Operations", "🗂️", ["workflow_owner"],
            granted_access=["customer_ops_workspace_view"],
        )
        riley = create_user(
            "Riley Brooks", "riley.brooks@flowmatch.demo", dept_shared, pod_general_support,
            "Quality Reviewer", "✅", ["reviewer"],
            granted_access=["customer_ops_workspace_view"],
        )
        dana = create_user(
            "Dana Kim", "dana.kim@flowmatch.demo", dept_biz_improvement, pod_automation_enablement,
            "Automation Mentor", "🤖", ["mentor", "contributor", "workflow_owner"],
            granted_access=["customer_ops_workspace_view", "biz_improvement_workspace_view"],
        )
        morgan = create_user(
            "Morgan Taylor", "morgan.taylor@flowmatch.demo", dept_shared, pod_general_support,
            "Business Analyst", "🌱", ["contributor"],
            granted_access=["customer_ops_workspace_view"],
        )
        casey = create_user(
            "Casey Nguyen", "casey.nguyen@flowmatch.demo", dept_shared, pod_general_support,
            "Junior Analyst", "🚧", ["contributor"],
            granted_access=[],  # deliberately missing access -> demonstrates the blocked-match path
        )
        admin = create_user(
            "Admin User", "admin@flowmatch.demo", dept_shared, pod_general_support,
            "Platform Administrator", "🛡️", ["administrator"],
        )

        # Assign each pod's lead ("boss" for org-tree purposes) now that the
        # users exist. Used by GET /api/org/me to answer "who is my manager".
        conn.execute("UPDATE pods SET lead_user_id = ? WHERE id = ?", (priya, pod_exception_reporting))
        conn.execute("UPDATE pods SET lead_user_id = ? WHERE id = ?", (dana, pod_automation_enablement))
        conn.execute("UPDATE pods SET lead_user_id = ? WHERE id = ?", (riley, pod_general_support))

        # --- Morgan's profile (eligible contributor) ---
        conn.execute(
            "INSERT INTO user_skills (user_id, skill_id, proficiency, evidence) VALUES (?, ?, ?, ?)",
            (morgan, skill_id("Excel"), "Working knowledge", "Used for departmental reporting."),
        )
        conn.execute(
            "INSERT INTO user_skills (user_id, skill_id, proficiency, evidence) VALUES (?, ?, ?, ?)",
            (morgan, skill_id("Process mapping"), "Independent", "Mapped 3 internal workflows unaided."),
        )
        conn.execute(
            "INSERT INTO learning_goals (user_id, skill_id, goal_type) VALUES (?, ?, ?)",
            (morgan, skill_id("Power Automate"), "learn"),
        )
        conn.execute(
            "INSERT INTO learning_goals (user_id, skill_id, goal_type) VALUES (?, ?, ?)",
            (morgan, skill_id("Automation design"), "learn"),
        )
        conn.execute(
            """INSERT INTO user_preferences (user_id, opportunity_types, declared_availability,
                   ai_support_band, visibility, opted_into_discovery)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (morgan, json.dumps(["process_discovery", "shadow_for_a_day"]), "2 hours/week for 4 weeks",
             "Practitioner", "visible_to_org", 1),
        )

        # --- Casey's profile (ineligible - missing access) ---
        conn.execute(
            "INSERT INTO user_skills (user_id, skill_id, proficiency, evidence) VALUES (?, ?, ?, ?)",
            (casey, skill_id("Process mapping"), "Awareness", None),
        )
        conn.execute(
            """INSERT INTO user_preferences (user_id, opportunity_types, declared_availability,
                   ai_support_band, visibility, opted_into_discovery)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (casey, json.dumps(["process_discovery"]), "1 hour/week", "Explorer", "visible_to_org", 1),
        )

        # --- Dana's profile (mentor) ---
        conn.execute(
            "INSERT INTO user_skills (user_id, skill_id, proficiency, evidence) VALUES (?, ?, ?, ?)",
            (dana, skill_id("Power Automate"), "Coach", "Built the reporting automation template."),
        )
        conn.execute(
            """INSERT INTO user_preferences (user_id, opportunity_types, declared_availability,
                   ai_support_band, visibility, opted_into_discovery)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (dana, json.dumps(["ai_coaching", "automation_transfer"]), "1 coaching session/week",
             "Enabler", "visible_to_org", 1),
        )

        # --- Workflow 1: Customer Operations exception report (published, ready for matching) ---
        source_text = (
            "Export approved synthetic records.\n"
            "Remove irrelevant fields.\n"
            "Standardize categories.\n"
            "Identify missing information.\n"
            "Create a summary.\n"
            "Submit it for review."
        )
        workflow_1 = conn.execute(
            """INSERT INTO workflows (name, description, department_id, pod_id, business_purpose,
                   owner_id, reviewer_id, source_type, source_text, validation_status, sensitivity,
                   comparison_permission, created_at, last_reviewed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "Prepare weekly operational exception report", "Weekly spreadsheet preparation for exception cases.",
                dept_customer_ops, pod_exception_reporting,
                "Give leadership visibility into unresolved customer-operations exceptions each week.",
                jordan, riley, "pasted_text", source_text, "published", "low", 1, _now(), _now(),
            ),
        ).lastrowid
        stage_names = [
            ("Export approved synthetic records", "systems", "Reporting system export"),
            ("Remove irrelevant fields", None, None),
            ("Standardize categories", None, None),
            ("Identify missing information", None, None),
            ("Create a summary", None, None),
            ("Submit it for review", None, None),
        ]
        stage_ids_1 = []
        for i, (name, _, systems) in enumerate(stage_names, start=1):
            backlog = "critical_internal_need" if i == 3 else "no_current_need"
            bottleneck = "Manual spreadsheet standardization takes ~3 hours/week and is error-prone." if i == 3 else None
            sid = conn.execute(
                """INSERT INTO workflow_stages
                   (workflow_id, name, description, sequence, activities, responsible_role, inputs, outputs,
                    systems, backlog_status, bottleneck, automation_maturity, sensitivity, controls,
                    access_requirements, suitable_process_discovery, suitable_bounded_help,
                    required_reviewer_id, last_validated_at, ai_generated, uncertain_fields)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    workflow_1, name, name, i, name, "Operations Analyst",
                    "Prior week's exception records" if i == 1 else None,
                    "Standardized exception summary" if i == 5 else None,
                    systems, backlog, bottleneck, "manual" if i == 3 else "partial",
                    "low", "Reviewed weekly by team lead", "customer_ops_workspace_view",
                    1, 1, riley, _now(), 0, "[]",
                ),
            ).lastrowid
            stage_ids_1.append(sid)

        bottleneck_stage_id = stage_ids_1[2]  # "Standardize categories"

        # --- Workflow 2: Business Improvement's similar automated workflow (published) ---
        workflow_2 = conn.execute(
            """INSERT INTO workflows (name, description, department_id, pod_id, business_purpose,
                   owner_id, reviewer_id, source_type, source_text, validation_status, sensitivity,
                   comparison_permission, created_at, last_reviewed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "Prepare monthly internal reporting summary", "Similar structured-data reporting workflow, already partly automated.",
                dept_biz_improvement, pod_automation_enablement,
                "Give leadership a monthly summary of internal reporting metrics.",
                dana, dana, "manual", None, "published", "low", 1, _now(), _now(),
            ),
        ).lastrowid
        biz_stage_names = [
            ("Export structured records", "Reporting system export"),
            ("Standardize categories using automation template", "Power Automate"),
            ("Create a summary", None),
        ]
        stage_ids_2 = []
        for i, (name, systems) in enumerate(biz_stage_names, start=1):
            sid = conn.execute(
                """INSERT INTO workflow_stages
                   (workflow_id, name, description, sequence, activities, responsible_role, systems,
                    backlog_status, automation_maturity, sensitivity, suitable_automation_reuse,
                    required_reviewer_id, last_validated_at, ai_generated, uncertain_fields)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    workflow_2, name, name, i, name, "Automation Analyst", systems,
                    "no_current_need", "automated" if i == 2 else "partial", "low", 1,
                    dana, _now(), 0, "[]",
                ),
            ).lastrowid
            stage_ids_2.append(sid)

        automated_stage_id = stage_ids_2[1]  # "Standardize categories using automation template"

        # --- Reusable asset on workflow 2 ---
        conn.execute(
            """INSERT INTO reusable_assets
               (workflow_id, name, type, description, owner_id, approved_users, reuse_permission,
                documentation_status, dependencies, required_systems, known_constraints,
                risk_classification, review_date, transfer_contact)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                workflow_2, "Reporting Data Prep Automation Template", "automation",
                "A Power Automate template that standardizes exported record categories automatically.",
                dana, "[]", "requires_review", "documented", "Power Automate license",
                "Power Automate", "Requires reviewing field mappings before reuse.", "low", _now(),
                "dana.kim@flowmatch.demo",
            ),
        )

        # --- Opportunity 1: fully specified, published (spec section 19's bounded opportunity) ---
        conn.execute(
            """INSERT INTO opportunities
               (workflow_id, stage_id, title, problem_statement, opportunity_type, desired_outcome,
                definition_of_done, expected_deliverable, estimated_effort, required_skills,
                learnable_skills, required_ai_band, required_systems, required_authorization,
                mandatory_training, sensitivity, approved_ai_assistance, reusable_assets,
                owner_id, reviewer_id, mentor_available, escalation_points, start_conditions,
                participation_boundary, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                workflow_1, bottleneck_stage_id,
                "Assess and document exception-report standardization for automation",
                "The weekly category-standardization step is manual, repetitive, and error-prone.",
                "process_discovery",
                "A clear write-up of the manual steps and a recommendation on whether the "
                "Business Improvement automation template could be adapted for reuse.",
                "A one-page process-discovery note listing manual steps, time spent, and an "
                "automation-reuse recommendation, reviewed and accepted by the reviewer.",
                "Documented findings note", "2 hours/week for 4 weeks",
                json.dumps(["Process mapping"]), json.dumps(["Power Automate", "Automation design"]),
                None, "Reporting system", "customer_ops_workspace_view", None, "low",
                "Approved for structuring/documenting synthetic data only",
                json.dumps(["Reporting Data Prep Automation Template"]),
                priya, riley, 1,
                "Escalate to Priya Sharma if source data looks incomplete or sensitive.",
                "Access to the reporting export has been pre-approved for this opportunity.",
                "Do not access any records outside the weekly exception report export.",
                "published", _now(),
            ),
        )

        # --- Opportunity 2: deliberately incomplete draft (demonstrates blocked publish, design.md FR14) ---
        conn.execute(
            """INSERT INTO opportunities
               (workflow_id, stage_id, title, problem_statement, opportunity_type, desired_outcome,
                definition_of_done, expected_deliverable, estimated_effort, required_skills,
                learnable_skills, required_ai_band, required_systems, required_authorization,
                mandatory_training, sensitivity, approved_ai_assistance, reusable_assets,
                owner_id, reviewer_id, mentor_available, escalation_points, start_conditions,
                participation_boundary, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                workflow_1, stage_ids_1[1],
                "Shadow the exception-report field-removal step",
                "Contributors could learn the intake process by shadowing this step.",
                "shadow_for_a_day", "Better cross-team understanding of the report intake process.",
                None,  # definition_of_done missing - blocks publish
                None, "1 afternoon", json.dumps([]), json.dumps([]),
                None, None, None, None, "unknown",  # sensitivity unknown - blocks publish
                None, "[]",
                priya, None,  # reviewer missing - blocks publish
                0, None, None, None,
                "draft", _now(),
            ),
        )

        # --- Bulk synthetic company: ~250 more profiles across a realistic
        # FinTech org, plus cross-department workflows (docs/DECISIONS.md #5
        # extended for a richer demo). Kept in a separate module so the
        # original spec-scenario entity ids above never shift. ---
        from app.seed_bulk import seed_bulk
        seed_bulk(
            conn, skill_id, extra_skill_catalogue=[
                "AML/KYC review", "Fraud detection", "Regulatory reporting", "Payment reconciliation",
                "Credit risk modeling", "Underwriting", "SQL", "Python", "Incident response",
                "Cloud infrastructure", "API design", "Ledger accounting", "Financial close",
                "Vendor risk assessment", "Chargeback handling", "Card network rules",
                "Liquidity forecasting", "Data pipeline engineering", "Machine learning",
                "Customer success", "Sales enablement", "Campaign management", "Employment law",
                "HR operations",
            ],
            original_users={
                "priya": priya, "jordan": jordan, "riley": riley, "dana": dana,
                "morgan": morgan, "casey": casey, "admin": admin,
            },
        )

    print("FlowMatch demo data seeded.")


if __name__ == "__main__":
    seed()
