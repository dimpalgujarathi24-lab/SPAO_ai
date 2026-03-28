// script.js — SharkAI Merged v3.0

const API = "http://127.0.0.1:5000";
let SESSION_ID  = null;
let SHARK_KEY   = "namita";
let isWaiting   = false;
let currentScores = null;

const SHARK_CONFIG = {
  ashneer: { initials: "AG", avatarClass: "ashneer-color", accentColor: "#ff4d4d", barColor: "#ff4d4d" },
  namita:  { initials: "NT", avatarClass: "namita-color",  accentColor: "#c8f135", barColor: "#c8f135" },
  aman:    { initials: "AM", avatarClass: "aman-color",    accentColor: "#00e5ff", barColor: "#00e5ff" }
};

// ── Select shark ──────────────────────────────────────────────────
async function selectShark(sharkKey) {
  SHARK_KEY = sharkKey;
  const cfg = SHARK_CONFIG[sharkKey];

  try {
    const res  = await fetch(`${API}/session/new`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ shark: sharkKey })
    });
    const data = await res.json();
    SESSION_ID = data.session_id;

    updateSharkUI(sharkKey, data.shark, cfg);

    document.getElementById("selector-screen").style.display = "none";
    document.getElementById("chat-screen").classList.add("visible");
    document.getElementById("session-badge").textContent = `SESSION ${SESSION_ID.toUpperCase()}`;
    document.getElementById("messages-area").innerHTML = "";
    document.getElementById("analysis-banner").style.display = "none";
    resetScoreboard();
    updateProgressBar(0, 7);
    updateStageDisplay("COLLECTING INFO");

    appendMessage(data.opening, "bot", data.shark);

  } catch (err) {
    alert("Cannot connect to backend.\nMake sure Flask is running: python app.py");
  }
}

// ── Update shark UI ───────────────────────────────────────────────
function updateSharkUI(sharkKey, sharkName, cfg) {
  document.getElementById("sidebar-avatar").textContent  = cfg.initials;
  document.getElementById("sidebar-avatar").className    = `sidebar-avatar ${cfg.avatarClass}`;
  document.getElementById("sidebar-shark-name").textContent = sharkName;
  const tagMap = { ashneer: "Brutal & Direct", namita: "Analytical", aman: "Brand Focused" };
  document.getElementById("sidebar-shark-tag").textContent = tagMap[sharkKey] || "";
  document.getElementById("chat-header-avatar").textContent    = cfg.initials;
  document.getElementById("chat-header-avatar").style.color    = cfg.accentColor;
  document.getElementById("chat-header-avatar").style.borderColor = cfg.accentColor;
  document.getElementById("chat-header-name").textContent = sharkName;
}

// ── Send message ──────────────────────────────────────────────────
async function sendMessage() {
  if (isWaiting) return;
  const input = document.getElementById("chat-input");
  const text  = input.value.trim();
  if (!text || !SESSION_ID) return;

  input.value = "";
  autoResizeTextarea(input);
  appendMessage(text, "user", "You");

  isWaiting = true;
  setInputLoading(true);
  const typingEl = showTyping();

  try {
    const res  = await fetch(`${API}/chat`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ session_id: SESSION_ID, message: text })
    });
    const data = await res.json();
    removeTyping(typingEl);

    if (data.error) { appendMessage("Error: " + data.error, "bot", "System"); return; }

    appendMessage(data.message, "bot", data.shark);

    // ── Update progress bar during collection ──
    if (data.stage === "collecting" && data.fields_done !== undefined) {
      updateProgressBar(data.fields_done, data.fields_total);
      updateStageDisplay(`COLLECTING INFO (${data.fields_done}/${data.fields_total})`);
    }

    // ── Show scoreboard when analysis arrives ──
    if (data.analysis) {
      showScoreboard(data.analysis);
      updateStageDisplay("VERDICT GIVEN");
      updateProgressBar(7, 7);
    }

    // ── Update scores live during follow-up chat ──
    if (data.updated_scores) {
      updateScoreboardLive(data.updated_scores);
      updateStageDisplay("FOLLOW-UP");
    }

    if (data.stage === "collecting") {
      updateStageDisplay(`COLLECTING (${data.fields_done || 0}/7)`);
    }

  } catch (err) {
    removeTyping(typingEl);
    appendMessage("Cannot reach backend. Make sure python app.py is running.", "bot", "System");
  } finally {
    isWaiting = false;
    setInputLoading(false);
    input.focus();
  }
}

