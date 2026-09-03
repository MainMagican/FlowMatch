/* Thin fetch() wrapper for the FlowMatch API. Bearer token in localStorage
   (docs/DECISIONS.md #3 - dev-mode identity, no real SSO). */

const API_BASE = "http://127.0.0.1:8100/api";

const Api = {
  token() {
    return localStorage.getItem("flowmatch_token");
  },
  setToken(token) {
    localStorage.setItem("flowmatch_token", token);
  },
  clearToken() {
    localStorage.removeItem("flowmatch_token");
  },
  setUser(user) {
    localStorage.setItem("flowmatch_user", JSON.stringify(user));
  },
  getUser() {
    const raw = localStorage.getItem("flowmatch_user");
    return raw ? JSON.parse(raw) : null;
  },

  async _request(method, path, body) {
    const headers = { "Content-Type": "application/json" };
    const token = this.token();
    if (token) headers["Authorization"] = "Bearer " + token;
    const resp = await fetch(API_BASE + path, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    let data = null;
    try {
      data = await resp.json();
    } catch (e) {
      data = null;
    }
    if (!resp.ok) {
      const err = new Error((data && data.error) || "Request failed");
      err.reasons = data && data.reasons;
      err.status = resp.status;
      throw err;
    }
    return data;
  },

  get(path) { return this._request("GET", path); },
  post(path, body) { return this._request("POST", path, body); },
  put(path, body) { return this._request("PUT", path, body); },
  del(path) { return this._request("DELETE", path); },

  // Auth
  demoUsers() { return this.get("/auth/demo-users"); },
  login(userId, role) { return this.post("/auth/login", { user_id: userId, role }); },
  me() { return this.get("/auth/me"); },

  // Org
  departments() { return this.get("/org/departments"); },
  podMembers(podId) { return this.get(`/org/pods/${podId}/members`); },
  myOrg() { return this.get("/org/me"); },
  orgForUser(userId) { return this.get(`/org/user/${userId}`); },
  companyTree() { return this.get("/org/tree"); },
  aiReadinessSummary() { return this.get("/org/ai-readiness-summary"); },

  // Profile
  getProfile() { return this.get("/profile/me"); },
  updateProfile(body) { return this.put("/profile/me", body); },
  skillsCatalogue() { return this.get("/profile/skills-catalogue"); },
  skillsOverview() { return this.get("/profile/skills-overview"); },

  // Workflows
  listWorkflows() { return this.get("/workflows"); },
  getWorkflow(id) { return this.get(`/workflows/${id}`); },
  createWorkflow(body) { return this.post("/workflows", body); },
  editWorkflow(id, body) { return this.put(`/workflows/${id}`, body); },
  editStage(workflowId, stageId, body) { return this.put(`/workflows/${workflowId}/stages/${stageId}`, body); },
  addStage(workflowId, body) { return this.post(`/workflows/${workflowId}/stages`, body); },
  deleteStage(workflowId, stageId) { return this.del(`/workflows/${workflowId}/stages/${stageId}`); },
  transitionWorkflow(id, targetStatus) { return this.post(`/workflows/${id}/transition`, { target_status: targetStatus }); },

  // Backlog
  setBacklogSignal(stageId, backlogStatus) { return this.put(`/backlog/stages/${stageId}`, { backlog_status: backlogStatus }); },
  backlogDashboard() { return this.get("/backlog/dashboard"); },

  // Opportunities
  listOpportunities() { return this.get("/opportunities"); },
  pendingApproval() { return this.get("/opportunities/pending-my-approval"); },
  myDrafts() { return this.get("/opportunities/my-drafts"); },
  teachMatches() { return this.get("/opportunities/teach-matches"); },
  getOpportunity(id) { return this.get(`/opportunities/${id}`); },
  createOpportunity(body) { return this.post("/opportunities", body); },
  updateOpportunity(id, body) { return this.put(`/opportunities/${id}`, body); },
  publishOpportunity(id) { return this.post(`/opportunities/${id}/publish`); },
  setOpportunityStatus(id, status) { return this.post(`/opportunities/${id}/status`, { status }); },

  // Matches
  recommendations() { return this.get("/matches/recommendations"); },
  eligibilityCheck(opportunityId) { return this.get(`/matches/eligibility-check/${opportunityId}`); },
  expressInterest(opportunityId) { return this.post(`/matches/${opportunityId}/express-interest`); },
  declineInterest(opportunityId) { return this.post(`/matches/${opportunityId}/decline`); },
  approveInterest(opportunityId) { return this.post(`/matches/${opportunityId}/approve`); },
  myManager() { return this.get("/matches/my-manager"); },
  requestTlSupport(opportunityId, note) { return this.post(`/matches/${opportunityId}/request-tl-support`, { note }); },
  teamRequests() { return this.get("/matches/team-requests"); },
  acknowledgeTeamRequest(requestId) { return this.post(`/matches/team-requests/${requestId}/acknowledge`); },

  // Similarity & reuse
  listReusableAssets() { return this.get("/reusable-assets"); },
  createReusableAsset(body) { return this.post("/reusable-assets", body); },
  compareStages(stageAId, stageBId) { return this.post("/similarity/compare", { stage_a_id: stageAId, stage_b_id: stageBId }); },
  autoScanSimilarities() { return this.get("/similarity/auto-scan"); },

  // Workspace / review / feedback
  getWorkspace(opportunityId) { return this.get(`/workspaces/by-opportunity/${opportunityId}`); },
  submitOutput(workspaceId, content) { return this.post(`/workspaces/${workspaceId}/submissions`, { content }); },
  reviewSubmission(submissionId, body) { return this.post(`/reviews/submissions/${submissionId}`, body); },
  recordFeedback(opportunityId, note) { return this.post(`/feedback/opportunities/${opportunityId}`, { note }); },

  // Audit
  auditFeed() { return this.get("/audit"); },
};
