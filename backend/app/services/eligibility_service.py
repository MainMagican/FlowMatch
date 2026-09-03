"""Hard eligibility filters, applied before any relevance scoring (design.md FR16).

A failed hard filter excludes the opportunity from the user's recommendations
entirely - it is never shown "anyway" with a caveat (spec section 12.3).
"""

import json


def check_eligibility(conn, opportunity, user):
    """Return (is_eligible: bool, reasons: list[str])."""
    reasons = []

    if opportunity["status"] != "published":
        reasons.append("Opportunity is not published.")

    prefs = conn.execute(
        "SELECT * FROM user_preferences WHERE user_id = ?", (user["id"],)
    ).fetchone()
    opted_in = bool(prefs["opted_into_discovery"]) if prefs else True
    if not opted_in:
        reasons.append("User has not opted into opportunity discovery.")

    if opportunity.get("mandatory_training"):
        completed = json.loads(user["completed_trainings"] or "[]")
        if opportunity["mandatory_training"] not in completed:
            reasons.append(
                "Mandatory training '{}' has not been completed.".format(opportunity["mandatory_training"])
            )

    required_auth = (opportunity.get("required_authorization") or "").strip()
    # "manager_sign_off" is satisfied BY the team-lead approval step itself
    # (spec section 12.3 approval workflow) - it must not pre-block express
    # interest, otherwise nobody could ever reach the approval that grants it.
    if required_auth and required_auth.lower() not in ("none", "manager_sign_off"):
        granted = json.loads(user["granted_access"] or "[]")
        if required_auth not in granted:
            reasons.append(
                "Required access '{}' has not been granted.".format(required_auth)
            )

    if opportunity.get("sensitivity") in (None, "unknown"):
        reasons.append("Sensitivity is unknown; cannot confirm this employee may participate.")

    if not opportunity.get("reviewer_id"):
        reasons.append("No human reviewer is defined for this opportunity.")

    return (len(reasons) == 0, reasons)
