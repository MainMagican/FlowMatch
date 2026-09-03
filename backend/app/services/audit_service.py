"""Audit trail helper (design.md FR28, spec section 15.13/17.6).

Every significant action records who did it, in which role, what happened,
whether AI was involved, and whether a human approved it. Full sensitive
source text is never logged - only structured metadata.
"""

from datetime import datetime, timezone


def audit_event(conn, user, action, object_type=None, object_id=None, ai_involved=False, human_approved=False):
    conn.execute(
        """INSERT INTO audit_events
           (actor_user_id, actor_role, action, object_type, object_id, ai_involved, human_approved, timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            user["id"] if user else None,
            user.get("active_role") if user else None,
            action,
            object_type,
            object_id,
            1 if ai_involved else 0,
            1 if human_approved else 0,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
