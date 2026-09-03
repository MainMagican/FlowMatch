"""Bulk synthetic org generator: ~250 additional employee profiles across a
realistic 500+ headcount FinTech company, plus a batch of cross-department
workflows (some sharing near-identical stages on purpose, some fully unique)
so the similarity/reuse and validation demos have real breadth.

Deterministic (fixed random seed) so re-seeding produces the same company
every time. Called once from app.seed.seed() AFTER the original spec section
19 scenario, so none of the original demo entity ids shift (tests rely on
those staying put).
"""

import json
import random
from datetime import datetime, timezone

FIRST_NAMES = [
    "James", "Maria", "Wei", "Fatima", "Liam", "Sofia", "Noah", "Amara", "Yusuf", "Elena",
    "Chen", "Aisha", "Lucas", "Priya", "Omar", "Grace", "Kenji", "Anya", "Diego", "Ingrid",
    "Tariq", "Nora", "Hiro", "Camila", "Sven", "Zainab", "Marcus", "Leila", "Felix", "Wanjiru",
    "Arjun", "Freya", "Kwame", "Yuki", "Adrian", "Chioma", "Mateo", "Sana", "Bjorn", "Rosa",
    "Nikolai", "Ama", "Ravi", "Elif", "Connor", "Meera", "Tomas", "Nadia", "Ethan", "Layla",
    "Hassan", "Mei", "Gabriel", "Zoe", "Aditya", "Ingrid", "Kofi", "Lena", "Rohan", "Isla",
]
LAST_NAMES = [
    "Nguyen", "Okafor", "Kowalski", "Silva", "Andersson", "Haddad", "Kim", "Patel", "Rossi", "Novak",
    "Mensah", "Ibrahim", "Larsen", "Tanaka", "Moreno", "Schmidt", "Osei", "Duarte", "Kovac", "Reyes",
    "Petrov", "Diallo", "Fischer", "Costa", "Bakker", "Adeyemi", "Nakamura", "Santos", "Weber", "Kaur",
    "Ferreira", "Berg", "Odhiambo", "Ivanova", "Marchetti", "Yamamoto", "Cisse", "Novotny", "Almeida", "Ostrom",
    "Choudhury", "Karlsson", "Adeleke", "Wojcik", "Lindqvist", "Machado", "Boateng", "Sokolova", "Vidal", "Truong",
]

FINTECH_SKILLS = [
    "AML/KYC review", "Fraud detection", "Regulatory reporting", "Payment reconciliation",
    "Credit risk modeling", "Underwriting", "SQL", "Python", "Incident response", "Cloud infrastructure",
    "API design", "Ledger accounting", "Financial close", "Vendor risk assessment", "Chargeback handling",
    "Card network rules", "Liquidity forecasting", "Data pipeline engineering", "Machine learning",
    "Customer success", "Sales enablement", "Campaign management", "Employment law", "HR operations",
]

AI_BANDS = ["Explorer", "Practitioner", "Builder", "Enabler"]
OPPORTUNITY_TYPE_POOL = [
    "shadow_for_a_day", "bounded_backlog_assistance", "ai_coaching",
    "automation_transfer", "process_discovery", "short_cross_team_project",
]


def _now():
    return datetime.now(timezone.utc).isoformat()


