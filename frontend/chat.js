const $ = (id) => document.getElementById(id);
const CONTACT_KEY = "pinetree_contact_v1";
const THEME_KEY = "pinetree_theme";

const store = {
  get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} },
  del(k) { try { localStorage.removeItem(k); } catch (e) {} },
};

let sessionId = null;
let busy = false;

/* ---------- Theme ---------- */
function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  $("theme-label").textContent = theme === "dark" ? "Light mode" : "Dark mode";
  $("theme-toggle").setAttribute("aria-label", theme === "dark" ? "Switch to light theme" : "Switch to dark theme");
}
$("theme-toggle").addEventListener("click", () => {
  const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
  store.set(THEME_KEY, next);
  applyTheme(next);
});
applyTheme(document.documentElement.getAttribute("data-theme"));

/* ---------- Mobile menu ---------- */
function setNav(open) {
  document.body.classList.toggle("nav-open", open);
  $("menu-btn").setAttribute("aria-expanded", String(open));
}
$("menu-btn").addEventListener("click", () => setNav(!document.body.classList.contains("nav-open")));
$("overlay").addEventListener("click", () => setNav(false));
document.addEventListener("keydown", (e) => { if (e.key === "Escape") setNav(false); });

/* ---------- Sidebar contact details ---------- */
fetch("/api/config").then((r) => r.json()).then((c) => {
  if (c.contact_email) {
    const a = $("contact-email");
    a.href = "mailto:" + c.contact_email;
    a.querySelector("span").textContent = c.contact_email;
    a.hidden = false;
  }
}).catch(() => {});

/* ---------- Helpers ---------- */
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const scrollDown = () => { const s = $("scroll"); s.scrollTop = s.scrollHeight; };

const CONNECTION_MSG = "I'm having trouble connecting right now. Please try again in a moment.";

async function post(url, body) {
  let res;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (e) {
    throw new Error(CONNECTION_MSG);
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = data && data.detail;
    const err = new Error(Array.isArray(detail) ? "Please check your details and try again."
      : typeof detail === "string" ? detail : CONNECTION_MSG);
    err.fields = Array.isArray(detail)
      ? Object.fromEntries(detail.map((d) => [d.loc && d.loc[d.loc.length - 1], d.msg]))
      : {};
    throw err;
  }
  return data || {};
}

// Keep the typing animation up for 1-3 seconds, longer for longer answers.
const holdTyping = (startedAt, text) => wait(Math.min(3000, Math.max(1000, 1000 + text.length * 8)) - (Date.now() - startedAt));

function makeRow(who) {
  const row = document.createElement("div");
  row.className = `row ${who}`;
  if (who === "bot") {
    const av = document.createElement("img");
    av.src = "/static/logo-icon.png"; av.alt = ""; av.className = "avatar";
    row.appendChild(av);
  }
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  row.appendChild(bubble);
  $("thread").appendChild(row);
  return { row, bubble };
}

function addMessage(text, who, extraClass) {
  const { row, bubble } = makeRow(who);
  bubble.textContent = text;
  if (extraClass) bubble.classList.add(extraClass);
  scrollDown();
  return row;
}

function showTyping() {
  const { row, bubble } = makeRow("bot");
  bubble.innerHTML = '<span class="typing" role="status" aria-label="Assistant is typing"><i></i><i></i><i></i></span>';
  scrollDown();
  return row;
}

async function botSays(text, extraClass, delay = 650) {
  const typing = showTyping();
  await wait(delay);
  typing.remove();
  return addMessage(text, "bot", extraClass);
}

/* ---------- Composer ---------- */
const input = $("input");
function setComposerEnabled(on) {
  input.disabled = !on;
  $("send-btn").disabled = !on;
  input.placeholder = on ? "Ask about the PineTree Macro fund..." : "Enter your details above first";
  if (on) input.focus();
}
function autosize() {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 160) + "px";
  input.style.overflowY = input.scrollHeight > 160 ? "auto" : "hidden";
}
input.addEventListener("input", autosize);
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    $("composer").requestSubmit();
  }
});
$("composer").addEventListener("submit", (e) => {
  e.preventDefault();
  send(input.value);
});

