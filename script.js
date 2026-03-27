// script.js — SharkAI Chatbot v2.0

const API = "http://127.0.0.1:5000";
let SESSION_ID  = null;
let SHARK_KEY   = "namita";
let isWaiting   = false;

// ── Shark display config ──────────────────────────────────────────
const SHARK_CONFIG = {
  ashneer: {
    initials: "AG",
    avatarClass: "ashneer-color",
    accentColor: "#ff4d4d",
    barColor:    "#ff4d4d"
  },
  namita: {
    initials: "NT",
    avatarClass: "namita-color",
    accentColor: "#c8f135",
    barColor:    "#c8f135"
  },
  aman: {
    initials: "AM",
    avatarClass: "aman-color",
    accentColor: "#00e5ff",
    barColor:    "#00e5ff"
  }
};

// ── Select shark and start session ───────────────────────────────
async function selectShark(sharkKey) {
  SHARK_KEY = sharkKey;
  const cfg = SHARK_CONFIG[sharkKey];

  try {
    // Create session on backend
    const res  = await fetch(`${API}/session/new`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ shark: sharkKey })
    });
    const data = await res.json();
    SESSION_ID = data.session_id;

    // Update all shark UI elements
    updateSharkUI(sharkKey, data.shark, cfg);

    // Switch screens
    document.getElementById("selector-screen").style.display = "none";
    const chatScreen = document.getElementById("chat-screen");
    chatScreen.classList.add("visible");

    // Show session badge
    document.getElementById("session-badge").textContent =
      `SESSION ${SESSION_ID.toUpperCase()}`;

    // Clear messages and show opening message
    document.getElementById("messages-area").innerHTML = "";
    document.getElementById("analysis-banner").style.display = "none";

    // Show shark opening line
    appendMessage(data.opening, "bot", data.shark);
    updateStageDisplay("WAITING FOR PITCH");

  } catch (err) {
    alert(
      "Cannot connect to backend.\n" +
      "Make sure Flask is running:\n" +
      "cd backend → python app.py"
    );
  }
}

// ── Update all shark-themed UI ────────────────────────────────────
function updateSharkUI(sharkKey, sharkName, cfg) {
  // Sidebar
  document.getElementById("sidebar-avatar").textContent    = cfg.initials;
  document.getElementById("sidebar-avatar").className      =
    `sidebar-avatar ${cfg.avatarClass}`;
  document.getElementById("sidebar-shark-name").textContent = sharkName;

  const tagMap = {
    ashneer: "Brutal & Direct",
    namita:  "Analytical",
    aman:    "Brand Focused"
  };
  document.getElementById("sidebar-shark-tag").textContent =
    tagMap[sharkKey] || "";

  // Header
  document.getElementById("chat-header-avatar").textContent = cfg.initials;
  document.getElementById("chat-header-avatar").style.color =
    cfg.accentColor;
  document.getElementById("chat-header-avatar").style.borderColor =
    cfg.accentColor;
  document.getElementById("chat-header-name").textContent = sharkName;
}

// ── Send a message ────────────────────────────────────────────────
async function sendMessage() {
  if (isWaiting) return;

  const input = document.getElementById("chat-input");
  const text  = input.value.trim();
  if (!text) return;
  if (!SESSION_ID) {
    alert("No active session. Please select a shark first.");
    return;
  }

  // Clear input and show user message
  input.value = "";
  autoResizeTextarea(input);
  appendMessage(text, "user", "You");

  // Show typing indicator
  isWaiting = true;
  setInputLoading(true);
  const typingEl = showTyping();

  try {
    const res  = await fetch(`${API}/chat`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({
        session_id: SESSION_ID,
        message:    text
      })
    });

    const data = await res.json();
    removeTyping(typingEl);

    if (data.error) {
      appendMessage("Error: " + data.error, "bot", "System");
      return;
    }

    // Show bot response
    appendMessage(data.message, "bot", data.shark);

    // Update stage display
    const stageMap = {
      "greeting":   "WAITING FOR PITCH",
      "collecting": "COLLECTING INFO",
      "analyzing":  "VERDICT GIVEN",
      "followup":   "FOLLOW-UP",
      "reset":      "NEW PITCH"
    };
    updateStageDisplay(stageMap[data.stage] || data.stage.toUpperCase());

    // If analysis is included — show the banner
    if (data.analysis) {
      showAnalysisBanner(data.analysis);
    }

  } catch (err) {
    removeTyping(typingEl);
    appendMessage(
      "Cannot reach backend. Make sure python app.py is running.",
      "bot",
      "System"
    );
  } finally {
    isWaiting = false;
    setInputLoading(false);
    input.focus();
  }
}