def seed_bulk(conn, skill_id, extra_skill_catalogue, original_users):
    """original_users: dict with keys priya/jordan/riley/dana/morgan/casey/admin -> user_id,
    used only to wire up manager_id for the original 7 so the company tree is fully connected."""
    rng = random.Random(42)

    for name in extra_skill_catalogue:
        conn.execute("INSERT OR IGNORE INTO skills (name, is_custom) VALUES (?, 0)", (name,))
    skill_ids = {}
    for row in conn.execute("SELECT id, name FROM skills").fetchall():
        skill_ids[row["name"]] = row["id"]

    used_emails = set(r["email"] for r in conn.execute("SELECT email FROM users").fetchall())

    def unique_name_email():
        while True:
            name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
            email = name.lower().replace(" ", ".") + "@flowmatch.demo"
            if email not in used_emails:
                used_emails.add(email)
                return name, email

    AVATARS = ["🧑‍💼", "👩‍💻", "🧑‍💻", "👨‍💼", "🧑‍🔬", "👩‍🔬", "🧑‍🎓", "👨‍🏫", "🧑‍⚖️", "👩‍⚖️"]

    def make_user(dept_id, pod_id, role_title, roles, manager_id=None, skills=None, goals=None,
                  ai_band=None, opted_in=True):
        name, email = unique_name_email()
        user_id = conn.execute(
            """INSERT INTO users (name, email, department_id, pod_id, manager_id, role_title,
                   avatar_emoji, completed_trainings, granted_access, profile_last_reviewed)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, email, dept_id, pod_id, manager_id, role_title, rng.choice(AVATARS),
             "[]", json.dumps(["customer_ops_workspace_view"]) if rng.random() < 0.6 else "[]", _now()),
        ).lastrowid
        for role in roles:
            conn.execute("INSERT OR IGNORE INTO user_roles (user_id, role) VALUES (?, ?)", (user_id, role))
        for sk in (skills or []):
            if sk in skill_ids:
                conn.execute(
                    "INSERT OR IGNORE INTO user_skills (user_id, skill_id, proficiency, evidence) VALUES (?, ?, ?, ?)",
                    (user_id, skill_ids[sk], rng.choice(["Awareness", "Working knowledge", "Independent", "Advanced"]), None),
                )
        for g in (goals or []):
            if g in skill_ids:
                conn.execute(
                    "INSERT OR IGNORE INTO learning_goals (user_id, skill_id, goal_type) VALUES (?, ?, ?)",
                    (user_id, skill_ids[g], rng.choice(["learn", "practise", "master"])),
                )
        conn.execute(
            """INSERT INTO user_preferences (user_id, opportunity_types, declared_availability,
                   ai_support_band, visibility, opted_into_discovery)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, json.dumps(rng.sample(OPPORTUNITY_TYPE_POOL, k=rng.randint(1, 3))),
             rng.choice(["1 hour/week", "2 hours/week for 4 weeks", "Half a day/month", "3 hours/week"]),
             ai_band or rng.choice(AI_BANDS), "visible_to_org", 1 if opted_in and rng.random() < 0.9 else 0),
        )
        return user_id

    # ---- CEO / Executive Office (root of the company tree) ----
    dept_exec = conn.execute(
        "INSERT INTO departments (name, description) VALUES (?, ?)",
        ("Executive Office", "Company leadership and executive functions."),
    ).lastrowid
    pod_exec = conn.execute(
        "INSERT INTO pods (name, department_id, description) VALUES (?, ?, ?)",
        ("Executive Leadership", dept_exec, "C-suite and executive staff."),
    ).lastrowid
    ceo_id = make_user(dept_exec, pod_exec, "Chief Executive Officer", ["administrator"], manager_id=None,
                        ai_band="Enabler")
    conn.execute("UPDATE pods SET lead_user_id = ? WHERE id = ?", (ceo_id, pod_exec))
    for _ in range(3):
        make_user(dept_exec, pod_exec, rng.choice(["Chief of Staff", "Executive Assistant", "VP Strategy"]),
                  ["contributor"], manager_id=ceo_id)

    # Wire the original 7 demo personas into the same company tree.
    conn.execute("UPDATE users SET manager_id = ? WHERE id = ?", (ceo_id, original_users["priya"]))
    conn.execute("UPDATE users SET manager_id = ? WHERE id = ?", (original_users["priya"], original_users["jordan"]))
    conn.execute("UPDATE users SET manager_id = ? WHERE id = ?", (ceo_id, original_users["dana"]))
    conn.execute("UPDATE users SET manager_id = ? WHERE id = ?", (ceo_id, original_users["riley"]))
    conn.execute("UPDATE users SET manager_id = ? WHERE id = ?", (original_users["riley"], original_users["morgan"]))
    conn.execute("UPDATE users SET manager_id = ? WHERE id = ?", (original_users["riley"], original_users["casey"]))
    conn.execute("UPDATE users SET manager_id = ? WHERE id = ?", (ceo_id, original_users["admin"]))

    # ---- Department blueprint: (name, description, [(pod_name, size, owns_workflow)]) ----
    blueprint = [
        ("Engineering & Platform", "Builds and operates the core banking and payments platform.", [
            ("Payments Platform", 11, True), ("Core Banking Systems", 10, False),
            ("Developer Experience", 7, False), ("Site Reliability", 9, True),
        ]),
        ("Product Management", "Defines product strategy and requirements.", [
            ("Consumer Product", 6, False), ("SMB Product", 6, False), ("Platform Product", 5, False),
        ]),
        ("Risk & Compliance", "Manages regulatory, credit, and compliance risk.", [
            ("AML & KYC", 8, True), ("Regulatory Reporting", 7, True), ("Credit Risk", 7, False),
        ]),
        ("Fraud & Security Operations", "Detects and responds to fraud and security threats.", [
            ("Fraud Detection", 8, True), ("Security Operations", 7, False),
        ]),
        ("Data & Analytics", "Central data platform, BI, and modeling.", [
            ("Data Engineering", 8, False), ("Business Intelligence", 7, False), ("ML & Modeling", 7, False),
        ]),
        ("Payments Operations", "Runs day-to-day transaction and settlement operations.", [
            ("Transaction Processing", 10, False), ("Chargebacks & Disputes", 9, True), ("Settlement", 9, True),
        ]),
        ("Customer Support & Success", "Front-line support and account success.", [
            ("Tier 1 Support", 13, False), ("Tier 2 Support", 10, False), ("Customer Success", 10, False),
        ]),
        ("Sales & Partnerships", "New business and partner relationships.", [
            ("Enterprise Sales", 6, False), ("Partnerships", 6, False),
        ]),
        ("Marketing & Growth", "Brand, content, and growth marketing.", [
            ("Brand & Content", 6, False), ("Growth & Performance", 6, True),
        ]),
        ("Finance & Accounting", "Financial close, reporting, and planning.", [
            ("Accounting", 6, True), ("FP&A", 6, False),
        ]),
        ("Treasury & Liquidity", "Manages company liquidity and funding.", [
            ("Treasury Operations", 4, False),
        ]),
        ("People & Culture", "HR, talent acquisition, and people operations.", [
            ("Talent Acquisition", 5, True), ("HR Business Partners", 5, False),
        ]),
        ("Legal & Regulatory Affairs", "Legal counsel and regulatory affairs.", [
            ("Legal Counsel", 4, True),
        ]),
    ]

    dept_ids = {}
    pod_ids = {}
    pod_leads = {}   # pod_name -> user_id
    dept_heads = {}  # dept_name -> user_id

    for dept_name, dept_desc, pods_spec in blueprint:
        dept_id = conn.execute(
            "INSERT INTO departments (name, description) VALUES (?, ?)", (dept_name, dept_desc)
        ).lastrowid
        dept_ids[dept_name] = dept_id
        dept_head_id = None
        for pod_name, size, owns_workflow in pods_spec:
            pod_id = conn.execute(
                "INSERT INTO pods (name, department_id, description) VALUES (?, ?, ?)",
                (pod_name, dept_id, f"{pod_name} team within {dept_name}."),
            ).lastrowid
            pod_ids[pod_name] = pod_id

            lead_roles = ["team_lead"] + (["workflow_owner"] if owns_workflow else [])
            lead_manager = dept_head_id if dept_head_id else ceo_id
            lead_id = make_user(
                dept_id, pod_id, f"{pod_name} Lead", lead_roles, manager_id=lead_manager,
                skills=rng.sample(FINTECH_SKILLS, k=2),
            )
            conn.execute("UPDATE pods SET lead_user_id = ? WHERE id = ?", (lead_id, pod_id))
            pod_leads[pod_name] = lead_id
            if dept_head_id is None:
                dept_head_id = lead_id
                # Re-parent the department head under the CEO explicitly (already set above).
                conn.execute("UPDATE users SET manager_id = ? WHERE id = ?", (ceo_id, lead_id))

            # First member of every pod also gets "reviewer" so each area has someone
            # who can review submissions/opportunities.
            for i in range(size - 1):
                roles = ["contributor"]
                if i == 0:
                    roles.append("reviewer")
                elif rng.random() < 0.05:
                    roles.append("mentor")
                make_user(
                    dept_id, pod_id, f"{pod_name} Specialist", roles, manager_id=lead_id,
                    skills=rng.sample(FINTECH_SKILLS, k=rng.randint(1, 3)),
                    goals=rng.sample(FINTECH_SKILLS, k=rng.randint(0, 2)),
                )
        dept_heads[dept_name] = dept_head_id

    # ================= Synthetic cross-department workflows =================
    # Each entry: (name, business_purpose, dept_name, pod_name, owner_id, reviewer_id,
    #              validation_status, sensitivity, [(stage_name, backlog_status)])
    def add_workflow(name, purpose, dept_name, pod_name, owner_id, reviewer_id, status, sensitivity, stages):
        wf_id = conn.execute(
            """INSERT INTO workflows (name, description, department_id, pod_id, business_purpose,
                   owner_id, reviewer_id, source_type, source_text, validation_status, sensitivity,
                   comparison_permission, created_at, last_reviewed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, purpose, dept_ids[dept_name], pod_ids[pod_name], purpose, owner_id, reviewer_id,
             "manual", None, status, sensitivity, 1, _now(), _now() if status in ("validated", "published") else None),
        ).lastrowid
        stage_ids = []
        for i, (stage_name, backlog) in enumerate(stages, start=1):
            sid = conn.execute(
                """INSERT INTO workflow_stages
                   (workflow_id, name, description, sequence, activities, responsible_role,
                    backlog_status, automation_maturity, sensitivity, ai_generated, uncertain_fields)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (wf_id, stage_name, stage_name, i, stage_name, f"{pod_name} Specialist",
                 backlog, rng.choice(["manual", "partial"]), sensitivity, 0, "[]"),
            ).lastrowid
            stage_ids.append(sid)
        return wf_id, stage_ids

    kyc_owner = pod_leads["AML & KYC"]
    kyc_reviewer = dept_heads["Risk & Compliance"]
    add_workflow(
        "Customer KYC onboarding verification",
        "Verify new customer identity before activating a banking account.",
        "Risk & Compliance", "AML & KYC", kyc_owner, kyc_reviewer, "published", "high",
        [("Collect customer documents", "assistance_requested"), ("Verify identity documents", "no_current_need"),
         ("Screen against watchlists", "no_current_need"), ("Approve or escalate account", "no_current_need"),
         ("Notify customer of outcome", "no_current_need")],
    )

    add_workflow(
        "Enhanced due diligence for high-risk customers",
        "Deeper review triggered when a customer is flagged as elevated-risk during onboarding.",
        "Risk & Compliance", "AML & KYC", kyc_owner, kyc_reviewer, "draft", "high",
        [("Flag elevated-risk customer", "no_current_need"), ("Gather enhanced documentation", "assistance_requested"),
         ("Senior analyst review", "no_current_need"), ("Approve or reject account", "no_current_need")],
    )

    hr_owner = pod_leads["Talent Acquisition"]
    add_workflow(
        "New employee onboarding",
        "Onboard a new hire from offer acceptance to first day readiness.",
        "People & Culture", "Talent Acquisition", hr_owner, dept_heads["People & Culture"], "validated", "medium",
        [("Collect new hire documents", "monitoring"), ("Provision system access", "critical_internal_need"),
         ("Schedule orientation", "no_current_need"), ("Assign onboarding buddy", "no_current_need")],
    )

    legal_owner = pod_leads["Legal Counsel"]
    add_workflow(
        "Vendor onboarding & due diligence",
        "Onboard a new third-party vendor after a compliance review.",
        "Legal & Regulatory Affairs", "Legal Counsel", legal_owner, dept_heads["Risk & Compliance"],
        "needs_owner_review", "medium",
        [("Collect vendor documents", "assistance_requested"), ("Perform due diligence check", "no_current_need"),
         ("Approve vendor contract", "no_current_need")],
    )

    fraud_owner = pod_leads["Fraud Detection"]
    add_workflow(
        "Fraud alert triage",
        "Triage and act on real-time fraud detection alerts.",
        "Fraud & Security Operations", "Fraud Detection", fraud_owner, dept_heads["Fraud & Security Operations"],
        "published", "high",
        [("Receive fraud alert", "no_current_need"), ("Investigate transaction pattern", "critical_internal_need"),
         ("Decide block or clear", "no_current_need"), ("Document decision", "no_current_need")],
    )

    chargeback_owner = pod_leads["Chargebacks & Disputes"]
    add_workflow(
        "Chargeback dispute resolution",
        "Investigate and respond to customer chargeback disputes.",
        "Payments Operations", "Chargebacks & Disputes", chargeback_owner, dept_heads["Payments Operations"],
        "published", "medium",
        [("Receive chargeback notice", "no_current_need"), ("Investigate transaction pattern", "assistance_requested"),
         ("Gather evidence", "no_current_need"), ("Submit response to card network", "no_current_need"),
         ("Document decision", "no_current_need")],
    )

    finance_owner = pod_leads["Accounting"]
    add_workflow(
        "Monthly financial close",
        "Close the books at month end and produce leadership reporting.",
        "Finance & Accounting", "Accounting", finance_owner, dept_heads["Finance & Accounting"], "published", "medium",
        [("Reconcile ledger accounts", "monitoring"), ("Review journal entries", "no_current_need"),
         ("Prepare close summary", "no_current_need"), ("Obtain sign-off", "no_current_need")],
    )

    settlement_owner = pod_leads["Settlement"]
    add_workflow(
        "Payment settlement reconciliation",
        "Reconcile daily payment settlement records against the ledger.",
        "Payments Operations", "Settlement", settlement_owner, dept_heads["Payments Operations"],
        "needs_owner_review", "medium",
        [("Export settlement records", "no_current_need"), ("Reconcile ledger accounts", "critical_internal_need"),
         ("Identify discrepancies", "assistance_requested"), ("Escalate unresolved items", "no_current_need")],
    )

    regreport_owner = pod_leads["Regulatory Reporting"]
    add_workflow(
        "Regulatory report submission",
        "Prepare and submit a periodic regulatory filing.",
        "Risk & Compliance", "Regulatory Reporting", regreport_owner, dept_heads["Risk & Compliance"], "validated", "high",
        [("Extract regulatory data", "no_current_need"), ("Validate data completeness", "monitoring"),
         ("Generate regulatory filing", "no_current_need"), ("Submit to regulator", "no_current_need"),
         ("Archive confirmation", "no_current_need")],
    )

    sre_owner = pod_leads["Site Reliability"]
    add_workflow(
        "Incident response runbook execution",
        "Respond to a production incident from detection to post-mortem.",
        "Engineering & Platform", "Site Reliability", sre_owner, dept_heads["Engineering & Platform"], "published", "low",
        [("Detect incident", "no_current_need"), ("Triage severity", "no_current_need"),
         ("Mitigate impact", "assistance_requested"), ("Conduct post-mortem", "no_current_need")],
    )

    marketing_owner = pod_leads["Growth & Performance"]
    add_workflow(
        "Marketing campaign approval",
        "Take a campaign from brief to launch with the right sign-offs.",
        "Marketing & Growth", "Growth & Performance", marketing_owner, dept_heads["Marketing & Growth"],
        "ai_generated_draft", "low",
        [("Draft campaign brief", "no_current_need"), ("Legal compliance review", "monitoring"),
         ("Design creative assets", "no_current_need"), ("Launch campaign", "no_current_need"),
         ("Measure performance", "assistance_requested")],
    )

    print(f"FlowMatch bulk org seeded: {len(dept_ids) + 1} new departments, "
          f"{conn.execute('SELECT COUNT(*) c FROM users').fetchone()['c']} total users.")
