/* FlowMatch frontend view-router + state logic. Vanilla JS, no build step
   (docs/DECISIONS.md #2). Every AI-generated / recommended element is
   visibly badged per design.md section 6 / spec section 17.5. */

const state = {
  user: null,
  view: "login",
  profileDraft: null,
};

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function esc(str) {
  return String(str ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function fmtLabel(str) {
  return String(str ?? "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/* ---------------- View routing ---------------- */

function showView(name) {
  state.view = name;
  $$(".view").forEach((v) => v.classList.add("hidden"));
  const el = document.getElementById(`view-${name}`);
  if (el) el.classList.remove("hidden");
  $$(".nav-btn").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
}

async function goto(name, opts = {}, navOptions = {}) {
  showView(name);
  try {
    if (name === "dashboard") await renderDashboard();
    else if (name === "org") await renderOrg();
    else if (name === "profile") await renderProfile();
    else if (name === "workflows") await renderWorkflows();
    else if (name === "workflow-detail") await renderWorkflowDetail(opts.id);
    else if (name === "opportunities") await renderOpportunities();
    else if (name === "opportunity-detail") await renderOpportunityDetail(opts.id);
    else if (name === "workspace") await renderWorkspace(opts.opportunityId);
    else if (name === "audit") await renderAudit();
  } catch (err) {
    console.error(err);
    alert(err.message || "Something went wrong.");
  }
  // Keep the browser Back/Forward buttons inside the app instead of leaving
  // it entirely (there's no server-side routing, so without this the
  // browser has nowhere else to go but a raw API response or blank page).
  if (!navOptions.skipHistory) {
    history.pushState({ view: name, opts }, "", "#" + name);
  }
}

window.addEventListener("popstate", (e) => {
  if (!state.user) return;
  const target = e.state || { view: "dashboard", opts: {} };
  // If Back is pressed all the way to the pre-login history entry while
  // still signed in, land on the dashboard instead of showing the bare
  // login form underneath the nav bar.
  if (target.view === "login") { goto("dashboard", {}, { skipHistory: true }); return; }
  goto(target.view, target.opts || {}, { skipHistory: true });
});

/* Sub-tab bars within a view (e.g. Workflows: Library / Similarity,
   Opportunities: Marketplace / Backlog) - one tiny generic handler covers
   both instead of separate top-level nav entries. */
const SUBTAB_LOADERS = {
  "wf-library": renderWorkflows,
  "wf-similarity": renderSimilarityShell,
  "opp-marketplace": renderOpportunities,
  "opp-backlog": renderBacklog,
};

document.addEventListener("click", (e) => {
  const navBtn = e.target.closest(".nav-btn");
  if (navBtn) goto(navBtn.dataset.view);
  const backBtn = e.target.closest(".back-btn");
  if (backBtn) goto(backBtn.dataset.back);
  const subtabBtn = e.target.closest(".subtab-btn");
  if (subtabBtn) {
    const bar = subtabBtn.closest(".subtab-bar");
    bar.querySelectorAll(".subtab-btn").forEach((b) => b.classList.toggle("active", b === subtabBtn));
    bar.parentElement.querySelectorAll(".subtab-panel").forEach((p) => p.classList.add("hidden"));
    const panel = document.getElementById(`panel-${subtabBtn.dataset.subtab}`);
    if (panel) panel.classList.remove("hidden");
    const loader = SUBTAB_LOADERS[subtabBtn.dataset.subtab];
    if (loader) {
      try { Promise.resolve(loader()).catch((err) => { console.error(err); alert(err.message || "Something went wrong."); }); }
      catch (err) { console.error(err); alert(err.message || "Something went wrong."); }
    }
  }
});

/* ---------------- Login ---------------- */

const FEATURED_PROFILE_EMAILS = [
  "ainars.djatlevskis@flowmatch.demo", "reanne.lord-simpson@flowmatch.demo",
  "hamida.khanom@flowmatch.demo", "claus.rasmus.hjort@flowmatch.demo",
  "david.gluschitz@flowmatch.demo", "thomas.nielsen@flowmatch.demo",
  "flowmatch.admin@flowmatch.demo",
];

let allDemoUsers = [];

async function initLogin() {
  allDemoUsers = await Api.demoUsers();
  renderLoginList("");
  $("#user-search").addEventListener("input", (e) => renderLoginList(e.target.value));
}

function renderLoginList(query) {
  const list = $("#demo-user-list");
  const q = query.trim().toLowerCase();
  const matches = (u) => !q || [u.name, u.role_title, u.department_name, u.pod_name].some(
    (f) => (f || "").toLowerCase().includes(q)
  );

  const featured = allDemoUsers.filter((u) => FEATURED_PROFILE_EMAILS.includes(u.email) && matches(u));
  const rest = allDemoUsers.filter((u) => !FEATURED_PROFILE_EMAILS.includes(u.email) && matches(u))
    .slice(0, 40);

  function userButton(u, role) {
    const btn = document.createElement("button");
    btn.className = "demo-user-btn";
    btn.innerHTML = `
      <span>
        <div class="u-name">${u.avatar_emoji || "👤"} ${esc(u.name)}</div>
        <div class="u-role">${esc(u.role_title || "")} · ${esc(u.department_name || u.pod_name || "")}</div>
      </span>
      <span class="pill">${esc(fmtLabel(role))}</span>`;
    btn.addEventListener("click", () => doLogin(u.id, role));
    return btn;
  }

  list.innerHTML = "";
  if (featured.length) {
    const h = document.createElement("div");
    h.className = "muted";
    h.style.cssText = "font-size:0.78rem; font-weight:700; text-transform:uppercase; margin:6px 0 2px";
    h.textContent = "Featured profiles";
    list.appendChild(h);
    featured.forEach((u) => (u.roles || []).forEach((role) => list.appendChild(userButton(u, role))));
  }
  if (rest.length) {
    const h = document.createElement("div");
    h.className = "muted";
    h.style.cssText = "font-size:0.78rem; font-weight:700; text-transform:uppercase; margin:12px 0 2px";
    h.textContent = `All employees (${allDemoUsers.length - featured.length} total, showing ${rest.length})`;
    list.appendChild(h);
    rest.forEach((u) => (u.roles || []).forEach((role) => list.appendChild(userButton(u, role))));
  }
  if (!featured.length && !rest.length) {
    list.innerHTML = `<p class="muted">No employees match "${esc(query)}".</p>`;
  }
}

async function doLogin(userId, role) {
  try {
    const { token, user } = await Api.login(userId, role);
    Api.setToken(token);
    Api.setUser(user);
    state.user = user;
    onAuthenticated();
  } catch (err) {
    $("#login-error").textContent = err.message;
  }
}

function onAuthenticated() {
  $("#main-nav").classList.remove("hidden");
  $("#identity-box").classList.remove("hidden");
  $("#identity-avatar").textContent = state.user.avatar_emoji || "👤";
  $("#identity-role-badge").textContent = fmtLabel(state.user.active_role);
  $("#identity-name").textContent = state.user.name;
  goto("dashboard");
  refreshApprovalsBell();
  if (state.approvalsBellTimer) clearInterval(state.approvalsBellTimer);
  state.approvalsBellTimer = setInterval(refreshApprovalsBell, 45000);
}

async function refreshApprovalsBell() {
  if (!state.user) return;
  const countEl = $("#approvals-bell-count");
  try {
    const drafts = await Api.pendingApproval();
    state.pendingApprovals = drafts;
    if (drafts.length) {
      countEl.textContent = drafts.length > 9 ? "9+" : String(drafts.length);
      countEl.classList.remove("hidden");
    } else {
      countEl.classList.add("hidden");
    }
    renderApprovalsBellList(drafts);
  } catch (err) {
    countEl.classList.add("hidden");
  }
}

function renderApprovalsBellList(drafts) {
  const el = $("#approvals-bell-list");
  el.innerHTML = drafts.length
    ? drafts.map((o) => {
        const isInterest = o.approval_kind === "interest_approval";
        const person = isInterest ? o.contributor : o.owner;
        const verb = isInterest ? "wants to help with" : "drafted";
        return `
        <div class="approvals-bell-item" data-opp-id="${o.id}">
          <strong>${person?.avatar_emoji || "👤"} ${esc(person?.name || "Someone")}</strong> ${verb}
          <div class="approvals-bell-item-title">${esc(o.title)}</div>
          <span class="pill">${esc(fmtLabel(o.opportunity_type))}</span>
        </div>`;
      }).join("")
    : `<p class="muted">Nothing waiting on you right now.</p>`;
}

$("#approvals-bell-btn").addEventListener("click", (e) => {
  e.stopPropagation();
  $("#approvals-bell-dropdown").classList.toggle("hidden");
});

document.addEventListener("click", (e) => {
  const item = e.target.closest(".approvals-bell-item");
  if (item) {
    goto("opportunity-detail", { id: Number(item.dataset.oppId) });
    $("#approvals-bell-dropdown").classList.add("hidden");
    return;
  }
  if (!e.target.closest(".approvals-bell")) {
    $("#approvals-bell-dropdown").classList.add("hidden");
  }
});

$("#identity-menu-btn").addEventListener("click", (e) => {
  e.stopPropagation();
  $("#identity-menu-dropdown").classList.toggle("hidden");
});

document.addEventListener("click", (e) => {
  const menuItem = e.target.closest(".menu-item");
  if (menuItem) {
    goto(menuItem.dataset.view);
    $("#identity-menu-dropdown").classList.add("hidden");
    return;
  }
  if (!e.target.closest(".identity-menu")) {
    $("#identity-menu-dropdown").classList.add("hidden");
  }
});

$("#logout-btn").addEventListener("click", () => {
  Api.clearToken();
  state.user = null;
  if (state.approvalsBellTimer) clearInterval(state.approvalsBellTimer);
  $("#main-nav").classList.add("hidden");
  $("#identity-box").classList.add("hidden");
  goto("login");
});

/* ---------------- Dashboard ---------------- */

async function renderDashboard() {
  $("#dash-name").textContent = state.user.name;
  $("#dash-role").textContent = fmtLabel(state.user.active_role);

  const recEl = $("#dash-recommendations");
  const activeEl = $("#dash-active");
  const goalsEl = $("#dash-goals");
  const wfEl = $("#dash-workflows");
  recEl.innerHTML = activeEl.innerHTML = goalsEl.innerHTML = wfEl.innerHTML = `<p class="muted">Loading…</p>`;

  const [recs, profile, workflows, opportunities] = await Promise.all([
    Api.recommendations().catch(() => []),
    Api.getProfile().catch(() => null),
    Api.listWorkflows().catch(() => []),
    Api.listOpportunities().catch(() => []),
  ]);

  recEl.innerHTML = recs.length
    ? recs.slice(0, 4).map((r) => `
        <div class="list-item">
          <strong>${esc(r.opportunity.title)}</strong> <span class="badge ai">AI match</span>
          <p class="muted" style="margin:6px 0 8px">${esc(r.explanation.headline)}</p>
          <button class="secondary" onclick="goto('opportunity-detail', {id: ${r.opportunity.id}})">View</button>
        </div>`).join("")
    : `<p class="muted">No eligible recommendations yet — check your profile and opted-in preferences.</p>`;

  activeEl.innerHTML = opportunities.filter((o) => ["active", "pending_mutual_acceptance", "submitted_for_review"].includes(o.status)).length
    ? opportunities.filter((o) => ["active", "pending_mutual_acceptance", "submitted_for_review"].includes(o.status)).map((o) => `
        <div class="list-item">
          <strong>${esc(o.title)}</strong> <span class="pill">${esc(fmtLabel(o.status))}</span>
          <div style="margin-top:6px"><button class="secondary" onclick="goto('opportunity-detail', {id: ${o.id}})">Open</button></div>
        </div>`).join("")
    : `<p class="muted">Nothing active right now.</p>`;

  goalsEl.innerHTML = profile && profile.learning_goals.length
    ? profile.learning_goals.map((g) => `<span class="pill">${esc(g.name)} · ${esc(fmtLabel(g.goal_type))}</span> `).join("")
    : `<p class="muted">No learning goals set. Add some in your profile.</p>`;

  wfEl.innerHTML = workflows.length
    ? workflows.slice(0, 5).map((w) => `
        <div class="list-item">
          <strong>${esc(w.name)}</strong> <span class="pill">${esc(fmtLabel(w.validation_status))}</span>
          <div style="margin-top:6px"><button class="secondary" onclick="goto('workflow-detail', {id: ${w.id}})">View</button></div>
        </div>`).join("")
    : `<p class="muted">No workflows visible yet.</p>`;

  await renderMyDrafts();
  await renderPendingApproval();
  await renderTeamRequests();
}

async function renderMyDrafts() {
  const card = $("#dash-my-drafts-card");
  const el = $("#dash-my-drafts");
  try {
    const drafts = await Api.myDrafts();
    if (!drafts.length) {
      card.classList.add("hidden");
      return;
    }
    card.classList.remove("hidden");
    el.innerHTML = drafts.map((o) => `
      <div class="list-item">
        <strong>${esc(o.title)}</strong>
        <span class="pill">${esc(fmtLabel(o.opportunity_type))}</span>
        <p class="muted" style="margin:6px 0 8px">
          ⏳ Pending with ${o.approver ? `your TL <strong>${o.approver.avatar_emoji || "👤"} ${esc(o.approver.name)}</strong>` : "<strong>no one yet</strong> — no reviewer could be resolved"}
        </p>
        <button class="secondary" onclick="goto('opportunity-detail', {id: ${o.id}})">View</button>
      </div>`).join("");
  } catch (err) {
    card.classList.add("hidden");
  }
}

async function renderPendingApproval() {
  const card = $("#dash-pending-approval-card");
  const el = $("#dash-pending-approval");
  try {
    const drafts = await Api.pendingApproval();
    if (!drafts.length) {
      card.classList.add("hidden");
      return;
    }
    card.classList.remove("hidden");
    el.innerHTML = drafts.map((o) => `
      <div class="list-item">
        <strong>${o.owner?.avatar_emoji || "👤"} ${esc(o.owner?.name || "Someone")}</strong>
        <span class="muted">drafted</span>
        <strong>${esc(o.title)}</strong>
        <span class="pill">${esc(fmtLabel(o.opportunity_type))}</span>
        <span class="pill ${o.share_scope === "department_only" ? "" : "accent"}">${o.share_scope === "department_only" ? "Department only" : "Company-wide"}</span>
        <div style="margin-top:6px">
          <button class="secondary" onclick="goto('opportunity-detail', {id: ${o.id}})">Review &amp; publish</button>
        </div>
      </div>`).join("");
  } catch (err) {
    card.classList.add("hidden");
  }
}

async function renderTeamRequests() {
  const card = $("#dash-team-requests-card");
  const el = $("#dash-team-requests");
  try {
    const requests = await Api.teamRequests();
    if (!requests.length) {
      card.classList.add("hidden");
      return;
    }
    card.classList.remove("hidden");
    el.innerHTML = requests.map((r) => `
      <div class="list-item">
        <strong>${r.contributor_avatar || "👤"} ${esc(r.contributor_name)}</strong>
        <span class="muted">(${esc(r.contributor_role_title || "")})</span> wants to take on
        <strong>${esc(r.opportunity_title)}</strong>
        <span class="pill">${esc(fmtLabel(r.opportunity_type))}</span>
        <span class="pill ${r.status === "acknowledged" ? "accent" : ""}">${esc(fmtLabel(r.status))}</span>
        ${r.note ? `<p class="muted" style="margin:6px 0">"${esc(r.note)}"</p>` : ""}
        <div style="margin-top:6px; display:flex; gap:8px">
          <button class="secondary" onclick="goto('opportunity-detail', {id: ${r.opportunity_id}})">Open opportunity</button>
          ${r.status === "pending" ? `<button class="secondary" data-ack="${r.id}">Acknowledge</button>` : ""}
        </div>
      </div>`).join("");
    $$("[data-ack]", el).forEach((btn) => btn.addEventListener("click", async () => {
      await Api.acknowledgeTeamRequest(btn.dataset.ack);
      renderTeamRequests();
    }));
  } catch (err) {
    card.classList.add("hidden");
  }
}

/* ---------------- Org ---------------- */

async function renderOrg() {
  await renderOrgTreeFor(state.user.id);
  await renderSkillsOverview();
  await renderCompanyTree();
  $("#expand-tree-btn").addEventListener("click", () => {
    $$("#company-tree .tree-children").forEach((c) => c.classList.remove("collapsed"));
    $$("#company-tree .tree-toggle").forEach((t) => (t.textContent = "▾"));
  }, { once: true });

  await renderAiReadinessBenchmark();
}

async function renderOrgTreeFor(userId) {
  const isSelf = userId === state.user.id;
  const orgData = isSelf ? await Api.myOrg() : await Api.orgForUser(userId);
  const el = $("#my-org-tree");
  const subject = isSelf ? state.user : orgData.subject;

  const nodeChip = (u, extraClass = "", label = "") => `
    <div class="org-chip org-chip-clickable ${extraClass}" data-person-id="${u.id}">
      <span class="org-chip-avatar">${u.avatar_emoji || "👤"}</span>
      <span class="org-chip-name">${esc(u.name)}</span>
      <span class="org-chip-role">${esc(u.role_title || "")}</span>
      ${label ? `<span class="pill" style="margin-top:4px">${label}</span>` : ""}
    </div>`;

  const managerRow = orgData.manager
    ? `<div class="org-tree-row">${nodeChip(orgData.manager, "org-chip-manager", "Manager")}</div><div class="org-connector"></div>`
    : `<div class="org-tree-row"><div class="muted">No manager on record${orgData.is_pod_lead ? " — leads this pod" : ""}.</div></div><div class="org-connector"></div>`;

  const meAndColleagues = `
    <div class="org-tree-row org-tree-row-wide">
      ${nodeChip(subject, "org-chip-me", isSelf ? "You" : "Selected")}
      ${orgData.colleagues.map((c) => nodeChip(c, "org-chip-peer", "Teammate")).join("")}
    </div>`;

  const reportsRow = orgData.direct_reports.length
    ? `<div class="org-connector"></div><div class="org-tree-row org-tree-row-wide">${orgData.direct_reports.map((r) => nodeChip(r, "org-chip-report", "Reports to " + (isSelf ? "you" : "them"))).join("")}</div>`
    : "";

  el.innerHTML = `
    <div class="card">
      <div class="view-header-row" style="margin-bottom:4px">
        <p class="muted" style="margin:0">
          ${isSelf ? "" : `<strong>${esc(subject.name)}</strong>'s team · `}
          Department: <strong>${esc(orgData.department ? orgData.department.name : "Unassigned")}</strong> · Pod: <strong>${esc(orgData.pod ? orgData.pod.name : "Unassigned")}</strong>
        </p>
        ${isSelf ? "" : `<button class="secondary" id="back-to-my-team-btn">← Back to my team</button>`}
      </div>
      <p class="muted" style="font-size:0.8rem;margin-bottom:14px">Click any person below to see their department and team.</p>
      <div class="org-tree">
        ${managerRow}
        ${meAndColleagues}
        ${reportsRow}
      </div>
    </div>`;

  el.querySelectorAll("[data-person-id]").forEach((chip) => {
    chip.addEventListener("click", () => renderOrgTreeFor(Number(chip.dataset.personId)));
  });
  const backBtn = $("#back-to-my-team-btn");
  if (backBtn) backBtn.addEventListener("click", () => renderOrgTreeFor(state.user.id));
}

async function renderAiReadinessBenchmark() {
  const summary = await Api.aiReadinessSummary();
  const el = $("#ai-readiness-benchmark");
  const avgPct = summary.average !== null ? (summary.average / 10) * 100 : null;
  const myPct = summary.my_score !== null && summary.my_score !== undefined ? (summary.my_score / 10) * 100 : null;
  el.innerHTML = `
    <h4 class="ai-readiness-title">Employees AI readiness self evaluation</h4>
    <div class="ai-readiness-scale">
      <div class="ai-readiness-track">
        ${avgPct !== null ? `<div class="ai-readiness-avg-line" style="bottom:${avgPct}%"><span>${summary.average}</span></div>` : ""}
        ${myPct !== null ? `<div class="ai-readiness-my-marker" style="bottom:${myPct}%" title="Your self-evaluation: ${summary.my_score}"></div>` : ""}
      </div>
      <div class="ai-readiness-scale-labels"><span>10</span><span>0</span></div>
    </div>
    <p class="muted ai-readiness-caption">
      ${summary.average !== null
        ? `Company average: <strong>${summary.average}</strong>/10 (${summary.respondents}/${summary.total_employees} responded)`
        : `No self-evaluations submitted yet.`}
    </p>`;
}

async function renderCompanyTree() {
  const data = await Api.companyTree();
  const el = $("#company-tree");
  const myId = state.user.id;

  if (window.mountOrgScene) {
    el.style.display = "none";
    const sceneEl = $("#org-scene");
    sceneEl.style.display = "block";
    window.mountOrgScene(data, myId, sceneEl);
    return;
  }

  function pathToMe(node, path) {
    const newPath = [...path, node.id];
    if (node.id === myId) return newPath;
    for (const child of node.children) {
      const found = pathToMe(child, newPath);
      if (found) return found;
    }
    return null;
  }
  let expandSet = new Set();
  for (const root of data.roots) {
    const found = pathToMe(root, []);
    if (found) expandSet = new Set(found);
  }

  function renderNode(node, depth) {
    const isMe = node.id === myId;
    const hasChildren = node.children.length > 0;
    const expanded = expandSet.has(node.id) || depth === 0;
    return `
      <div class="tree-node">
        <div class="tree-node-label ${isMe ? "tree-node-me" : ""}">
          ${hasChildren ? `<span class="tree-toggle" data-toggle>${expanded ? "▾" : "▸"}</span>` : `<span class="tree-toggle-spacer"></span>`}
          <span class="tree-node-person" data-person-id="${node.id}" title="View ${esc(node.name)}'s team">
            <span>${"👤"}</span> <strong>${esc(node.name)}</strong>
            <span class="muted" style="font-size:0.78rem">${esc(node.role_title || "")}${node.department ? " · " + esc(node.department) : ""}</span>
          </span>
          ${hasChildren ? `<span class="pill" style="margin-left:6px">${node.children.length} report${node.children.length > 1 ? "s" : ""}</span>` : ""}
        </div>
        ${hasChildren ? `<div class="tree-children ${expanded ? "" : "collapsed"}">${node.children.map((c) => renderNode(c, depth + 1)).join("")}</div>` : ""}
      </div>`;
  }

  el.innerHTML = `<p class="muted" style="margin-bottom:10px">${data.total_employees} employees total. Your position is highlighted.</p>` +
    data.roots.map((r) => renderNode(r, 0)).join("");

  el.querySelectorAll("[data-toggle]").forEach((toggle) => {
    toggle.addEventListener("click", () => {
      const children = toggle.closest(".tree-node").querySelector(":scope > .tree-children");
      if (!children) return;
      const collapsed = children.classList.toggle("collapsed");
      toggle.textContent = collapsed ? "▸" : "▾";
    });
  });

  el.querySelectorAll("[data-person-id]").forEach((personEl) => {
    personEl.addEventListener("click", async () => {
      await renderOrgTreeFor(Number(personEl.dataset.personId));
      $("#my-org-tree").scrollIntoView({ block: "start", behavior: "smooth" });
    });
  });
}

/* ---------------- Profile ---------------- */

/* Predefined skill suggestions per department - a light-touch nudge so
   people don't stare at a blank input; manual entry always remains available. */
const DEPT_SKILL_SUGGESTIONS = {
  "Customer Operations": ["Process Automation", "SQL", "Excel/Spreadsheets", "Standard Operating Procedures", "Ticketing Tools"],
  "Business Improvement": ["Process Automation", "SQL", "Python", "Lean Six Sigma", "Power BI"],
  "Engineering & Platform": ["Python", "SQL", "CI/CD", "Cloud Infrastructure", "API Design"],
  "Product Management": ["Roadmapping", "SQL", "User Research", "A/B Testing", "Jira/Confluence"],
  "Risk & Compliance": ["Regulatory Reporting", "SQL", "KYC/AML", "Risk Modeling", "Policy Writing"],
  "Fraud & Security Operations": ["Fraud Detection", "SQL", "Python", "Anomaly Detection", "Incident Response"],
  "Data & Analytics": ["SQL", "Python", "Power BI/Tableau", "Statistics", "Machine Learning Basics"],
  "Payments Operations": ["Transaction Reconciliation", "SQL", "Process Automation", "Chargeback Handling", "Excel/Spreadsheets"],
  "Customer Support & Success": ["Customer Communication", "Ticketing Tools", "Process Automation", "SQL", "Conflict Resolution"],
  "Sales & Partnerships": ["CRM (Salesforce)", "Negotiation", "Pitch Development", "SQL", "Excel/Spreadsheets"],
  "Marketing & Growth": ["Content Strategy", "SEO", "Analytics/GA4", "Copywriting", "Campaign Automation"],
  "Finance & Accounting": ["Excel/Spreadsheets", "SQL", "Financial Modeling", "Reconciliation", "GAAP/IFRS"],
  "Treasury & Liquidity": ["Cash Flow Forecasting", "Excel/Spreadsheets", "SQL", "Risk Modeling", "Regulatory Reporting"],
  "People & Culture": ["HRIS Systems", "Excel/Spreadsheets", "Talent Analytics", "Process Automation", "Employee Communication"],
  "Legal & Regulatory Affairs": ["Contract Review", "Regulatory Reporting", "Policy Writing", "Legal Research", "Compliance Monitoring"],
  "Executive Office": ["Strategic Planning", "Stakeholder Communication", "Excel/Spreadsheets", "Data Storytelling", "Project Management"],
  Unassigned: ["SQL", "Process Automation", "Python", "Excel/Spreadsheets", "Data Analysis"],
};

function renderSuggestionChips(containerId, deptName, alreadyNames, onPick) {
  const el = $(`#${containerId}`);
  if (!el) return;
  const already = new Set(alreadyNames.map((n) => n.toLowerCase()));
  const pool = DEPT_SKILL_SUGGESTIONS[deptName] || DEPT_SKILL_SUGGESTIONS.Unassigned;
  const suggestions = pool.filter((s) => !already.has(s.toLowerCase())).slice(0, 5);
  if (!suggestions.length) { el.innerHTML = ""; return; }
  el.innerHTML = `<span class="suggestion-label">Suggested for ${esc(deptName)}:</span>` +
    suggestions.map((s) => `<button type="button" class="suggestion-chip" data-suggest="${esc(s)}">+ ${esc(s)}</button>`).join("");
  el.querySelectorAll("[data-suggest]").forEach((btn) => {
    btn.addEventListener("click", () => onPick(btn.dataset.suggest));
  });
}

async function renderProfile() {
  const profile = await Api.getProfile();
  state.profileDraft = {
    skills: profile.skills.map((s) => ({ ...s })),
    learning_goals: profile.learning_goals.map((g) => ({ ...g })),
  };

  $("#profile-skills").innerHTML = profile.skills.length
    ? profile.skills.map((s, i) => `
        <div class="list-item">${esc(s.name)} <span class="pill">${esc(s.proficiency)}</span>
          <button class="ghost-btn" style="float:right" onclick="removeSkill(${i})">✕</button>
        </div>`).join("")
    : `<p class="muted">No skills recorded yet.</p>`;

  $("#profile-goals").innerHTML = profile.learning_goals.length
    ? profile.learning_goals.map((g, i) => `
        <div class="list-item">${esc(g.name)} <span class="pill">${esc(fmtLabel(g.goal_type))}</span>
          <button class="ghost-btn" style="float:right" onclick="removeGoal(${i})">✕</button>
        </div>`).join("")
    : `<p class="muted">No learning goals yet.</p>`;

  const deptName = profile.department_name || "Unassigned";
  renderSuggestionChips("skill-suggestions", deptName, profile.skills.map((s) => s.name), async (name) => {
    state.profileDraft.skills.push({ name, proficiency: "Working knowledge" });
    await Api.updateProfile({ skills: state.profileDraft.skills });
    renderProfile();
  });
  renderSuggestionChips("goal-suggestions", deptName, profile.learning_goals.map((g) => g.name), async (name) => {
    state.profileDraft.learning_goals.push({ name, goal_type: "learn" });
    await Api.updateProfile({ learning_goals: state.profileDraft.learning_goals });
    renderProfile();
  });

  $("#pref-availability").value = profile.declared_availability || "";
  $("#pref-opted-in").checked = !!profile.opted_into_discovery;

  const readinessSlider = $("#ai-readiness-slider");
  const readinessValue = $("#ai-readiness-value");
  readinessSlider.value = profile.ai_readiness_score ?? 5;
  readinessValue.textContent = readinessSlider.value;
  readinessSlider.oninput = () => { readinessValue.textContent = readinessSlider.value; };
}

function removeSkill(i) {
  state.profileDraft.skills.splice(i, 1);
  renderProfile();
}
function removeGoal(i) {
  state.profileDraft.learning_goals.splice(i, 1);
  renderProfile();
}
window.removeSkill = removeSkill;
window.removeGoal = removeGoal;
window.goto = goto;

$("#add-skill-btn").addEventListener("click", async () => {
  const name = $("#new-skill-name").value.trim();
  if (!name) return;
  state.profileDraft.skills.push({ name, proficiency: $("#new-skill-level").value });
  await Api.updateProfile({ skills: state.profileDraft.skills });
  $("#new-skill-name").value = "";
  renderProfile();
});

$("#add-goal-btn").addEventListener("click", async () => {
  const name = $("#new-goal-name").value.trim();
  if (!name) return;
  state.profileDraft.learning_goals.push({ name, goal_type: $("#new-goal-type").value });
  await Api.updateProfile({ learning_goals: state.profileDraft.learning_goals });
  $("#new-goal-name").value = "";
  renderProfile();
});

$("#save-prefs-btn").addEventListener("click", async () => {
  await Api.updateProfile({
    declared_availability: $("#pref-availability").value,
    opted_into_discovery: $("#pref-opted-in").checked,
    ai_readiness_score: Number($("#ai-readiness-slider").value),
  });
  $("#profile-save-msg").textContent = "Saved!";
  setTimeout(() => ($("#profile-save-msg").textContent = ""), 2000);
});

/* ---------------- Workflows ---------------- */

const DEPT_ICONS = {
  "Customer Operations": "🎧",
  "Business Improvement": "📈",
  "Engineering & Platform": "🛠️",
  "Product Management": "🧭",
  "Risk & Compliance": "🛡️",
  "Fraud & Security Operations": "🔒",
  "Data & Analytics": "📊",
  "Payments Operations": "💳",
  "Customer Support & Success": "💬",
  "Sales & Partnerships": "🤝",
  "Marketing & Growth": "📣",
  "Finance & Accounting": "💰",
  "Treasury & Liquidity": "🏦",
  "People & Culture": "🌱",
  "Legal & Regulatory Affairs": "⚖️",
  "Executive Office": "🏛️",
  Unassigned: "🗂️",
};

async function renderWorkflows() {
  const workflows = await Api.listWorkflows();
  const listEl = $("#workflow-list");
  if (!workflows.length) {
    listEl.innerHTML = `<p class="muted">No workflows yet.</p>`;
    return;
  }

  const byDept = new Map();
  for (const w of workflows) {
    const deptId = w.department_id ?? "unassigned";
    if (!byDept.has(deptId)) byDept.set(deptId, { name: w.department_name || "Unassigned", teams: new Map() });
    const entry = byDept.get(deptId);
    const teamKey = w.pod_name || "General";
    if (!entry.teams.has(teamKey)) entry.teams.set(teamKey, []);
    entry.teams.get(teamKey).push(w);
  }

  const renderDeptCard = (deptName, teams) => {
    const totalWf = Array.from(teams.values()).reduce((n, arr) => n + arr.length, 0);
    return `
    <div class="card wf-dept-card">
      <div class="wf-dept-header">
        <span class="wf-dept-icon">${DEPT_ICONS[deptName] || "🏢"}</span>
        <div>
          <h3>${esc(deptName)}</h3>
          <span class="muted">${totalWf} workflow${totalWf === 1 ? "" : "s"} across ${teams.size} team${teams.size === 1 ? "" : "s"}</span>
        </div>
      </div>
      <div class="wf-lineage">
        <div class="wf-teams-col">
          ${Array.from(teams.entries()).map(([teamName, wfs]) => `
            <div class="wf-team-row">
              <div class="wf-team-node">🧩 ${esc(teamName)} ${wfs.length > 1 ? `<span class="pill">${wfs.length} flows</span>` : ""}</div>
              <div class="wf-workflows-group">
                ${wfs.map((w) => `
                  <div class="wf-chip" onclick="goto('workflow-detail', {id: ${w.id}})">
                    <span class="wf-chip-name">${esc(w.name)} ${w.stages.some((s) => s.ai_generated) ? '<span class="badge ai">AI</span>' : ""}</span>
                    <span class="pill ${["validated", "published"].includes(w.validation_status) ? "accent" : ""}">${esc(fmtLabel(w.validation_status))}</span>
                    <span class="muted" style="font-size:0.72rem">${w.stages.length} stage(s)</span>
                  </div>`).join("")}
              </div>
            </div>`).join("")}
        </div>
      </div>
    </div>`;
  };

  const myDeptId = state.user.department_id ?? "unassigned";
  const mine = [];
  const others = [];
  for (const [deptId, entry] of byDept.entries()) {
    (deptId === myDeptId ? mine : others).push(renderDeptCard(entry.name, entry.teams));
  }

  listEl.innerHTML = `
    <h3 class="wf-section-title">Your department's workflows:</h3>
    ${mine.length ? mine.join("") : `<p class="muted">No workflows recorded for your department yet.</p>`}
    <h3 class="wf-section-title" style="margin-top:22px">Other departments' workflows</h3>
    ${others.length ? others.join("") : `<p class="muted">No other departments have recorded workflows yet.</p>`}`;
}

$("#new-workflow-btn").addEventListener("click", () => showView("workflow-intake"));

state.wfAttachmentFilename = null;

$("#wf-upload-input").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  const statusEl = $("#wf-upload-status");
  state.wfAttachmentFilename = null;
  if (!file) { statusEl.textContent = ""; return; }
  statusEl.textContent = `Scanning ${file.name}…`;
  try {
    const result = await Api.extractWorkflowFile(file);
    state.wfAttachmentFilename = result.filename;
    if (result.is_image) {
      statusEl.textContent = `📎 ${result.filename} attached for reference. ${result.note || ""}`;
    } else if (result.source_text) {
      $("#wf-source-text").value = result.source_text;
      $("#wf-source-type").value = "pasted_text";
      statusEl.textContent = `✅ Extracted ${result.stages_preview_count} step(s) from ${result.filename} — review below before creating the draft.`;
    } else {
      statusEl.textContent = `⚠ ${result.note || "No text could be extracted from " + result.filename + "."}`;
    }
  } catch (err) {
    statusEl.textContent = "";
    alert(err.message);
  }
});

$("#create-workflow-btn").addEventListener("click", async () => {
  const sourceType = $("#wf-source-type").value;
  const text = $("#wf-source-text").value;
  const body = {
    name: $("#wf-name").value || "Untitled workflow",
    business_purpose: $("#wf-purpose").value,
    source_type: (state.wfAttachmentFilename && sourceType === "pasted_text") ? "uploaded_file" : sourceType,
    source_text: text,
    attachment_filename: state.wfAttachmentFilename || undefined,
  };
  if (sourceType === "manual") {
    body.stages = text.split("\n").map((l) => l.trim()).filter(Boolean).map((line, idx) => ({
      name: line, sequence: idx + 1, ai_generated: false,
    }));
  }
  try {
    const wf = await Api.createWorkflow(body);
    $("#wf-create-msg").textContent = "Workflow created!";
    state.wfAttachmentFilename = null;
    setTimeout(() => goto("workflow-detail", { id: wf.id }), 600);
  } catch (err) {
    $("#wf-create-msg").textContent = "";
    alert(err.message);
  }
});

let dragStageIdx = null;

async function renderWorkflowDetail(id) {
  const wf = await Api.getWorkflow(id);
  $("#wfd-name").textContent = wf.name;
  $("#wfd-purpose").textContent = wf.business_purpose || "";
  $("#wfd-attachment").textContent = wf.source_attachment_filename ? `📎 Source document: ${wf.source_attachment_filename}` : "";
  $("#wfd-status").textContent = fmtLabel(wf.validation_status);
  $("#wfd-status").className = `pill ${["validated", "published"].includes(wf.validation_status) ? "accent" : ""}`;

  const canEditWorkflow = (state.user.roles || []).some((r) => ["team_lead", "workflow_owner", "administrator"].includes(r))
    && (state.user.roles.includes("administrator") || wf.department_id === state.user.department_id || wf.owner_id === state.user.id);

  $("#wfd-edit-btn").classList.toggle("hidden", !canEditWorkflow);
  $("#wfd-edit-form").classList.add("hidden");
  $("#wfd-edit-btn").onclick = () => {
    $("#wfd-edit-name").value = wf.name;
    $("#wfd-edit-purpose").value = wf.business_purpose || "";
    $("#wfd-edit-form").classList.remove("hidden");
  };
  $("#wfd-edit-cancel-btn").onclick = () => $("#wfd-edit-form").classList.add("hidden");
  $("#wfd-edit-save-btn").onclick = async () => {
    try {
      await Api.editWorkflow(wf.id, {
        name: $("#wfd-edit-name").value.trim() || wf.name,
        business_purpose: $("#wfd-edit-purpose").value,
      });
      renderWorkflowDetail(wf.id);
    } catch (err) { alert(err.message); }
  };

  $("#wfd-add-stage-card").classList.toggle("hidden", !canEditWorkflow);
  $("#wfd-add-stage-btn").onclick = async () => {
    const name = $("#wfd-new-stage-name").value.trim();
    if (!name) { alert("Give the new step a name."); return; }
    try {
      await Api.addStage(wf.id, { name, description: $("#wfd-new-stage-desc").value });
      $("#wfd-new-stage-name").value = "";
      $("#wfd-new-stage-desc").value = "";
      renderWorkflowDetail(wf.id);
    } catch (err) { alert(err.message); }
  };

  const TRANSITIONS = {
    draft: ["needs_owner_review"], ai_generated_draft: ["needs_owner_review"],
    needs_owner_review: ["validated"], validated: ["published", "needs_owner_review"],
    published: ["archived"], archived: [],
  };
  const next = TRANSITIONS[wf.validation_status] || [];
  $("#wfd-transition-actions").innerHTML = next.map(
    (t) => `<button class="secondary" data-transition="${t}">${esc(fmtLabel(t))}</button>`
  ).join(" ");
  $$("#wfd-transition-actions button").forEach((b) => b.addEventListener("click", async () => {
    try {
      await Api.transitionWorkflow(wf.id, b.dataset.transition);
      renderWorkflowDetail(wf.id);
    } catch (err) { alert(err.message); }
  }));

  const canvas = $("#wfd-canvas");
  canvas.innerHTML = wf.stages.map((s, i) => `
    <div class="stage-card" draggable="true" data-idx="${i}" data-id="${s.id}">
      <span class="stage-handle">⠿</span>
      <div class="stage-body">
        <div class="stage-title">${i + 1}. ${esc(s.name)} ${s.ai_generated ? '<span class="badge ai">AI drafted</span>' : ""}
          ${s.uncertain_fields.length ? `<span class="badge human">Needs review: ${s.uncertain_fields.map(fmtLabel).join(", ")}</span>` : ""}
        </div>
        <div class="stage-meta">${esc(s.description || s.activities || "No description yet.")}</div>
        ${s.backlog_status && s.backlog_status !== "no_current_need" ? `<span class="badge blocked">${esc(fmtLabel(s.backlog_status))}</span>` : ""}
      </div>
      <div class="stage-actions">
        ${canEditWorkflow ? `<button class="ghost-btn" data-edit-stage="${s.id}">✏️ Rewrite</button>` : ""}
        ${canEditWorkflow ? `<button class="ghost-btn" data-set-backlog="${s.id}">📌 Signal backlog</button>` : ""}
        ${canEditWorkflow ? `<button class="ghost-btn" data-delete-stage="${s.id}">🗑️ Remove</button>` : ""}
      </div>
    </div>`).join("");

  renderWorkflowMap(wf.stages);

  // Drag-reorder (visual only — sequence is illustrative per design decision).
  $$(".stage-card", canvas).forEach((card) => {
    card.addEventListener("dragstart", () => { dragStageIdx = card.dataset.idx; card.classList.add("dragging"); });
    card.addEventListener("dragend", () => card.classList.remove("dragging"));
    card.addEventListener("dragover", (e) => { e.preventDefault(); card.classList.add("drag-over"); });
    card.addEventListener("dragleave", () => card.classList.remove("drag-over"));
    card.addEventListener("drop", (e) => {
      e.preventDefault();
      card.classList.remove("drag-over");
      const fromIdx = Number(dragStageIdx);
      const toIdx = Number(card.dataset.idx);
      if (fromIdx === toIdx) return;
      const nodes = Array.from(canvas.children);
      const moved = nodes[fromIdx];
      canvas.removeChild(moved);
      canvas.insertBefore(moved, nodes[toIdx === nodes.length - 1 && toIdx > fromIdx ? null : (toIdx > fromIdx ? nodes[toIdx].nextSibling : nodes[toIdx])] || null);
    });
    card.querySelector("[data-set-backlog]")?.addEventListener("click", async (e) => {
      e.stopPropagation();
      const options = ["no_current_need", "monitoring", "assistance_requested", "critical_internal_need"];
      const choice = prompt("Set backlog signal:\n" + options.join(", "), "assistance_requested");
      if (!choice || !options.includes(choice)) return;
      try {
        await Api.setBacklogSignal(card.dataset.id, choice);
        renderWorkflowDetail(wf.id);
      } catch (err) { alert(err.message); }
    });
    card.querySelector("[data-edit-stage]")?.addEventListener("click", async (e) => {
      e.stopPropagation();
      const stage = wf.stages.find((s) => String(s.id) === card.dataset.id);
      const newName = prompt("Step name:", stage?.name || "");
      if (newName === null) return;
      const newDesc = prompt("Step description:", stage?.description || stage?.activities || "");
      if (newDesc === null) return;
      try {
        await Api.editStage(wf.id, card.dataset.id, { name: newName.trim() || stage.name, description: newDesc });
        renderWorkflowDetail(wf.id);
      } catch (err) { alert(err.message); }
    });
    card.querySelector("[data-delete-stage]")?.addEventListener("click", async (e) => {
      e.stopPropagation();
      if (!confirm("Remove this step from the workflow?")) return;
      try {
        await Api.deleteStage(wf.id, card.dataset.id);
        renderWorkflowDetail(wf.id);
      } catch (err) { alert(err.message); }
    });
  });
}

/* Compact connected-node "workflow map" shown alongside the stage list.
   Hovering a node (or its matching stage card) highlights both, so a
   complex multi-step workflow can still be traced visually at a glance. */
function renderWorkflowMap(stages) {
  const mapEl = $("#wfd-map");
  if (!stages.length) {
    mapEl.innerHTML = `<p class="muted">No steps yet — add one to see the map.</p>`;
    return;
  }
  mapEl.innerHTML = stages.map((s, i) => `
    <div class="wfd-map-node" data-id="${s.id}">
      <div class="wfd-map-dot">${i + 1}</div>
      <div class="wfd-map-label" title="${esc(s.description || s.activities || "")}">${esc(s.name)}</div>
    </div>
    ${i < stages.length - 1 ? '<div class="wfd-map-connector"></div>' : ""}`).join("");

  const canvas = $("#wfd-canvas");
  const highlight = (id, on) => {
    $$(`.wfd-map-node[data-id="${id}"]`, mapEl).forEach((n) => n.classList.toggle("wfd-map-node-active", on));
    $$(`.stage-card[data-id="${id}"]`, canvas).forEach((c) => c.classList.toggle("stage-card-active", on));
  };
  $$(".wfd-map-node", mapEl).forEach((node) => {
    node.addEventListener("mouseenter", () => highlight(node.dataset.id, true));
    node.addEventListener("mouseleave", () => highlight(node.dataset.id, false));
  });
  $$(".stage-card", canvas).forEach((card) => {
    card.addEventListener("mouseenter", () => highlight(card.dataset.id, true));
    card.addEventListener("mouseleave", () => highlight(card.dataset.id, false));
  });
}

/* ---------------- Backlog ---------------- */

async function renderBacklog() {
  const stages = await Api.backlogDashboard();
  $("#backlog-list").innerHTML = stages.length ? stages.map((s) => `
    <div class="card">
      <h3>${esc(s.name)} <span class="badge blocked">${esc(fmtLabel(s.backlog_status))}</span></h3>
      <p class="muted">From workflow: ${esc(s.workflow_name)}</p>
      ${s.opportunities.length ? `<p>Opportunities: ${s.opportunities.map((o) => `<span class="pill">${esc(o.title)}</span>`).join(" ")}</p>` : `<p class="muted">No opportunity drafted yet.</p>`}
    </div>`).join("") : `<p class="muted">No declared backlog signals yet.</p>`;
}

/* ---------------- Opportunities ---------------- */

async function renderOpportunities() {
  const [opportunities, backlogStages] = await Promise.all([
    Api.listOpportunities(),
    Api.backlogDashboard().catch(() => []),
  ]);

  const shadowOpps = opportunities.filter((o) => o.opportunity_type === "shadow_for_a_day");
  const hotOpps = opportunities.filter((o) => o.opportunity_type !== "shadow_for_a_day");
  // Backlog stages that don't yet have any opportunity drafted from them -
  // surface the raw backlog signal so hot tasks show up even before someone
  // formalizes them into an opportunity.
  const backlogOnly = backlogStages.filter((s) => !s.opportunities.length);

  $("#hot-tasks-list").innerHTML = renderOppCards(hotOpps, backlogOnly);
  $("#shadow-list").innerHTML = shadowOpps.length
    ? shadowOpps.map(oppCard).join("")
    : `<p class="muted">No shadowing opportunities published yet.</p>`;

  // Reset to the "choose an option" state each time the tab is opened -
  // users pick Learn/Help/Teach explicitly rather than seeing a default lane.
  $("#lane-empty-hint").classList.remove("hidden");
  $$(".lane-bar .lane-btn").forEach((b) => b.classList.remove("active"));
  $$("#view-opportunities .lane-panel").forEach((p) => p.classList.add("hidden"));

  await renderTeachMatches();
}

document.addEventListener("click", (e) => {
  const laneBtn = e.target.closest(".lane-btn");
  if (!laneBtn) return;
  const bar = laneBtn.closest(".lane-bar");
  bar.querySelectorAll(".lane-btn").forEach((b) => b.classList.toggle("active", b === laneBtn));
  $("#lane-empty-hint").classList.add("hidden");
  bar.parentElement.querySelectorAll(".lane-panel").forEach((p) => p.classList.add("hidden"));
  $(`#lane-${laneBtn.dataset.lane}`).classList.remove("hidden");
});

async function renderTeachMatches() {
  const el = $("#teach-matches-list");
  if (!el) return;
  try {
    const matches = await Api.teachMatches();
    el.innerHTML = matches.length ? matches.map((m) => `
      <div class="teach-match-card">
        <h3>${esc(m.skill_name)} <span class="pill">Your level: ${esc(m.my_proficiency)}</span></h3>
        <p class="muted">${m.learners_count} colleague${m.learners_count === 1 ? "" : "s"} want${m.learners_count === 1 ? "s" : ""} to learn this</p>
        <div class="teach-learners">
          ${m.sample_learners.map((l) => `<span class="teach-learner-chip">${l.avatar_emoji || "👤"} ${esc(l.name)}${l.department_name ? ` · ${esc(l.department_name)}` : ""}</span>`).join("")}
        </div>
        <button class="primary" data-offer-teach="${m.skill_id}" data-skill-name="${esc(m.skill_name)}">🧑‍🏫 Offer to teach ${esc(m.skill_name)}</button>
      </div>`).join("") : `<p class="muted">None of your listed skills currently match a colleague's learning goal yet. Add more skills in your Profile to see matches here.</p>`;

    el.querySelectorAll("[data-offer-teach]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const skillName = btn.dataset.skillName;
        btn.disabled = true;
        btn.textContent = "Sending for approval…";
        try {
          const opp = await Api.createOpportunity({
            title: `Learn ${skillName} — shadow ${state.user.name}`,
            opportunity_type: "shadow_for_a_day",
            problem_statement: `${state.user.name} is offering to teach ${skillName} to colleagues who want to learn it.`,
            desired_outcome: `A colleague builds working knowledge of ${skillName}.`,
            definition_of_done: `Shadowing session(s) completed and the learner can perform the task independently.`,
            learnable_skills: [skillName],
            sensitivity: "low",
            share_scope: "company_wide",
            mentor_available: true,
            required_authorization: "none",
          });
          goto("opportunity-detail", { id: opp.id });
        } catch (err) {
          alert(err.message);
          btn.disabled = false;
          btn.textContent = `🧑‍🏫 Offer to teach ${skillName}`;
        }
      });
    });
  } catch (e) { el.innerHTML = `<p class="muted">Could not load teaching matches.</p>`; }
}