function sendQuick(text) {
  document.getElementById("chat-input").value = text;
  sendMessage();
}

function changeShark() {
  SESSION_ID = null;
  document.getElementById("messages-area").innerHTML = "";
  document.getElementById("analysis-banner").style.display = "none";
  document.getElementById("chat-screen").classList.remove("visible");
  document.getElementById("selector-screen").style.display = "flex";
  resetScoreboard();
}

// ── Append message ────────────────────────────────────────────────
function appendMessage(text, role, name) {
  const area    = document.getElementById("messages-area");
  const cfg     = SHARK_CONFIG[SHARK_KEY];
  const isUser  = role === "user";
  const initials = isUser ? "YOU" : cfg.initials;

  const now     = new Date();
  const timeStr = now.getHours().toString().padStart(2,"0") + ":" + now.getMinutes().toString().padStart(2,"0");

  const msgEl = document.createElement("div");
  msgEl.className = `message ${isUser ? "user-message" : "bot-message"}`;
  msgEl.innerHTML = `
    <div class="message-avatar ${isUser ? "user-avatar" : "bot-avatar"}"
         style="${!isUser ? `color:${cfg.accentColor};border-color:${cfg.accentColor}40` : ""}">
      ${initials}
    </div>
    <div>
      <div class="message-bubble ${isUser ? "user-bubble" : "bot-bubble"}">${escapeHtml(text)}</div>
      <div class="message-time">${timeStr}</div>
    </div>`;
  area.appendChild(msgEl);
  area.scrollTop = area.scrollHeight;
}

// ── SCOREBOARD ────────────────────────────────────────────────────
function showScoreboard(analysis) {
  const scores  = analysis.scores || {};
  const prob    = analysis.investment_probability || 0;
  const decision = analysis.decision || {};
  const cfg     = SHARK_CONFIG[SHARK_KEY];

  currentScores = scores;

  const banner = document.getElementById("analysis-banner");
  banner.style.display = "block";

  // Verdict + probability in top bar
  const verdictEl = document.getElementById("banner-verdict");
  verdictEl.textContent = decision.decision || "—";
  verdictEl.className   = `banner-verdict ${decision.color || ""}`;

  document.getElementById("banner-prob").textContent = prob + "%";
  setTimeout(() => {
    const fill = document.getElementById("banner-prob-fill");
    fill.style.width      = prob + "%";
    fill.style.background = cfg.barColor;
  }, 200);

  document.getElementById("banner-score").textContent =
    (scores.total_score || 0) + "/100";

  document.getElementById("banner-industry").textContent =
    (analysis.extracted_data || {}).industry_detected || "—";

  // Score sliders
  renderScoreSliders(scores, cfg.accentColor);
}

function renderScoreSliders(scores, accentColor) {
  const container = document.getElementById("score-sliders");
  if (!container) return;

  const metrics = [
    { key: "profitability", label: "PROFITABILITY", max: 25 },
    { key: "scalability",   label: "SCALABILITY",   max: 25 },
    { key: "uniqueness",    label: "UNIQUENESS",     max: 25 },
    { key: "growth",        label: "GROWTH",         max: 25 },
  ];

  container.innerHTML = "";
  container.style.display = "block";

  metrics.forEach(m => {
    const val     = scores[m.key] || 0;
    const pct     = Math.round((val / m.max) * 100);
    const color   = pct >= 70 ? "#2ea043" : pct >= 40 ? accentColor : "#da3633";

    const row = document.createElement("div");
    row.className = "score-row";
    row.innerHTML = `
      <div class="score-row-header">
        <span class="score-row-label">${m.label}</span>
        <span class="score-row-val" style="color:${color}">${val}/${m.max}</span>
      </div>
      <div class="score-bar-track">
        <div class="score-bar-fill" data-target="${pct}" style="width:0%;background:${color}"></div>
      </div>`;
    container.appendChild(row);
  });

  // Risk row (inverted — lower is better)
  const risk     = scores.risk_penalty || 0;
  const riskPct  = Math.round((risk / 25) * 100);
  const riskColor = riskPct <= 20 ? "#2ea043" : riskPct <= 50 ? "#e3912a" : "#da3633";
  const riskRow  = document.createElement("div");
  riskRow.className = "score-row";
  riskRow.innerHTML = `
    <div class="score-row-header">
      <span class="score-row-label">RISK LEVEL</span>
      <span class="score-row-val" style="color:${riskColor}">${risk}/25</span>
    </div>
    <div class="score-bar-track">
      <div class="score-bar-fill" data-target="${riskPct}" style="width:0%;background:${riskColor}"></div>
    </div>`;
  container.appendChild(riskRow);

  // Animate bars in
  requestAnimationFrame(() => {
    setTimeout(() => {
      document.querySelectorAll(".score-bar-fill").forEach(bar => {
        bar.style.width = bar.dataset.target + "%";
      });
    }, 100);
  });
}

