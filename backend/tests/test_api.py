"""Integration tests for the FlowMatch backend covering the full spec section
19 demo journey plus the required "blocked" paths (design.md Success Metrics)."""

from conftest import login, auth_headers


def test_demo_users_seeded(client):
    users = client.get("/api/auth/demo-users").get_json()
    names = {u["name"] for u in users}
    assert "Priya Sharma" in names
    assert "Morgan Taylor" in names
    assert "Casey Nguyen" in names


def test_profile_get_and_update(client):
    token, _ = login(client, "morgan.taylor@flowmatch.demo", "contributor")
    resp = client.get("/api/profile/me", headers=auth_headers(token))
    assert resp.status_code == 200
    profile = resp.get_json()
    assert profile["ai_support_band"] == "Practitioner"

    update = client.put(
        "/api/profile/me",
        headers=auth_headers(token),
        json={"ai_support_band": "Builder", "opportunity_types": ["process_discovery"]},
    )
    assert update.status_code == 200
    assert update.get_json()["ai_support_band"] == "Builder"


def test_no_endpoint_exposes_a_combined_score(client):
    """design.md FR6/FR19: no endpoint should return an employee ranking or
    a single combined numeric 'score' field."""
    token, _ = login(client, "morgan.taylor@flowmatch.demo", "contributor")
    resp = client.get("/api/matches/recommendations", headers=auth_headers(token))
    assert resp.status_code == 200
    for rec in resp.get_json():
        assert "score" not in rec
        assert "rank" not in rec
        assert "_sort_score" not in rec


def test_blocked_publish_path(client):
    """design.md FR14: publish is blocked with structured reasons when the
    seeded incomplete opportunity (missing reviewer/definition-of-done/
    sensitivity) is published."""
    token, _ = login(client, "priya.sharma@flowmatch.demo", "team_lead")
    opps = client.get("/api/opportunities", headers=auth_headers(token)).get_json()
    incomplete = next(o for o in opps if o["title"].startswith("Shadow the exception-report"))
    resp = client.post(
        "/api/opportunities/{}/publish".format(incomplete["id"]), headers=auth_headers(token)
    )
    assert resp.status_code == 422
    body = resp.get_json()
    assert len(body["reasons"]) >= 3


def test_blocked_match_path(client):
    """design.md FR16: Casey Nguyen lacks required_authorization for the
    published opportunity, so it must never appear in her recommendations."""
    token, _ = login(client, "casey.nguyen@flowmatch.demo", "contributor")
    resp = client.get("/api/matches/recommendations", headers=auth_headers(token))
    assert resp.status_code == 200
    titles = [r["opportunity"]["title"] for r in resp.get_json()]
    assert "Assess and document exception-report standardization for automation" not in titles

    check = client.get(
        "/api/matches/eligibility-check/1", headers=auth_headers(token)
    )
    # opportunity id 1 is the fully-specified published one
    assert check.status_code == 200
    check_body = check.get_json()
    assert check_body["eligible"] is False
    assert any("access" in r.lower() for r in check_body["reasons"])