function oppCard(o) {
  return `
    <div class="card" style="cursor:pointer" onclick="goto('opportunity-detail', {id: ${o.id}})">
      <h3>${esc(o.title)}</h3>
      <p class="muted">${esc(fmtLabel(o.opportunity_type))}</p>
      <span class="pill ${o.status === "published" ? "accent" : ""}">${esc(fmtLabel(o.status))}</span>
    </div>`;
}

function backlogCard(s) {
  const urgent = s.backlog_status === "critical_internal_need";
  return `
    <div class="card">
      <h3>${esc(s.name)} <span class="badge ${urgent ? "blocked" : "human"}">${esc(fmtLabel(s.backlog_status))}</span></h3>
      <p class="muted" style="cursor:pointer" onclick="goto('workflow-detail', {id: ${s.workflow_id}})">From workflow: ${esc(s.workflow_name)} <span class="muted">(view workflow)</span></p>
      <span class="pill">📋 Backlog signal — no opportunity drafted yet</span>
      <button class="primary" style="margin-top:10px;display:block;width:100%" data-offer-help="${s.id}" data-workflow-id="${s.workflow_id}" data-stage-name="${esc(s.name)}">🙋 I'll help with this — send request</button>
    </div>`;
}

document.addEventListener("click", async (e) => {
  const helpBtn = e.target.closest("[data-offer-help]");
  if (!helpBtn) return;
  helpBtn.disabled = true;
  helpBtn.textContent = "Sending for approval…";
  const stageName = helpBtn.dataset.stageName;
  try {
    const opp = await Api.createOpportunity({
      title: `Help clear backlog: ${stageName}`,
      opportunity_type: "bounded_backlog_assistance",
      workflow_id: Number(helpBtn.dataset.workflowId),
      stage_id: Number(helpBtn.dataset.offerHelp),
      problem_statement: `${state.user.name} is offering to help clear the backlog on "${stageName}".`,
      desired_outcome: `The backlog on "${stageName}" is reduced or resolved.`,
      definition_of_done: `Agreed backlog items for "${stageName}" are completed.`,
      sensitivity: "low",
      required_authorization: "none",
      share_scope: "company_wide",
    });
    goto("opportunity-detail", { id: opp.id });
  } catch (err) {
    alert(err.message);
    helpBtn.disabled = false;
    helpBtn.textContent = "🙋 I'll help with this";
  }
});

