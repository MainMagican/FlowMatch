"""SQLite schema and connection helper for the FlowMatch backend.

Design note (docs/DECISIONS.md #2): stdlib sqlite3 is used instead of a
managed relational database because this sandbox has no Docker/DB server
available. The schema below covers every entity listed in
docs/features/flowmatch/design.md Technical Considerations / the source
spec section 21.
"""

import contextlib
import sqlite3

from app.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS pods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    department_id INTEGER NOT NULL REFERENCES departments(id),
    description TEXT,
    lead_user_id INTEGER REFERENCES users(id)  -- the pod's team lead ("boss" for org-tree purposes)
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    department_id INTEGER REFERENCES departments(id),
    pod_id INTEGER REFERENCES pods(id),
    manager_id INTEGER REFERENCES users(id),  -- direct manager, for the company-wide org tree
    role_title TEXT,
    avatar_emoji TEXT DEFAULT '🙂',
    completed_trainings TEXT DEFAULT '[]',   -- JSON list of training codes
    granted_access TEXT DEFAULT '[]',        -- JSON list of access/workspace codes
    profile_last_reviewed TEXT
);

-- A user may hold multiple roles (Contributor, Team Lead, Workflow Owner,
-- Reviewer, Mentor, Administrator). Enforced server-side via require_role().
CREATE TABLE IF NOT EXISTS user_roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    role TEXT NOT NULL,
    UNIQUE(user_id, role)
);

CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    is_custom INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user_skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    skill_id INTEGER NOT NULL REFERENCES skills(id),
    proficiency TEXT NOT NULL,  -- Awareness/Working knowledge/Independent/Advanced/Coach
    evidence TEXT,
    UNIQUE(user_id, skill_id)
);

CREATE TABLE IF NOT EXISTS learning_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    skill_id INTEGER NOT NULL REFERENCES skills(id),
    goal_type TEXT NOT NULL,  -- learn / practise / master
    UNIQUE(user_id, skill_id, goal_type)
);

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    opportunity_types TEXT DEFAULT '[]',   -- JSON list
    declared_availability TEXT DEFAULT 'Unspecified',
    ai_support_band TEXT DEFAULT 'Explorer',  -- Explorer/Practitioner/Builder/Enabler
    visibility TEXT DEFAULT 'visible_to_org',
    opted_into_discovery INTEGER NOT NULL DEFAULT 1,
    ai_readiness_score INTEGER  -- 0-10 self-evaluation, nullable until the person fills it in
);

CREATE TABLE IF NOT EXISTS workflows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    department_id INTEGER REFERENCES departments(id),
    pod_id INTEGER REFERENCES pods(id),
    business_purpose TEXT,
    owner_id INTEGER REFERENCES users(id),
    reviewer_id INTEGER REFERENCES users(id),
    source_type TEXT NOT NULL,  -- pasted_text / manual / ai_draft
    source_text TEXT,
    validation_status TEXT NOT NULL DEFAULT 'draft',
    -- draft / ai_generated_draft / needs_owner_review / validated / published / archived
    sensitivity TEXT DEFAULT 'unknown',
    comparison_permission INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    last_reviewed_at TEXT
);

CREATE TABLE IF NOT EXISTS workflow_stages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id INTEGER NOT NULL REFERENCES workflows(id),
    name TEXT NOT NULL,
    description TEXT,
    sequence INTEGER NOT NULL,
    activities TEXT,
    responsible_role TEXT,
    inputs TEXT,
    outputs TEXT,
    systems TEXT,
    handoffs TEXT,
    decision_points TEXT,
    effort TEXT,
    frequency TEXT,
    backlog_status TEXT DEFAULT 'no_current_need',
    -- no_current_need / monitoring / assistance_requested / critical_internal_need
    bottleneck TEXT,
    automation_maturity TEXT,
    existing_automation TEXT,
    sensitivity TEXT DEFAULT 'unknown',
    controls TEXT,
    access_requirements TEXT,
    suitable_shadowing INTEGER NOT NULL DEFAULT 0,
    suitable_bounded_help INTEGER NOT NULL DEFAULT 0,
    suitable_process_discovery INTEGER NOT NULL DEFAULT 0,
    suitable_automation_reuse INTEGER NOT NULL DEFAULT 0,
    required_reviewer_id INTEGER REFERENCES users(id),
    last_validated_at TEXT,
    ai_generated INTEGER NOT NULL DEFAULT 0,
    uncertain_fields TEXT DEFAULT '[]'  -- JSON list of field names AI was unsure about
);