// ── Quick action buttons ──────────────────────────────────────────
function sendQuick(text) {
  document.getElementById("chat-input").value = text;
  sendMessage();
}

// ── Change shark (go back to selector) ───────────────────────────
function changeShark() {
  SESSION_ID = null;
  document.getElementById("messages-area").innerHTML = "";
  document.getElementById("analysis-banner").style.display = "none";
  document.getElementById("chat-screen").classList.remove("visible");
  document.getElementById("selector-screen").style.display = "flex";
}

// ── Append message bubble ─────────────────────────────────────────
function appendMessage(text, role, name) {
  const area    = document.getElementById("messages-area");
  const cfg     = SHARK_CONFIG[SHARK_KEY];
  const isUser  = role === "user";
  const initials = isUser ? "YOU" : cfg.initials;

  const now     = new Date();
  const timeStr = now.getHours().toString().padStart(2,"0") + ":" +
                  now.getMinutes().toString().padStart(2,"0");

  const msgEl   = document.createElement("div");
  msgEl.className = `message ${isUser ? "user-message" : "bot-message"}`;

  msgEl.innerHTML = `
    <div class="message-avatar ${isUser ? "user-avatar" : "bot-avatar"}"
         style="${!isUser ? `color:${cfg.accentColor};border-color:${cfg.accentColor}40` : ""}">
      ${initials}
    </div>
    <div>
      <div class="message-bubble ${isUser ? "user-bubble" : "bot-bubble"}">
        ${escapeHtml(text)}
      </div>
      <div class="message-time">${timeStr}</div>
    </div>`;

  area.appendChild(msgEl);
  area.scrollTop = area.scrollHeight;
}

// ── Show analysis results banner ──────────────────────────────────
function showAnalysisBanner(analysis) {
  const banner  = document.getElementById("analysis-banner");
  const decision = analysis.decision || {};
  const prob     = analysis.investment_probability || 0;
  const scores   = analysis.scores || {};
  const cfg      = SHARK_CONFIG[SHARK_KEY];

  // Verdict
  const verdictEl = document.getElementById("banner-verdict");
  verdictEl.textContent = decision.decision || "—";
  verdictEl.className   = `banner-verdict ${decision.color || ""}`;

  // Probability
  document.getElementById("banner-prob").textContent = prob + "%";
  setTimeout(() => {
    const fill = document.getElementById("banner-prob-fill");
    fill.style.width      = prob + "%";
    fill.style.background = cfg.barColor;
  }, 200);

  // Score
  document.getElementById("banner-score").textContent =
    (scores.total_score || 0) + "/100";

  // Industry
  const extracted = analysis.extracted_data || {};
  document.getElementById("banner-industry").textContent =
    extracted.industry_detected || "—";

  banner.style.display = "block";
}

// ── Typing indicator ──────────────────────────────────────────────
function showTyping() {
  const area = document.getElementById("messages-area");
  const el   = document.createElement("div");
  el.className = "message bot-message";
  el.id        = "typing-indicator";
  el.innerHTML = `
    <div class="message-avatar bot-avatar"
         style="color:${SHARK_CONFIG[SHARK_KEY].accentColor}">
      ${SHARK_CONFIG[SHARK_KEY].initials}
    </div>
    <div class="typing-indicator">
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
    </div>`;
  area.appendChild(el);
  area.scrollTop = area.scrollHeight;
  return el;
}

function removeTyping(el) {
  if (el && el.parentNode) el.parentNode.removeChild(el);
}

// ── Stage display ─────────────────────────────────────────────────
function updateStageDisplay(text) {
  document.getElementById("stage-display").textContent = text;
}

// ── Input loading state ───────────────────────────────────────────
function setInputLoading(on) {
  const btn     = document.getElementById("btn-send");
  const sendTxt = document.getElementById("send-text");
  const spinner = document.getElementById("send-spinner");
  btn.disabled          = on;
  sendTxt.style.display = on ? "none" : "inline";
  spinner.style.display = on ? "block" : "none";
}

// ── Auto resize textarea ──────────────────────────────────────────
function autoResizeTextarea(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 120) + "px";
}

// ── Escape HTML to prevent XSS ────────────────────────────────────
function escapeHtml(text) {
  return text
    .replace(/&/g,  "&amp;")
    .replace(/</g,  "&lt;")
    .replace(/>/g,  "&gt;")
    .replace(/\n/g, "<br>");
}

// ── Keyboard shortcut — Enter to send ────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("chat-input");
  if (!input) return;

  input.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  input.addEventListener("input", () => autoResizeTextarea(input));
});