function renderOppCards(opps, backlogStages) {
  const cards = [...opps.map(oppCard), ...backlogStages.map(backlogCard)];
  return cards.length ? cards.join("") : `<p class="muted">No hot tasks right now.</p>`;
}

function skillBarRows(rows, maxCount, fillClass, showExpert) {
  return rows.map((s) => `
    <div class="skill-bar-row">
      <span class="skill-bar-label">${esc(s.name)}</span>
      <div class="skill-bar-track"><div class="skill-bar-fill ${fillClass}" style="width:${Math.max(6, (s.people_count / maxCount) * 100)}%"></div></div>
      <span class="skill-bar-count">${s.people_count}${showExpert && s.expert_count ? ` <span class="muted">(${s.expert_count} expert)</span>` : ""}</span>
    </div>`).join("");
}

async function renderSkillsOverview() {
  try {
    const data = await Api.skillsOverview();
    const maxAvail = Math.max(1, ...data.available_skills.map((s) => s.people_count));
    const maxWanted = Math.max(1, ...data.wanted_skills.map((s) => s.people_count));
    $("#skills-available-panel").innerHTML = data.available_skills.length
      ? `<p class="muted skills-overview-caption">${data.totals.people_with_skills} of ${data.totals.total_people} people have listed skills</p>
         <div class="skills-scroll-panel">${skillBarRows(data.available_skills, maxAvail, "skill-bar-fill-avail", true)}</div>`
      : `<p class="muted">No skills logged yet.</p>`;
    $("#skills-wanted-panel").innerHTML = data.wanted_skills.length
      ? `<p class="muted skills-overview-caption">${data.totals.people_with_goals} of ${data.totals.total_people} people have learning goals</p>
         <div class="skills-scroll-panel">${skillBarRows(data.wanted_skills, maxWanted, "skill-bar-fill-wanted", false)}</div>`
      : `<p class="muted">No learning goals logged yet.</p>`;
  } catch (e) { /* non-fatal */ }
}

