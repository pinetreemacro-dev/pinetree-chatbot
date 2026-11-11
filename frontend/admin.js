const view = document.getElementById("view");
let currentTab = "overview";

function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v);
  }
  for (const c of children.flat()) if (c != null) el.append(c);
  return el;
}

async function api(path, options) {
  const res = await fetch("/api/admin" + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    throw new Error(typeof d === "string" ? d : "Request failed (check the fields)");
  }
  return data;
}

const fmt = (iso) => new Date(iso + "Z").toLocaleString();
const empty = (msg) => h("div", { class: "empty" }, msg);

function table(headers, rows) {
  if (!rows.length) return empty("Nothing here yet.");
  return h("div", { class: "table-wrap" }, h("table", {},
    h("thead", {}, h("tr", {}, headers.map((t) => h("th", {}, t)))),
    h("tbody", {}, rows)));
}

async function showTranscript(sessionId, into) {
  into.replaceChildren(h("div", { class: "muted" }, "Loading..."));
  try {
    const msgs = await api(`/sessions/${sessionId}/messages`);
    into.replaceChildren(...msgs.map((m) =>
      h("div", { class: `tx ${m.sender === "user" ? "user" : "bot"}` }, m.text)));
  } catch (e) { into.replaceChildren(h("div", { class: "error" }, e.message)); }
}

async function overview() {
  const s = await api("/stats");
  const tile = (n, label) => h("div", { class: "tile" }, h("b", {}, String(n)), h("span", {}, label));
  return h("div", {},
    h("div", { class: "tiles" },
      tile(s.conversations, "Conversations"), tile(s.leads, "Leads"),
      tile(s.answered, "Questions answered"), tile(s.escalations_open, "Open escalations"),
      tile(s.escalations_total, "Total escalations")),
    h("h3", {}, "Most-asked FAQs"),
    table(["FAQ", "Times answered"], s.top_faqs.map((t) => h("tr", {}, h("td", {}, t.faq_id), h("td", {}, String(t.count))))));
}

async function escalations() {
  const list = await api("/escalations");
  const transcriptBox = h("div", { class: "transcript" });
  const panel = h("div", { class: "panel hidden" }, h("b", {}, "Conversation"), transcriptBox);
  const rows = list.map((e) => h("tr", {},
    h("td", {}, fmt(e.created_at)),
    h("td", {}, e.question),
    h("td", {}, h("div", {}, e.name), h("div", { class: "muted" }, e.email), h("div", { class: "muted" }, e.phone)),
    h("td", {}, h("span", { class: `tag ${e.status}` }, e.status), " ", h("span", { class: "tag" }, e.email_sent ? "emailed" : "not emailed")),
    h("td", {}, h("div", { class: "row-actions" },
      h("button", { class: "btn secondary small", onclick: () => { panel.classList.remove("hidden"); showTranscript(e.session_id, transcriptBox); } }, "View chat"),
      h("button", { class: "btn secondary small", onclick: async () => {
        await api(`/escalations/${e.id}/status`, { method: "POST", body: JSON.stringify({ status: e.status === "open" ? "resolved" : "open" }) });
        render();
      } }, e.status === "open" ? "Mark resolved" : "Reopen"),
      h("button", { class: "btn small", onclick: () => { currentTab = "faqs"; render({ question: e.question }); } }, "Create FAQ")))));
  return h("div", {}, panel, table(["When", "Question", "User", "Status", "Actions"], rows));
}

async function leads() {
  const list = await api("/leads");
  return table(["Started", "Name", "Email", "Phone", "Last activity"], list.map((l) => h("tr", {},
    h("td", {}, fmt(l.started_at)), h("td", {}, l.name), h("td", {}, l.email), h("td", {}, l.phone), h("td", {}, fmt(l.last_activity)))));
}

async function faqs(prefill) {
  const list = await api("/faqs");
  const f = { id: null, question: "", answer: "", category: "", keywords: [], active: true, data_as_of: "", ...(prefill || {}) };
  const q = h("input", { value: f.question });
  const a = h("textarea", { rows: "4" }); a.value = f.answer;
  const cat = h("input", { value: f.category });
  const kw = h("input", { value: (f.keywords || []).join(", "), placeholder: "comma-separated synonyms" });
  const asOf = h("input", { value: f.data_as_of || "", placeholder: "YYYY-MM-DD (optional)" });
  const active = h("input", { type: "checkbox", style: "width:auto" }); active.checked = f.active;
  const msg = h("div", { class: "error" });
  const form = h("form", { class: "panel", onsubmit: async (ev) => {
    ev.preventDefault(); msg.textContent = "";
    const body = { question: q.value, answer: a.value, category: cat.value,
      keywords: kw.value.split(",").map((k) => k.trim()).filter(Boolean),
      active: active.checked, data_as_of: asOf.value.trim() || null };
    try {
      await api(f.id ? `/faqs/${f.id}` : "/faqs", { method: f.id ? "PUT" : "POST", body: JSON.stringify(body) });
      render();
    } catch (err) { msg.textContent = err.message; }
  } },
    h("b", {}, f.id ? `Edit ${f.id}` : "New FAQ"),
    h("label", {}, "Question"), q, h("label", {}, "Answer"), a,
    h("label", {}, "Category"), cat, h("label", {}, "Keywords / synonyms"), kw,
    h("label", {}, "Data as of"), asOf,
    h("label", {}, active, " Active (the bot can use it)"),
    msg, h("button", { class: "btn", type: "submit" }, "Save FAQ"));
  const rows = list.map((x) => h("tr", {},
    h("td", {}, x.id), h("td", {}, x.question), h("td", {}, x.answer), h("td", {}, x.category || ""),
    h("td", {}, x.active === false ? h("span", { class: "tag" }, "inactive") : ""),
    h("td", {}, h("button", { class: "btn secondary small", onclick: () => { render(x); document.getElementById("scroll").scrollTop = 0; } }, "Edit"))));
  return h("div", {}, form, table(["ID", "Question", "Answer", "Category", "", ""], rows));
}

const tabs = { overview, escalations, leads, faqs };

async function render(arg) {
  document.querySelectorAll(".nav-item").forEach((t) => t.classList.toggle("active", t.dataset.tab === currentTab));
  view.replaceChildren(empty("Loading..."));
  try { view.replaceChildren(await tabs[currentTab](arg)); }
  catch (e) { view.replaceChildren(h("div", { class: "error" }, e.message)); }
}

document.getElementById("tabs").addEventListener("click", (e) => {
  const item = e.target.closest("[data-tab]");
  if (item) { currentTab = item.dataset.tab; setNav(false); render(); }
});

/* Theme and mobile menu, shared look with the chatbot */
function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  document.getElementById("theme-label").textContent = theme === "dark" ? "Light mode" : "Dark mode";
  document.getElementById("theme-toggle").setAttribute("aria-label", theme === "dark" ? "Switch to light theme" : "Switch to dark theme");
}
document.getElementById("theme-toggle").addEventListener("click", () => {
  const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
  try { localStorage.setItem("pinetree_theme", next); } catch (e) {}
  applyTheme(next);
});
applyTheme(document.documentElement.getAttribute("data-theme"));

function setNav(open) {
  document.body.classList.toggle("nav-open", open);
  document.getElementById("menu-btn").setAttribute("aria-expanded", String(open));
}
document.getElementById("menu-btn").addEventListener("click", () => setNav(!document.body.classList.contains("nav-open")));
document.getElementById("overlay").addEventListener("click", () => setNav(false));
document.addEventListener("keydown", (e) => { if (e.key === "Escape") setNav(false); });

render();