async function send(text) {
  text = text.trim();
  if (!text || busy || !sessionId) return;
  busy = true;
  $("send-btn").disabled = true;
  input.value = ""; autosize();
  $("chips").classList.add("hidden");
  document.querySelectorAll(".inline-chips").forEach((el) => el.remove());
  addMessage(text, "user");
  const typing = showTyping();
  try {
    const started = Date.now();
    const data = await post("/api/chat", { session_id: sessionId, message: text });
    await holdTyping(started, data.answer);
    typing.remove();
    addMessage(data.answer, "bot", data.escalated ? "handoff" : "");
    addFollowUps(data);
  } catch (err) {
    typing.remove();
    addMessage(err.message, "bot");
  } finally {
    busy = false;
    $("send-btn").disabled = false;
    input.focus();
  }
}

// Under a reply: the Contact our team button (hand-offs and contact answers) and follow-up questions.
function addFollowUps({ kind, suggestions = [], offer_contact: offerContact = false }) {
  if (!offerContact && !suggestions.length) return;
  const box = document.createElement("div");
  box.className = "inline-chips";
  if (offerContact) {
    const cta = document.createElement("button");
    cta.type = "button"; cta.className = "chip cta"; cta.textContent = "Contact our team";
    cta.addEventListener("click", openContact);
    box.appendChild(cta);
  }
  if (suggestions.length && kind !== "clarify") {
    const label = document.createElement("div");
    label.className = "label"; label.textContent = "You may also like to ask:";
    box.appendChild(label);
  }
  for (const q of suggestions) {
    const b = document.createElement("button");
    b.type = "button"; b.className = "chip"; b.textContent = q;
    b.addEventListener("click", () => send(q));
    box.appendChild(b);
  }
  $("thread").appendChild(box);
  scrollDown();
}

function showChips(questions) {
  const box = $("chips");
  box.replaceChildren(...questions.map((q) => {
    const b = document.createElement("button");
    b.type = "button"; b.className = "chip"; b.textContent = q;
    b.addEventListener("click", () => send(q));
    return b;
  }));
  box.classList.toggle("hidden", !questions.length);
}

/* ---------- Onboarding (inside the conversation) ---------- */
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
function validate(v) {
  const errors = {};
  if (!v.name.trim()) errors.name = "Please enter your name.";
  if (!EMAIL_RE.test(v.email.trim())) errors.email = "Please enter a valid email address.";
  const digits = v.phone.replace(/\D/g, "");
  if (!/^\+?[\d\s\-()]{7,20}$/.test(v.phone.trim()) || digits.length < 7 || digits.length > 15) {
    errors.phone = "Please enter a valid phone number, e.g. +91 98765 43210.";
  }
  return errors;
}

function showDetailsForm() {
  const { row, bubble } = makeRow("bot");
  bubble.classList.add("form-bubble");
  bubble.innerHTML = `
    <form class="details-card" novalidate>
      <div class="field"><label for="f-name">Name</label>
        <input id="f-name" name="name" autocomplete="name" maxlength="200" required>
        <div class="field-error" data-for="name" role="alert"></div></div>
      <div class="field"><label for="f-email">Email</label>
        <input id="f-email" name="email" type="email" inputmode="email" autocomplete="email" required>
        <div class="field-error" data-for="email" role="alert"></div></div>
      <div class="field"><label for="f-phone">Phone number</label>
        <input id="f-phone" name="phone" type="tel" inputmode="tel" autocomplete="tel" placeholder="+91 98765 43210" required>
        <div class="field-error" data-for="phone" role="alert"></div></div>
      <div class="form-error" role="alert"></div>
      <button class="btn" type="submit">Continue</button>
    </form>`.trim();
  const form = bubble.querySelector("form");
  const showErrors = (errors) => {
    for (const name of ["name", "email", "phone"]) {
      form.elements[name].setAttribute("aria-invalid", errors[name] ? "true" : "false");
      form.querySelector(`[data-for="${name}"]`).textContent = errors[name] || "";
    }
  };
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const values = { name: form.elements.name.value.trim(), email: form.elements.email.value.trim(), phone: form.elements.phone.value.trim() };
    const errors = validate(values);
    showErrors(errors);
    form.querySelector(".form-error").textContent = "";
    const firstBad = ["name", "email", "phone"].find((k) => errors[k]);
    if (firstBad) { form.elements[firstBad].focus(); return; }
    const btn = form.querySelector("button");
    btn.disabled = true;
    try {
      const data = await post("/api/session", values);
      store.set(CONTACT_KEY, JSON.stringify(values));
      sessionId = data.session_id;
      setContact(values);
      row.remove();
      const summary = addMessage(`${values.name}\n${values.email}\n${values.phone}`, "user");
      summary.querySelector(".bubble").classList.add("details-summary");
      $("reset-details").classList.remove("hidden");
      await botSays(data.greeting);
      showChips(data.suggested_questions);
      setComposerEnabled(true);
    } catch (err) {
      const serverErrors = {};
      for (const k of ["name", "email", "phone"]) if (err.fields && err.fields[k]) serverErrors[k] = "Please check this field.";
      showErrors(serverErrors);
      form.querySelector(".form-error").textContent = Object.keys(serverErrors).length ? "" : err.message;
      btn.disabled = false;
    }
  });
  scrollDown();
  form.elements.name.focus({ preventScroll: true });
}