$("#new-opportunity-btn").addEventListener("click", async () => {
  showView("opportunity-intake");
  const sel = $("#opp-workflow-select");
  const stageSel = $("#opp-stage-select");
  sel.innerHTML = `<option value="">— Loading workflows… —</option>`;
  try {
    const workflows = await Api.listWorkflows();
    sel.innerHTML = `<option value="">— Not tied to a specific workflow —</option>` +
      workflows.map((w) => `<option value="${w.id}">${esc(w.name)}${w.department_name ? ` (${esc(w.department_name)})` : ""}</option>`).join("");
    sel.dataset.loaded = "1";
    sel._workflows = workflows;
  } catch (e) {
    sel.innerHTML = `<option value="">— Not tied to a specific workflow —</option>`;
  }
  stageSel.innerHTML = `<option value="">— Choose a workflow first —</option>`;
  stageSel.disabled = true;
});

$("#opp-workflow-select").addEventListener("change", (e) => {
  const stageSel = $("#opp-stage-select");
  const workflows = e.target._workflows || [];
  const wf = workflows.find((w) => String(w.id) === e.target.value);
  if (!wf) {
    stageSel.innerHTML = `<option value="">— Choose a workflow first —</option>`;
    stageSel.disabled = true;
    return;
  }
  stageSel.disabled = false;
  stageSel.innerHTML = `<option value="">— Not tied to a specific step —</option>` +
    wf.stages.map((s) => `<option value="${s.id}">${esc(s.name)}</option>`).join("");
});