function updateScoreboardLive(scores) {
  if (!currentScores) return;
  currentScores = scores;
  const cfg = SHARK_CONFIG[SHARK_KEY];

  // Update probability
  const prob = scores.probability || 0;
  document.getElementById("banner-prob").textContent = prob + "%";
  const fill = document.getElementById("banner-prob-fill");
  if (fill) {
    fill.style.width      = prob + "%";
    fill.style.background = cfg.barColor;
  }

  // Update total score
  document.getElementById("banner-score").textContent = (scores.total_score || 0) + "/100";

  // Pulse the sliders to show update
  const container = document.getElementById("score-sliders");
  if (container && container.style.display !== "none") {
    renderScoreSliders(scores, cfg.accentColor);
    container.classList.add("score-updated");
    setTimeout(() => container.classList.remove("score-updated"), 800);
  }

  // Update verdict badge
  const prob2 = scores.probability || 0;
  const verdictEl = document.getElementById("banner-verdict");
  if (verdictEl) {
    if (prob2 >= 70) {
      verdictEl.textContent = "DEAL";
      verdictEl.className   = "banner-verdict green";
    } else if (prob2 >= 45) {
      verdictEl.textContent = "CONDITIONAL DEAL";
      verdictEl.className   = "banner-verdict orange";
    } else {
      verdictEl.textContent = "NO DEAL";
      verdictEl.className   = "banner-verdict red";
    }
  }
}

function resetScoreboard() {
  document.getElementById("analysis-banner").style.display = "none";
  const container = document.getElementById("score-sliders");
  if (container) { container.innerHTML = ""; container.style.display = "none"; }
  currentScores = null;
}

// ── Progress bar ──────────────────────────────────────────────────
function updateProgressBar(done, total) {
  const bar = document.getElementById("collection-progress");
  if (!bar) return;
  const pct = Math.round((done / total) * 100);
  bar.style.display = "block";
  bar.querySelector(".progress-fill").style.width = pct + "%";
  bar.querySelector(".progress-label").textContent = `PITCH INFO: ${done}/${total}`;
}

// ── Typing indicator ──────────────────────────────────────────────
function showTyping() {
  const area = document.getElementById("messages-area");
  const el   = document.createElement("div");
  el.className = "message bot-message";
  el.id        = "typing-indicator";
  el.innerHTML = `
    <div class="message-avatar bot-avatar" style="color:${SHARK_CONFIG[SHARK_KEY].accentColor}">
      ${SHARK_CONFIG[SHARK_KEY].initials}
    </div>
    <div class="typing-indicator">
      <div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>
    </div>`;
  area.appendChild(el);
  area.scrollTop = area.scrollHeight;
  return el;
}

function removeTyping(el) { if (el && el.parentNode) el.parentNode.removeChild(el); }

function updateStageDisplay(text) {
  document.getElementById("stage-display").textContent = text;
}

function setInputLoading(on) {
  const btn     = document.getElementById("btn-send");
  const sendTxt = document.getElementById("send-text");
  const spinner = document.getElementById("send-spinner");
  btn.disabled          = on;
  sendTxt.style.display = on ? "none"  : "inline";
  spinner.style.display = on ? "block" : "none";
}

function autoResizeTextarea(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 120) + "px";
}

function escapeHtml(text) {
  return text
    .replace(/&/g,  "&amp;")
    .replace(/</g,  "&lt;")
    .replace(/>/g,  "&gt;")
    .replace(/\n/g, "<br>");
}

document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("chat-input");
  if (!input) return;
  input.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
  input.addEventListener("input", () => autoResizeTextarea(input));
});
