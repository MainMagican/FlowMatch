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

    def unique_name_email(person_name=None):
        if person_name:
            email = person_name.lower().replace(" ", ".") + "@flowmatch.demo"
            used_emails.add(email)
            return person_name, email
        while True:
            name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
            email = name.lower().replace(" ", ".") + "@flowmatch.demo"
            if email not in used_emails:
                used_emails.add(email)
                return name, email

    AVATARS = ["🧑‍💼", "👩‍💻", "🧑‍💻", "👨‍💼", "🧑‍🔬", "👩‍🔬", "🧑‍🎓", "👨‍🏫", "🧑‍⚖️", "👩‍⚖️"]

    def make_user(dept_id, pod_id, role_title, roles, manager_id=None, skills=None, goals=None,
                  ai_band=None, opted_in=True, person_name=None):
        if person_name:
            existing_user = conn.execute(
                "SELECT id FROM users WHERE name = ?", (person_name,)
            ).fetchone()
            if existing_user:
                for role in roles:
                    conn.execute(
                        "INSERT OR IGNORE INTO user_roles (user_id, role) VALUES (?, ?)",
                        (existing_user["id"], role),
                    )
                return existing_user["id"]
        name, email = unique_name_email(person_name)
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
                        ai_band="Enabler", person_name="Laust Bertelsen")
    conn.execute("UPDATE pods SET lead_user_id = ? WHERE id = ?", (ceo_id, pod_exec))

    # Wire the named internal profiles into the organization tree.
    conn.execute("UPDATE users SET manager_id = ? WHERE id = ?", (ceo_id, original_users["priya"]))
    conn.execute("UPDATE users SET manager_id = ? WHERE id = ?", (original_users["priya"], original_users["jordan"]))
    conn.execute("UPDATE users SET manager_id = ? WHERE id = ?", (ceo_id, original_users["dana"]))
    conn.execute("UPDATE users SET manager_id = ? WHERE id = ?", (ceo_id, original_users["riley"]))
    conn.execute("UPDATE users SET manager_id = ? WHERE id = ?", (original_users["riley"], original_users["morgan"]))
    conn.execute("UPDATE users SET manager_id = ? WHERE id = ?", (original_users["riley"], original_users["casey"]))
    conn.execute("UPDATE users SET manager_id = ? WHERE id = ?", (ceo_id, original_users["admin"]))

    # July 2026 organization structure. Team members remain synthetic demo
    # profiles, while the hierarchy and functional leadership reflect the org chart.
    # (name, description, (department_head, title), [(pod, lead, title, size, owns_workflow)])
    blueprint = [
        ("Business AML", "Client due diligence, financial-crime operations, and investigations.",
         ("James Grant", "Head of Business AML"), [
            ("Client Due Diligence", "Dean Fry", "Head of Client Due Diligence", 14, True),
            ("Transaction Monitoring & Investigations", "Emma Johnson", "Head of TM & Investigations", 12, True),
            ("Sanctions Screening", "Kelvin Asare-Ofei", "Sanctions Screening Lead", 10, True),
            ("AML Intelligence & Investigations", "Sophie Bielska", "Team Lead", 6, False),
        ]),
        ("Commercial", "Commercial strategy, sales, account management, and market engagement.",
         ("Mishal Ruparel", "Chief Commercial Officer"), [
            ("Sales UK & EMEA", "Jonathan Levine", "Head of Business Development UK", 10, False),
            ("Europe Account Management", "Sophia Boehm", "Team Lead", 8, False),
            ("APAC Commercial", "Nischa Us-Moynihan", "Chief Sales Officer", 8, False),
            ("Marketing", "Gaya Ananda", "Head of Client & Market Engagement", 6, True),
        ]),
        ("Global Core Operations", "Global client operations, payment operations, and process automation.",
         ("Christopher John Hughes", "Head of Global Core Operations"), [
            ("Client Operations", "Thomas Bolden", "Head of Client Operations", 12, True),
            ("Operations Stability & Support", "Kathrine Møller", "Head of Payment Monitoring", 9, False),
            ("Payment Process Automation", "Claus Rasmus Hjort", "Head of Payment Process Automation", 8, True),
        ]),
        ("Client Technology", "Client integration, client platforms, and commercial technology.",
         ("Christian Hededal", "Head of Client Technology"), [
            ("Client Integration", "Giuditta Introini", "Head of Client Integration", 8, False),
            ("Client Platform", "Stefan Kretzer", "Head of Client Platform", 12, False),
            ("Commercial Analytics & Tools", "Sebastian Gabel", "Head of Commercial Analytics & Tools", 8, False),
        ]),
        ("Core Technology", "Core payments, banking, and business-test technology.",
         ("Lars Bæk Pedersen", "Co-Head of Core Technology"), [
            ("Core Payments Execution", "Lars Bæk Pedersen", "Co-Head of Core Technology", 10, False),
            ("Core Banking", "Ajit Kumar Singh", "Team Lead", 9, False),
            ("Business Test", "Lars Bæk Pedersen", "Team Lead", 7, False),
        ]),
        ("Technology Operations", "Technology operations, platforms, cloud engineering, and service management.",
         ("Daniel Studer", "Head of Technology Operations"), [
            ("Operations Center", "Paul Hartley", "Head of Operations Center", 9, False),
            ("Core Technology Platforms", "Michael Vedel", "Head of Core Technology Platforms", 9, False),
            ("Cloud Engineering", "Darius Romosan", "Head of Cloud Engineering", 9, True),
        ]),
        ("Clearing Technology", "Clearing products, alternative payment methods, and clearing technology.",
         ("Michael Boel", "Co-Head of Clearing Technology"), [
            ("Clearing Business Analysis", "Mikko Olsamo", "Team Lead", 7, False),
            ("CEPOS Clearing", "Gurkan Koyuncu", "Team Lead", 8, False),
            ("CEPOS Alternative Payment Methods", "Tomasz Maciej Barczewski", "Team Lead", 6, False),
        ]),
        ("Data, Analytics & AI", "Enterprise data engineering, data science, and information management.",
         ("Christian Karsten", "Chief Analytics Officer"), [
            ("Data Engineering", "Ejvind Hald", "Head of Data Engineering", 10, False),
            ("AIOps", "Anton Sörensen", "Lead Analytics Engineer", 7, True),
            ("Information Management", "Jacob Baggers Willemoes", "Head of Information Management", 8, True),
        ]),
        ("Products", "Product strategy and delivery across payments and business solutions.",
         ("Charlotte Hassing", "Head of Products"), [
            ("Payments & Business Development", "Lizette Drewsen", "Strategic Projects Lead", 8, False),
            ("FX & Business Solutions", "Frederik Hauge", "Head of FX & Business Solutions", 7, False),
            ("Ancillary Products & Product Governance", "Thomas Kampmann", "Head of Product Governance", 6, False),
        ]),
        ("Treasury", "Treasury front office and treasury analytics.",
         ("Rasmus Joey Hastrup", "Head of Treasury"), [
            ("Treasury Front Office", "Rasmus Joey Hastrup", "Head of Treasury", 7, False),
            ("Treasury Analytics", "Morten Viholt Daubjerg", "Deputy Head of Treasury", 6, False),
        ]),
        ("Finance", "Financial planning, accounting, regulatory reporting, and procurement.",
         ("Michael Bo Nørlem Hansen", "Chief Financial Officer"), [
            ("Accounting", "Katty Fries-Poitoux", "Head of Accounting", 10, True),
            ("Financial Planning & Management Reporting", "Jacob Kjeldtoft Hansen", "Head of Financial Planning", 7, False),
            ("Tax & Regulatory Reporting", "Paulius Juozaitis", "Head of Tax & Regulatory Reporting", 8, True),
        ]),
        ("People", "People operations, recruitment, payroll, and business partnering.",
         ("Jonas Fabricius-Bekker", "Chief People Officer"), [
            ("Recruitment", "Katja Linnea Serritzlew", "Global Recruitment Lead", 7, True),
            ("Business Partner", "Eve Ojijo-Grattan", "Head of Employee Experience", 6, False),
            ("HR Support", "Angela Pincheira", "HR Manager", 6, False),
        ]),
        ("Legal", "Legal counsel, governance, and regulatory projects.",
         ("Tobias Hansen", "General Counsel & Head of Legal"), [
            ("Legal Counsel", "Marianne Bernou", "Head of Legal Central Europe", 7, True),
            ("Internal Governance & Regulatory Projects", "Hanna Laitinmäki", "Head of Internal Governance", 6, False),
        ]),
        ("Risk", "Operational, financial, and ICT risk management.",
         ("Henrik Hednäs", "Chief Risk Officer"), [
            ("ICT Risk", "Kenneth Walker", "Global Information Security Officer", 7, False),
            ("Operational Risk", "Sergejs Koleda", "Head of Operational Risk", 6, False),
            ("Financial & UK Risk", "Danielle Gontier", "Head of Financial & UK Risk", 5, False),
        ]),
        ("Compliance", "Group compliance, MLRO offices, controls, and fraud investigations.",
         ("Patrick Green", "Chief Compliance Officer & MLRO"), [
            ("Fraud Investigations", "Andi Maliqi", "Head of Fraud Investigations", 7, True),
            ("Compliance Controls & Governance", "Pippa Vilas", "Head of Compliance Controls & Governance", 7, False),
            ("International Compliance", "Peter Paulsen", "Head of International Compliance", 7, False),
        ]),
    ]

    dept_ids = {}
    pod_ids = {}
    pod_leads = {}   # pod_name -> user_id
    dept_heads = {}  # dept_name -> user_id

    for dept_name, dept_desc, (head_name, head_title), pods_spec in blueprint:
        existing_department = conn.execute(
            "SELECT id FROM departments WHERE name = ?", (dept_name,)
        ).fetchone()
        dept_id = existing_department["id"] if existing_department else conn.execute(
            "INSERT INTO departments (name, description) VALUES (?, ?)", (dept_name, dept_desc)
        ).lastrowid
        dept_ids[dept_name] = dept_id
        leadership_pod_id = conn.execute(
            "INSERT INTO pods (name, department_id, description) VALUES (?, ?, ?)",
            (f"{dept_name} Leadership", dept_id, f"Leadership for {dept_name}."),
        ).lastrowid
        dept_head_id = make_user(dept_id, leadership_pod_id, head_title, ["team_lead"],
                                 manager_id=ceo_id, ai_band="Enabler", person_name=head_name)
        conn.execute("UPDATE pods SET lead_user_id = ? WHERE id = ?", (dept_head_id, leadership_pod_id))
        for pod_name, lead_name, lead_title, size, owns_workflow in pods_spec:
            pod_id = conn.execute(
                "INSERT INTO pods (name, department_id, description) VALUES (?, ?, ?)",
                (pod_name, dept_id, f"{pod_name} team within {dept_name}."),
            ).lastrowid
            pod_ids[pod_name] = pod_id

            lead_roles = ["team_lead"] + (["workflow_owner"] if owns_workflow else [])
            lead_id = make_user(
                dept_id, pod_id, lead_title, lead_roles, manager_id=dept_head_id,
                skills=rng.sample(FINTECH_SKILLS, k=2), person_name=lead_name,
            )
            conn.execute("UPDATE pods SET lead_user_id = ? WHERE id = ?", (lead_id, pod_id))
            pod_leads[pod_name] = lead_id

        dept_heads[dept_name] = dept_head_id

    # Place the named internal profiles in their chart-defined teams.
    conn.execute(
        "UPDATE users SET department_id = ?, pod_id = ?, manager_id = ? WHERE id = ?",
        (dept_ids["Client Technology"], pod_ids["Commercial Analytics & Tools"],
         pod_leads["Commercial Analytics & Tools"], original_users["priya"]),
    )
    conn.execute(
        "UPDATE users SET department_id = ?, pod_id = ?, manager_id = ? WHERE id IN (?, ?)",
        (dept_ids["Business AML"], pod_ids["Transaction Monitoring & Investigations"],
         pod_leads["Transaction Monitoring & Investigations"],
         original_users["jordan"], original_users["riley"]),
    )
    conn.execute(
        "UPDATE users SET manager_id = ? WHERE id = ?",
        (dept_heads["Global Core Operations"], original_users["dana"]),
    )

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

    kyc_owner = pod_leads["Client Due Diligence"]
    kyc_reviewer = dept_heads["Business AML"]
    add_workflow(
        "Customer KYC onboarding verification",
        "Verify new customer identity before activating a banking account.",
        "Business AML", "Client Due Diligence", kyc_owner, kyc_reviewer, "published", "high",
        [("Collect customer documents", "assistance_requested"), ("Verify identity documents", "no_current_need"),
         ("Screen against watchlists", "no_current_need"), ("Approve or escalate account", "no_current_need"),
         ("Notify customer of outcome", "no_current_need")],
    )

    add_workflow(
        "Enhanced due diligence for high-risk customers",
        "Deeper review triggered when a customer is flagged as elevated-risk during onboarding.",
        "Business AML", "Client Due Diligence", kyc_owner, kyc_reviewer, "draft", "high",
        [("Flag elevated-risk customer", "no_current_need"), ("Gather enhanced documentation", "assistance_requested"),
         ("Senior analyst review", "no_current_need"), ("Approve or reject account", "no_current_need")],
    )

    hr_owner = pod_leads["Recruitment"]
    add_workflow(
        "New employee onboarding",
        "Onboard a new hire from offer acceptance to first day readiness.",
        "People", "Recruitment", hr_owner, dept_heads["People"], "validated", "medium",
        [("Collect new hire documents", "monitoring"), ("Provision system access", "critical_internal_need"),
         ("Schedule orientation", "no_current_need"), ("Assign onboarding buddy", "no_current_need")],
    )

    legal_owner = pod_leads["Legal Counsel"]
    add_workflow(
        "Vendor onboarding & due diligence",
        "Onboard a new third-party vendor after a compliance review.",
        "Legal", "Legal Counsel", legal_owner, dept_heads["Legal"],
        "needs_owner_review", "medium",
        [("Collect vendor documents", "assistance_requested"), ("Perform due diligence check", "no_current_need"),
         ("Approve vendor contract", "no_current_need")],
    )

    fraud_owner = pod_leads["Fraud Investigations"]
    add_workflow(
        "Fraud alert triage",
        "Triage and act on real-time fraud detection alerts.",
        "Compliance", "Fraud Investigations", fraud_owner, dept_heads["Compliance"],
        "published", "high",
        [("Receive fraud alert", "no_current_need"), ("Investigate transaction pattern", "critical_internal_need"),
         ("Decide block or clear", "no_current_need"), ("Document decision", "no_current_need")],
    )

    chargeback_owner = pod_leads["Client Operations"]
    add_workflow(
        "Chargeback dispute resolution",
        "Investigate and respond to customer chargeback disputes.",
        "Global Core Operations", "Client Operations", chargeback_owner, dept_heads["Global Core Operations"],
        "published", "medium",
        [("Receive chargeback notice", "no_current_need"), ("Investigate transaction pattern", "assistance_requested"),
         ("Gather evidence", "no_current_need"), ("Submit response to card network", "no_current_need"),
         ("Document decision", "no_current_need")],
    )

    finance_owner = pod_leads["Accounting"]
    add_workflow(
        "Monthly financial close",
        "Close the books at month end and produce leadership reporting.",
        "Finance", "Accounting", finance_owner, dept_heads["Finance"], "published", "medium",
        [("Reconcile ledger accounts", "monitoring"), ("Review journal entries", "no_current_need"),
         ("Prepare close summary", "no_current_need"), ("Obtain sign-off", "no_current_need")],
    )

    settlement_owner = pod_leads["Client Operations"]
    add_workflow(
        "Payment settlement reconciliation",
        "Reconcile daily payment settlement records against the ledger.",
        "Global Core Operations", "Client Operations", settlement_owner, dept_heads["Global Core Operations"],
        "needs_owner_review", "medium",
        [("Export settlement records", "no_current_need"), ("Reconcile ledger accounts", "critical_internal_need"),
         ("Identify discrepancies", "assistance_requested"), ("Escalate unresolved items", "no_current_need")],
    )

    regreport_owner = pod_leads["Tax & Regulatory Reporting"]
    add_workflow(
        "Regulatory report submission",
        "Prepare and submit a periodic regulatory filing.",
        "Finance", "Tax & Regulatory Reporting", regreport_owner, dept_heads["Finance"], "validated", "high",
        [("Extract regulatory data", "no_current_need"), ("Validate data completeness", "monitoring"),
         ("Generate regulatory filing", "no_current_need"), ("Submit to regulator", "no_current_need"),
         ("Archive confirmation", "no_current_need")],
    )

    sre_owner = pod_leads["Cloud Engineering"]
    add_workflow(
        "Incident response runbook execution",
        "Respond to a production incident from detection to post-mortem.",
        "Technology Operations", "Cloud Engineering", sre_owner, dept_heads["Technology Operations"], "published", "low",
        [("Detect incident", "no_current_need"), ("Triage severity", "no_current_need"),
         ("Mitigate impact", "assistance_requested"), ("Conduct post-mortem", "no_current_need")],
    )

    marketing_owner = pod_leads["Marketing"]
    add_workflow(
        "Marketing campaign approval",
        "Take a campaign from brief to launch with the right sign-offs.",
        "Commercial", "Marketing", marketing_owner, dept_heads["Commercial"],
        "ai_generated_draft", "low",
        [("Draft campaign brief", "no_current_need"), ("Legal compliance review", "monitoring"),
         ("Design creative assets", "no_current_need"), ("Launch campaign", "no_current_need"),
         ("Measure performance", "assistance_requested")],
    )

    print(f"FlowMatch bulk org seeded: {len(dept_ids) + 1} new departments, "
          f"{conn.execute('SELECT COUNT(*) c FROM users').fetchone()['c']} total users.")