async function startNew() {
  await botSays("Hi, my name is Stan and I am here to assist you with your queries.", "", 450);
  await botSays("Before we begin, please tell us who you are so our team can follow up if needed. Your details and conversation are kept by PineTree for up to 30 days so our team can assist you.");
  showDetailsForm();
}

async function startReturning(contact) {
  const typing = showTyping();
  try {
    const data = await post("/api/session", { ...contact, returning: true });
    await wait(500);
    typing.remove();
    sessionId = data.session_id;
    setContact(contact);
    addMessage(data.greeting, "bot");
    $("reset-details").classList.remove("hidden");
    showChips(data.suggested_questions);
    setComposerEnabled(true);
  } catch (err) {
    typing.remove();
    store.del(CONTACT_KEY);
    await startNew();
  }
}

/* ---------- Contact our team ---------- */
let currentContact = null;
const dialog = $("contact-dialog");
const contactForm = $("contact-form");

function setContact(values) {
  currentContact = { ...values };
  $("contact-btn").disabled = false;
  $("contact-btn").removeAttribute("title");
}

function openContact() {
  if (!sessionId) return;
  setNav(false);
  contactForm.elements.name.value = currentContact.name;
  contactForm.elements.email.value = currentContact.email;
  contactForm.elements.phone.value = currentContact.phone;
  contactForm.querySelectorAll(".field-error, .form-error").forEach((el) => { el.textContent = ""; });
  contactForm.querySelectorAll("input, textarea").forEach((el) => el.setAttribute("aria-invalid", "false"));
  dialog.showModal();
  contactForm.elements.message.focus();
}

$("contact-btn").addEventListener("click", openContact);
$("cf-cancel").addEventListener("click", () => dialog.close());
dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });

contactForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const el = contactForm.elements;
  const values = { name: el.name.value.trim(), email: el.email.value.trim(), phone: el.phone.value.trim() };
  const errors = validate(values);
  const message = el.message.value.trim();
  if (!message) errors.message = "Please write a message for our team.";
  for (const field of ["name", "email", "phone", "message"]) {
    el[field].setAttribute("aria-invalid", errors[field] ? "true" : "false");
    contactForm.querySelector(`[data-for="${field}"]`).textContent = errors[field] || "";
  }
  const firstBad = ["name", "email", "phone", "message"].find((k) => errors[k]);
  if (firstBad) { el[firstBad].focus(); return; }

  $("cf-send").disabled = true;
  const started = Date.now();
  try {
    const data = await post("/api/contact-request", { session_id: sessionId, ...values, message });
    dialog.close();
    el.message.value = "";
    setContact(values);
    store.set(CONTACT_KEY, JSON.stringify(values));
    document.querySelectorAll(".inline-chips").forEach((box) => box.remove());
    addMessage(`Message to the team: ${message}`, "user");
    const typing = showTyping();
    await holdTyping(started, data.answer);
    typing.remove();
    addMessage(data.answer, "bot");
  } catch (err) {
    contactForm.querySelector(".form-error").textContent = err.message;
  } finally {
    $("cf-send").disabled = false;
  }
});

$("reset-details").addEventListener("click", () => {
  store.del(CONTACT_KEY);
  location.reload();
});

(function init() {
  let saved = null;
  try { saved = JSON.parse(store.get(CONTACT_KEY) || "null"); } catch (e) {}
  if (saved && saved.name && saved.email && saved.phone) startReturning(saved);
  else startNew();
})();