$("#create-opportunity-btn").addEventListener("click", async () => {
  const body = {
    workflow_id: Number($("#opp-workflow-select").value) || null,
    stage_id: Number($("#opp-stage-select").value) || null,
    title: $("#opp-title").value || "Untitled opportunity",
    opportunity_type: $("#opp-type").value,
    definition_of_done: $("#opp-dod").value,
    sensitivity: $("#opp-sensitivity").value,
    share_scope: $("#opp-share-scope").value,
    reviewer_id: null,
    required_authorization: $("#opp-required-auth").value,
  };
  try {
    const opp = await Api.createOpportunity(body);
    $("#opp-create-msg").textContent = "Draft saved!";
    setTimeout(() => goto("opportunity-detail", { id: opp.id }), 600);
  } catch (err) {
    $("#opp-create-msg").textContent = "";
    alert(err.message);
  }
});

async function renderOpportunityDetail(id) {
  const opp = await Api.getOpportunity(id);
  $("#opp-detail-card").innerHTML = `
    <h2>${esc(opp.title)} <span class="pill ${opp.status === "published" ? "accent" : ""}">${esc(fmtLabel(opp.status))}</span>
      ${opp.share_scope === "department_only" ? '<span class="pill">🔒 Department only</span>' : ""}</h2>
    <p class="muted">${esc(fmtLabel(opp.opportunity_type))}</p>
    <p>${esc(opp.problem_statement || "")}</p>
    <p><strong>Definition of done:</strong> ${esc(opp.definition_of_done || "Not specified.")}</p>
    <p><strong>Sensitivity:</strong> <span class="pill">${esc(fmtLabel(opp.sensitivity))}</span></p>`;

  const explEl = $("#opp-explanation-card");
  explEl.innerHTML = "";
  if (opp.status === "published") {
    try {
      const check = await Api.eligibilityCheck(opp.id);
      explEl.innerHTML = `
        <h3>Eligibility ${check.eligible ? '<span class="badge editable">Eligible</span>' : '<span class="badge blocked">Not eligible</span>'}</h3>
        ${check.reasons.length ? `<ul>${check.reasons.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>` : `<p class="muted">No blockers found.</p>`}`;
    } catch (e) { /* non-fatal */ }
  } else if (opp.status === "pending_mutual_acceptance" || opp.status === "active") {
    explEl.innerHTML = `<h3>Status</h3><p class="muted">${opp.status === "active" ? "This opportunity is active — mutual acceptance is complete." : "Someone has already expressed interest — this is now waiting on the opportunity owner's approval, not on eligibility."}</p>`;
  }

  const tlCard = $("#opp-team-lead-card");
  tlCard.innerHTML = "";
  if (opp.owner_id !== state.user.id && ["published", "pending_mutual_acceptance", "active"].includes(opp.status)) {
    try {
      const { manager } = await Api.myManager();
      tlCard.innerHTML = manager
        ? `<h3>🧭 Your team lead</h3>
           <p>${manager.avatar_emoji || "👤"} <strong>${esc(manager.name)}</strong> <span class="muted">(${esc(manager.role_title || "")})</span></p>
           <textarea id="tl-note" rows="2" placeholder="Optional note for your TL (e.g. why you'd like this opportunity)"></textarea>
           <button class="secondary" id="request-tl-btn" style="margin-top:8px">📨 Send request to your TL</button>
           <p id="tl-request-msg" class="success"></p>`
        : `<h3>🧭 Your team lead</h3><p class="muted">No manager on record for your profile yet.</p>`;
      $("#request-tl-btn")?.addEventListener("click", async () => {
        try {
          await Api.requestTlSupport(opp.id, $("#tl-note").value.trim());
          $("#tl-request-msg").textContent = `Sent to ${manager.name}!`;
        } catch (err) { alert(err.message); }
      });
    } catch (e) { /* non-fatal */ }
  }

  const actionsEl = $("#opp-actions-card");
  let html = "";
  if (opp.status === "draft") {
    if (opp.can_current_user_publish) {
      const approverNote = opp.owner_id === state.user.id
        ? ""
        : `<p class="muted">You're approving this as ${esc(opp.approver?.name || "the reviewer")}.</p>`;
      const authOptions = ["none", "manager_sign_off", "restricted_system_access", "confidential_data_clearance"];
      const reviewerLine = opp.reviewer_id
        ? `<p class="muted">Reviewer: ${opp.approver?.avatar_emoji || "👤"} <strong>${esc(opp.approver?.name || "—")}</strong></p>`
        : `<p class="muted">Reviewer: not set yet — you (${esc(state.user.name)}) will be assigned as reviewer when you approve.</p>`;
      html += `
        ${approverNote}
        <h3 style="margin-top:0">Review &amp; complete before approving</h3>
        <p class="muted" style="margin-top:-4px">Fill in anything missing, then approve — no need to send it back.</p>
        ${reviewerLine}
        <label>Definition of done<textarea id="edit-dod" rows="2">${esc(opp.definition_of_done || "")}</textarea></label>
        <div class="grid-2">
          <label>Sensitivity
            <select id="edit-sensitivity">
              <option value="low" ${opp.sensitivity === "low" ? "selected" : ""}>Low</option>
              <option value="medium" ${opp.sensitivity === "medium" ? "selected" : ""}>Medium</option>
              <option value="unknown" ${!opp.sensitivity || opp.sensitivity === "unknown" ? "selected" : ""}>Unknown — needs a decision</option>
            </select>
          </label>
          <label>Required authorization
            <select id="edit-auth">
              ${authOptions.map((a) => `<option value="${a}" ${opp.required_authorization === a ? "selected" : ""}>${esc(fmtLabel(a))}</option>`).join("")}
            </select>
          </label>
        </div>
        <label>Priority / estimated effort<input id="edit-effort" placeholder="e.g. Low effort — a few hours" value="${esc(opp.estimated_effort || "")}" /></label>
        <button class="primary" id="publish-opp-btn" style="margin-top:8px">✅ Save &amp; approve &amp; publish</button>
        <div id="publish-reasons" class="error" style="margin-top:10px"></div>`;
    } else {
      html += `<p class="muted">⏳ Awaiting approval from ${opp.approver ? `${opp.approver.avatar_emoji || "👤"} <strong>${esc(opp.approver.name)}</strong>` : "your Team Lead/manager"} before this becomes visible for grabs.</p>`;
    }
  }
  if (opp.status === "published") {
    html += `<button class="primary" id="express-interest-btn">Express interest</button>`;
  }
  if (opp.status === "pending_mutual_acceptance") {
    if (opp.owner_id === state.user.id) {
      html += `<button class="primary" id="approve-btn">Approve (owner)</button>`;
    } else {
      html += `<p class="muted">⏳ Pending approval from the opportunity owner${opp.owner ? `, ${opp.owner.avatar_emoji || "👤"} <strong>${esc(opp.owner.name)}</strong>` : ""}. No action needed from you right now.</p>`;
    }
  }
  if (opp.status === "active") {
    html += `<button class="primary" onclick="goto('workspace', {opportunityId: ${opp.id}})">Open guided workspace</button>`;
  }
  actionsEl.innerHTML = html || `<p class="muted">No actions available in this state.</p>`;

  $("#publish-opp-btn")?.addEventListener("click", async () => {
    try {
      await Api.updateOpportunity(opp.id, {
        definition_of_done: $("#edit-dod").value,
        sensitivity: $("#edit-sensitivity").value,
        required_authorization: $("#edit-auth").value,
        estimated_effort: $("#edit-effort").value,
        // Self-heal drafts that never got a resolvable manager/reviewer:
        // whoever is approving right now becomes the named reviewer.
        ...(opp.reviewer_id ? {} : { reviewer_id: state.user.id }),
      });
      await Api.publishOpportunity(opp.id);
      renderOpportunityDetail(opp.id);
      refreshApprovalsBell();
    } catch (err) {
      $("#publish-reasons").innerHTML = (err.reasons || [err.message]).map((r) => `<div>⚠ ${esc(r)}</div>`).join("");
    }
  });
  $("#express-interest-btn")?.addEventListener("click", async () => {
    try { await Api.expressInterest(opp.id); renderOpportunityDetail(opp.id); }
    catch (err) { alert((err.reasons || [err.message]).join("\n")); }
  });
  $("#approve-btn")?.addEventListener("click", async () => {
    try { await Api.approveInterest(opp.id); renderOpportunityDetail(opp.id); }
    catch (err) { alert(err.message); }
  });
}

/* ---------------- Similarity ---------------- */

function renderSimilarityShell() {
  $("#similarity-result").innerHTML = "";
  runSimilarityScan();
}

$("#rescan-similarity-btn").addEventListener("click", () => runSimilarityScan());

const CONFIDENCE_LABEL = { "medium-high": "Strong match", "low-medium": "Possible match" };

async function runSimilarityScan() {
  const summaryEl = $("#similarity-scan-summary");
  const resultEl = $("#similarity-auto-result");
  summaryEl.textContent = "Scanning workflow steps…";
  resultEl.innerHTML = "";
  try {
    const data = await Api.autoScanSimilarities();
    summaryEl.textContent = `Scanned ${data.scanned_stages} steps across validated/published workflows — found ${data.matches_found} similar pair(s), ${data.cross_department_matches} of them cross-department.`;
    if (!data.matches.length) {
      resultEl.innerHTML = `<div class="card muted">No notable overlaps found yet. Validate/publish more workflows to widen the scan.</div>`;
      return;
    }
    resultEl.innerHTML = data.matches.map((m) => `
      <div class="card sim-match-card ${m.cross_department ? "sim-cross-dept" : ""}">
        <div class="sim-match-header">
          <span class="badge ai">${esc(CONFIDENCE_LABEL[m.confidence] || m.confidence)} · ${m.match_percentage}% match</span>
          ${m.cross_department ? '<span class="badge human">Cross-department</span>' : '<span class="badge">Same department</span>'}
        </div>
        <div class="sim-match-sides">
          <div class="sim-match-side">
            <div class="sim-match-dept">${esc(m.stage_a.department_name || "—")} · ${esc(m.stage_a.pod_name || "—")}</div>
            <div class="sim-match-stage" data-open-workflow="${m.stage_a.workflow_id}">${esc(m.stage_a.name)}</div>
            <div class="muted">in ${esc(m.stage_a.workflow_name)}</div>
          </div>
          <div class="sim-match-vs">≈</div>
          <div class="sim-match-side">
            <div class="sim-match-dept">${esc(m.stage_b.department_name || "—")} · ${esc(m.stage_b.pod_name || "—")}</div>
            <div class="sim-match-stage" data-open-workflow="${m.stage_b.workflow_id}">${esc(m.stage_b.name)}</div>
            <div class="muted">in ${esc(m.stage_b.workflow_name)}</div>
          </div>
        </div>
        <p><strong>Shared:</strong> ${esc((m.shared_characteristics || []).join(", ") || "none found")}</p>
        <p class="sim-match-explanation">🤖 ${esc(m.explanation || "")}</p>
        <p class="muted">${esc(m.recommendation)}</p>
      </div>`).join("");
    $$("[data-open-workflow]", resultEl).forEach((el) => el.addEventListener("click", () => {
      goto("workflow-detail", { id: Number(el.dataset.openWorkflow) });
    }));
  } catch (err) {
    summaryEl.textContent = "";
    resultEl.innerHTML = `<div class="card muted">Could not run scan: ${esc(err.message)}</div>`;
  }
}

$("#compare-btn").addEventListener("click", async () => {
  const a = Number($("#sim-stage-a").value);
  const b = Number($("#sim-stage-b").value);
  if (!a || !b) return;
  try {
    const result = await Api.compareStages(a, b);
    $("#similarity-result").innerHTML = `
      <div class="card">
        <h3>Comparison <span class="badge ai">AI-assisted, ${result.match_percentage}% match · confidence: ${esc(result.confidence)}</span></h3>
        <p><strong>Shared:</strong> ${esc((result.shared_characteristics || []).join(", ") || "none found")}</p>
        <p class="sim-match-explanation">🤖 ${esc(result.explanation || "")}</p>
        <p><strong>Differences:</strong> ${esc((result.differences || []).join(", ") || "none found")}</p>
        <p><strong>Recommendation:</strong> ${esc(result.recommendation)}</p>
        <p class="badge human">Requires owner confirmation</p>
        ${result.reuse_recommendations.length ? `<h4>Reuse suggestions</h4><ul>${result.reuse_recommendations.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>` : ""}
      </div>`;
  } catch (err) { alert(err.message); }
});

/* ---------------- Workspace ---------------- */

async function renderWorkspace(opportunityId) {
  const data = await Api.getWorkspace(opportunityId);
  const el = $("#workspace-content");
  el.innerHTML = `
    <div class="card">
      <h3>Guided steps <span class="badge ai">AI-assisted guidance</span> <span class="badge human">Human review required</span></h3>
      <ol>${data.guidance.steps.map((s) => `<li style="margin-bottom:8px">${esc(s)}</li>`).join("")}</ol>
    </div>
    <div class="card">
      <h3>Submit your output</h3>
      <textarea id="submission-content" rows="4" placeholder="Describe or paste your output..."></textarea>
      <button class="primary" id="submit-output-btn" style="margin-top:10px">Submit for review</button>
      <p id="submit-msg" class="success"></p>
      <h4 style="margin-top:16px">Prior submissions</h4>
      ${data.submissions.length ? data.submissions.map((s) => `<div class="list-item">${esc(s.content)}</div>`).join("") : `<p class="muted">None yet.</p>`}
    </div>
    <div class="card">
      <h3>Reviewer decision</h3>
      <select id="review-decision"><option value="accepted">Accept</option><option value="changes_requested">Request changes</option><option value="rejected">Reject</option></select>
      <textarea id="review-reason" rows="2" placeholder="Reason (required to reject)" style="margin-top:8px"></textarea>
      <button class="secondary" id="submit-review-btn" style="margin-top:8px">Submit review</button>
    </div>
    <div class="card">
      <h3>Learning feedback</h3>
      <textarea id="feedback-note" rows="2" placeholder="What did you learn? (free-text only, never a rating)"></textarea>
      <button class="secondary" id="submit-feedback-btn" style="margin-top:8px">Save feedback</button>
      <p id="feedback-msg" class="success"></p>
    </div>`;

  $("#submit-output-btn").addEventListener("click", async () => {
    const content = $("#submission-content").value.trim();
    if (!content) return;
    await Api.submitOutput(data.workspace.id, content);
    $("#submit-msg").textContent = "Submitted!";
    renderWorkspace(opportunityId);
  });

  $("#submit-review-btn").addEventListener("click", async () => {
    const submissions = data.submissions;
    if (!submissions.length) return alert("No submission to review yet.");
    const latest = submissions[submissions.length - 1];
    try {
      await Api.reviewSubmission(latest.id, {
        decision: $("#review-decision").value,
        reason: $("#review-reason").value,
      });
      renderWorkspace(opportunityId);
    } catch (err) { alert(err.message); }
  });

  $("#submit-feedback-btn").addEventListener("click", async () => {
    const note = $("#feedback-note").value.trim();
    if (!note) return;
    await Api.recordFeedback(opportunityId, note);
    $("#feedback-msg").textContent = "Saved!";
  });
}

/* ---------------- Audit ---------------- */

async function renderAudit() {
  const events = await Api.auditFeed();
  $("#audit-list").innerHTML = events.length ? events.map((e) => `
    <div class="list-item">
      <strong>${esc(fmtLabel(e.action))}</strong>
      ${e.ai_involved ? '<span class="badge ai">AI</span>' : ""}
      ${e.human_approved ? '<span class="badge human">Human approved</span>' : ""}
      <div class="muted" style="font-size:0.8rem">${esc(e.object_type)} #${e.object_id} · ${esc(e.timestamp)}</div>
    </div>`).join("") : `<p class="muted">No audit events yet.</p>`;
}

/* ---------------- Init ---------------- */

(function init() {
  history.replaceState({ view: "login", opts: {} }, "", "#login");
  const token = Api.token();
  const user = Api.getUser();
  if (token && user) {
    state.user = user;
    onAuthenticated();
  } else {
    initLogin();
  }
})();