CREATE TABLE IF NOT EXISTS reusable_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id INTEGER NOT NULL REFERENCES workflows(id),
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    description TEXT,
    owner_id INTEGER REFERENCES users(id),
    approved_users TEXT DEFAULT '[]',
    reuse_permission TEXT DEFAULT 'requires_review',
    documentation_status TEXT DEFAULT 'draft',
    dependencies TEXT,
    required_systems TEXT,
    known_constraints TEXT,
    risk_classification TEXT DEFAULT 'unknown',
    review_date TEXT,
    transfer_contact TEXT
);

CREATE TABLE IF NOT EXISTS workflow_similarities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stage_a_id INTEGER NOT NULL REFERENCES workflow_stages(id),
    stage_b_id INTEGER NOT NULL REFERENCES workflow_stages(id),
    shared_characteristics TEXT,
    differences TEXT,
    confidence TEXT,
    requires_owner_confirmation INTEGER NOT NULL DEFAULT 1,
    recommendation TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id INTEGER REFERENCES workflows(id),
    stage_id INTEGER REFERENCES workflow_stages(id),
    title TEXT NOT NULL,
    problem_statement TEXT,
    opportunity_type TEXT NOT NULL,
    desired_outcome TEXT,
    definition_of_done TEXT,
    expected_deliverable TEXT,
    estimated_effort TEXT,
    required_skills TEXT DEFAULT '[]',      -- JSON list of skill names
    learnable_skills TEXT DEFAULT '[]',      -- JSON list of skill names
    required_ai_band TEXT,
    required_systems TEXT,
    required_authorization TEXT,
    mandatory_training TEXT,                -- training code, or NULL
    sensitivity TEXT,
    approved_ai_assistance TEXT,
    reusable_assets TEXT DEFAULT '[]',
    owner_id INTEGER REFERENCES users(id),
    reviewer_id INTEGER REFERENCES users(id),
    mentor_available INTEGER NOT NULL DEFAULT 0,
    escalation_points TEXT,
    start_conditions TEXT,
    participation_boundary TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    share_scope TEXT NOT NULL DEFAULT 'company_wide',  -- company_wide / department_only
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS expressions_of_interest (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER NOT NULL REFERENCES opportunities(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'pending',
    -- pending / accepted_by_contributor / approved_by_owner / declined
    created_at TEXT NOT NULL
);

-- A contributor can flag their manager/team-lead about wanting to take an
-- opportunity, so the manager can see their team's shadowing/opportunity
-- interest even when the manager isn't the opportunity owner. This is a
-- visibility/heads-up mechanism only - it never replaces the opportunity
-- owner's formal mutual-acceptance approval (design.md FR20).
CREATE TABLE IF NOT EXISTS manager_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER NOT NULL REFERENCES opportunities(id),
    contributor_id INTEGER NOT NULL REFERENCES users(id),
    manager_id INTEGER NOT NULL REFERENCES users(id),
    note TEXT,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending / acknowledged
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS match_recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER NOT NULL REFERENCES opportunities(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS match_explanation_components (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL REFERENCES match_recommendations(id),
    component_name TEXT NOT NULL,
    detail TEXT,
    matched INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS workspaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER NOT NULL REFERENCES opportunities(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    content TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL REFERENCES submissions(id),
    reviewer_id INTEGER NOT NULL REFERENCES users(id),
    decision TEXT NOT NULL,  -- accepted / changes_requested / rejected
    reason TEXT,
    delivered_expected_result INTEGER,
    appropriate_for_reuse INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS learning_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER NOT NULL REFERENCES opportunities(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    note TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id INTEGER REFERENCES users(id),
    actor_role TEXT,
    action TEXT NOT NULL,
    object_type TEXT,
    object_id INTEGER,
    ai_involved INTEGER NOT NULL DEFAULT 0,
    human_approved INTEGER NOT NULL DEFAULT 0,
    timestamp TEXT NOT NULL
);
"""


def init_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _dict_factory(cursor, row):
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}


@contextlib.contextmanager
def db_session():
    """Context manager yielding a sqlite3 connection with row-as-dict access.

    Commits on clean exit, rolls back on exception, always closes.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = _dict_factory
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