def test_full_journey_match_to_review_and_feedback(client):
    """End-to-end: Morgan is eligible, gets an explained recommendation,
    expresses interest, Priya approves, Morgan opens the workspace and
    submits, Riley reviews, Morgan records learning feedback."""
    morgan_token, morgan_id = login(client, "morgan.taylor@flowmatch.demo", "contributor")
    priya_token, _ = login(client, "priya.sharma@flowmatch.demo", "team_lead")
    riley_token, _ = login(client, "riley.brooks@flowmatch.demo", "reviewer")

    recs = client.get("/api/matches/recommendations", headers=auth_headers(morgan_token)).get_json()
    assert len(recs) >= 1
    rec = next(r for r in recs if r["opportunity"]["title"].startswith("Assess and document"))
    assert rec["explanation"]["headline"].startswith("Recommended because")
    opportunity_id = rec["opportunity"]["id"]

    express = client.post(
        "/api/matches/{}/express-interest".format(opportunity_id), headers=auth_headers(morgan_token)
    )
    assert express.status_code == 200

    approve = client.post(
        "/api/matches/{}/approve".format(opportunity_id), headers=auth_headers(priya_token)
    )
    assert approve.status_code == 200
    assert approve.get_json()["status"] == "active"

    workspace_resp = client.get(
        "/api/workspaces/by-opportunity/{}".format(opportunity_id), headers=auth_headers(morgan_token)
    )
    assert workspace_resp.status_code == 200
    workspace_body = workspace_resp.get_json()
    assert workspace_body["guidance"]["requires_human_review"] is True
    workspace_id = workspace_body["workspace"]["id"]

    submit = client.post(
        "/api/workspaces/{}/submissions".format(workspace_id),
        headers=auth_headers(morgan_token),
        json={"content": "Documented 6 manual steps; recommend evaluating the BI automation template."},
    )
    assert submit.status_code == 201
    submission_id = submit.get_json()["id"]

    review = client.post(
        "/api/reviews/submissions/{}".format(submission_id),
        headers=auth_headers(riley_token),
        json={"decision": "accepted", "delivered_expected_result": True, "appropriate_for_reuse": True},
    )
    assert review.status_code == 201

    feedback = client.post(
        "/api/feedback/opportunities/{}".format(opportunity_id),
        headers=auth_headers(morgan_token),
        json={"note": "Learned the basics of Power Automate mapping and process discovery."},
    )
    assert feedback.status_code == 201
    assert "rating" not in feedback.get_json()
    assert "score" not in feedback.get_json()


def test_workflow_validation_lifecycle_and_role_enforcement(client):
    """design.md FR9: only workflow_owner may validate/publish; non-owners
    are rejected server-side."""
    jordan_token, _ = login(client, "jordan.lee@flowmatch.demo", "workflow_owner")
    morgan_token, _ = login(client, "morgan.taylor@flowmatch.demo", "contributor")

    workflows = client.get("/api/workflows", headers=auth_headers(jordan_token)).get_json()
    workflow = next(w for w in workflows if w["name"].startswith("Prepare weekly"))
    assert workflow["validation_status"] == "published"

    # A contributor cannot transition workflow validation status.
    denied = client.post(
        "/api/workflows/{}/transition".format(workflow["id"]),
        headers=auth_headers(morgan_token),
        json={"target_status": "archived"},
    )
    assert denied.status_code == 403


def test_similarity_and_reuse_recommendation(client):
    token, _ = login(client, "dana.kim@flowmatch.demo", "workflow_owner")
    workflows = client.get("/api/workflows", headers=auth_headers(token)).get_json()
    wf1 = next(w for w in workflows if w["name"].startswith("Prepare weekly"))
    wf2 = next(w for w in workflows if w["name"].startswith("Prepare monthly"))
    stage_a = next(s for s in wf1["stages"] if s["name"] == "Standardize categories")
    stage_b = next(s for s in wf2["stages"] if "Standardize categories" in s["name"])

    resp = client.post(
        "/api/similarity/compare",
        headers=auth_headers(token),
        json={"stage_a_id": stage_a["id"], "stage_b_id": stage_b["id"]},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["requires_owner_confirmation"] is True
    assert len(body["reuse_recommendations"]) > 0
    assert len(body["reusable_assets_found"]) > 0


def test_extraction_service_marks_ai_generated_and_uncertain_fields(client):
    token, _ = login(client, "priya.sharma@flowmatch.demo", "team_lead")
    resp = client.post(
        "/api/workflows",
        headers=auth_headers(token),
        json={
            "name": "Test intake workflow",
            "source_type": "pasted_text",
            "source_text": "Do the first thing.\nDo the second thing.",
            "owner_id": 1,
        },
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["validation_status"] == "ai_generated_draft"
    assert len(body["stages"]) == 2
    assert body["stages"][0]["ai_generated"] == 1
    assert len(body["stages"][0]["uncertain_fields"]) > 0
