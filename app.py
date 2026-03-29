# app.py — SharkAI Merged Backend
# Gemini AI + structured pitch collection + live score updates

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import uuid, os, json
import google.generativeai as genai

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
CORS(app)

# ── Gemini setup ──────────────────────────────────────────────────
genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ")
gemini_model = genai.GenerativeModel("gemini-2.5-flash")

# ── Load dataset ──────────────────────────────────────────────────
DATASET_PATH = os.path.join(BASE_DIR, "dataset.json")
DATASET = []
if os.path.exists(DATASET_PATH):
    with open(DATASET_PATH, "r") as f:
        DATASET = json.load(f)

# ── Serve frontend ────────────────────────────────────────────────
@app.route("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")

@app.route("/style.css")
def serve_css():
    return send_from_directory(BASE_DIR, "style.css")

@app.route("/script.js")
def serve_js():
    return send_from_directory(BASE_DIR, "script.js")

# ── Sessions store ────────────────────────────────────────────────
# Each session: { history, stage, shark, pitch_fields, scores, chat_count }
# stage: "collecting" | "analyzing" | "followup"
# pitch_fields collected one by one:
#   name, sector, revenue, users, ask, equity, description
SESSIONS = {}

REQUIRED_FIELDS = ["name", "sector", "revenue", "users", "ask", "equity", "description"]

FIELD_QUESTIONS = {
    "name":        "What's the name of your startup?",
    "sector":      "What sector or industry is it in? (e.g. FinTech, EdTech, Food, Health...)",
    "revenue":     "What is your current monthly revenue? (Be specific — crore, lakh, etc.)",
    "users":       "How many users or customers do you have right now?",
    "ask":         "How much investment are you asking for?",
    "equity":      "What percentage of equity are you offering in return?",
    "description": "Give me your full pitch — the problem you solve, your solution, traction, and why you'll win."
}

# ── Shark personas ────────────────────────────────────────────────
SHARK_PERSONAS = {
    "ashneer": {
        "name": "Ashneer Grover",
        "style": "brutal and blunt. You speak in a mix of Hindi and English (Hinglish). You are direct, no-nonsense, and tear apart weak numbers immediately. You say things like 'Bhai', 'seedha baat kar', and 'yeh toh ganda hai'. You respect hustle but despise dishonesty.",
        "greeting": "Bhai, seedha baat kar. What is your business and why should I care? Let's not waste time.",
    },
    "namita": {
        "name": "Namita Thapar",
        "style": "analytical and data-driven. You focus heavily on unit economics, margins, regulatory clarity, and market size. You are thorough and professional but warm. You always want exact numbers, not approximations.",
        "greeting": "Hello! I'm excited to hear your pitch. Tell me — what problem are you solving and who is your customer?",
    },
    "aman": {
        "name": "Aman Gupta",
        "style": "brand-focused and enthusiastic. You built boAt from scratch so you love D2C brands, consumer stories, social media traction, and brand differentiation. You get excited about products with mass market potential.",
        "greeting": "Hey! Super excited to hear this. Tell me — what's your brand story and who are you building this for?",
    }
}

# ── RAG context builder ───────────────────────────────────────────
def build_rag_context(sector):
    if not DATASET:
        return ""
    sector_lower = sector.lower()
    relevant = [d for d in DATASET if sector_lower in d.get("sector", "").lower()]
    if not relevant:
        relevant = DATASET[:2]
    context = "Past Shark Tank Cases for reference:\n"
    for d in relevant[:2]:
        context += f"- {d['startup']} | Sector: {d['sector']} | Revenue: {d['revenue']} | Ask: {d['ask']} | Outcome: {d['outcome']}\n"
    return context

# ── Score calculator (keyword-based, instant) ─────────────────────
def calculate_scores(fields):
    """Quick keyword-based scoring from collected pitch fields."""
    import re
    text = " ".join(str(v) for v in fields.values()).lower()

    # Profitability: revenue signals
    prof = 0
    for kw in ["crore", "lakh", "million", "revenue", "profit", "sales", "mrr", "arr", "profitable"]:
        if kw in text: prof += 5
    for kw in ["no revenue", "pre-revenue", "zero revenue"]:
        if kw in text: prof -= 10
    profitability = max(0, min(25, prof))

    # Scalability
    scale = 0
    for kw in ["scalable", "scale", "pan india", "global", "platform", "app", "software", "digital", "automated", "api"]:
        if kw in text: scale += 4
    scalability = max(0, min(25, scale))

    # Uniqueness
    unique = 0
    for kw in ["patent", "proprietary", "unique", "exclusive", "first mover", "award", "viral", "partnership"]:
        if kw in text: unique += 5
    uniqueness = max(0, min(25, unique))

    # Growth
    growth = 0
    for kw in ["growing", "growth", "scaling", "10x", "traction", "momentum", "doubling", "month on month"]:
        if kw in text: growth += 4
    for kw in ["declining", "stagnant", "no growth", "flat"]:
        if kw in text: growth -= 6
    growth_score = max(0, min(25, growth))

    # Risk
    risk = 0
    for kw in ["competition", "regulated", "no patent", "debt", "loan", "seasonal", "single customer"]:
        if kw in text: risk += 6
    risk_score = max(0, min(25, risk))

    # Revenue number bonus
    revenue_text = fields.get("revenue", "")
    crore_match = re.findall(r'(\d+\.?\d*)\s*(?:crore|cr\b)', revenue_text.lower())
    if crore_match and float(crore_match[0]) >= 1:
        profitability = min(25, profitability + 5)

    total = max(0, min(100, profitability + scalability + uniqueness + growth_score - risk_score))

    # Investment probability
    prob = (
        (growth_score / 25) * 30 +
        (profitability / 25) * 30 +
        (scalability / 25) * 20 +
        (uniqueness / 25) * 15 -
        (risk_score / 25) * 20
    )
    probability = max(5, min(95, round(prob)))

    return {
        "profitability": profitability,
        "scalability":   scalability,
        "uniqueness":    uniqueness,
        "growth":        growth_score,
        "risk_penalty":  risk_score,
        "total_score":   total,
        "probability":   probability
    }

# ── Gemini AI call ────────────────────────────────────────────────
def call_gemini(shark_key, fields, user_message, history, mode="chat"):
    shark = SHARK_PERSONAS[shark_key]
    rag_context = build_rag_context(fields.get("sector", ""))

    pitch_summary = f"""
Startup: {fields.get('name', 'Unknown')}
Sector: {fields.get('sector', 'Unknown')}
Monthly Revenue: {fields.get('revenue', 'Not specified')}
Users: {fields.get('users', 'Not specified')}
Investment Ask: {fields.get('ask', 'Not specified')}
Equity Offered: {fields.get('equity', 'Not specified')}
Pitch: {fields.get('description', 'Not provided')}
"""

    history_text = ""
    for msg in history[-6:]:  # last 6 messages for context
        role = "Investor" if msg["role"] == "assistant" else "Founder"
        history_text += f"{role}: {msg['content']}\n"

    if mode == "verdict":
        prompt = f"""You are {shark['name']}, a Shark Tank India investor.
Your personality: {shark['style']}

{rag_context}

The founder has just finished their pitch:
{pitch_summary}

Give your INITIAL VERDICT. In character as {shark['name']}:
1. React to the pitch in your personality style (2-3 sentences)
2. State your verdict clearly: DEAL, CONDITIONAL DEAL, or NO DEAL
3. Give your top 2 concerns or praise points
4. Ask ONE sharp follow-up question

Keep it under 150 words. Be in character throughout."""

    else:
        prompt = f"""You are {shark['name']}, a Shark Tank India investor.
Your personality: {shark['style']}

The startup being pitched:
{pitch_summary}

Conversation so far:
{history_text}

The founder just said: "{user_message}"

Respond in character as {shark['name']}. Be sharp, relevant, and true to your personality.
Ask follow-up questions if needed. Keep under 120 words."""

    try:
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"[AI Error: {str(e)}. Check your Gemini API key.]"

# ── Routes ────────────────────────────────────────────────────────

@app.route("/session/new", methods=["POST"])
def new_session():
    data       = request.get_json() or {}
    shark_pref = data.get("shark", "namita").lower()
    if shark_pref not in SHARK_PERSONAS:
        shark_pref = "namita"

    session_id = str(uuid.uuid4())[:8]
    SESSIONS[session_id] = {
        "history":      [],
        "stage":        "collecting",
        "shark":        shark_pref,
        "pitch_fields": {},
        "scores":       None,
        "chat_count":   0,
        "current_field": "name"  # first field to collect
    }

    shark = SHARK_PERSONAS[shark_pref]
    opening = f"{shark['greeting']}\n\nFirst — {FIELD_QUESTIONS['name']}"

    return jsonify({
        "session_id": session_id,
        "shark":      shark["name"],
        "opening":    opening,
    })


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data sent."}), 400

    session_id   = data.get("session_id", "")
    user_message = data.get("message", "").strip()

    if not session_id or session_id not in SESSIONS:
        return jsonify({"error": "Invalid session."}), 400
    if not user_message:
        return jsonify({"error": "Empty message."}), 400

    session   = SESSIONS[session_id]
    shark_key = session["shark"]
    shark     = SHARK_PERSONAS[shark_key]
    stage     = session["stage"]
    fields    = session["pitch_fields"]

    # Save user message
    session["history"].append({"role": "user", "content": user_message})

    # ── STAGE: collecting fields one by one ───────────────────────
    if stage == "collecting":
        current_field = session["current_field"]

        # Save the answer to the current field
        fields[current_field] = user_message

        # Find next missing field
        next_field = None
        for f in REQUIRED_FIELDS:
            if f not in fields:
                next_field = f
                break

        if next_field:
            # Ask the next field question, with a brief shark-flavoured ack
            acks = {
                "ashneer": ["Theek hai.", "Haan.", "Samjha.", "Noted."],
                "namita":  ["Got it.", "Thank you.", "Noted.", "Understood."],
                "aman":    ["Nice!", "Cool.", "Got it!", "Awesome."]
            }
            import random
            ack = random.choice(acks[shark_key])
            reply = f"{ack} {FIELD_QUESTIONS[next_field]}"
            session["current_field"] = next_field
            session["history"].append({"role": "assistant", "content": reply})
            session["history"] = session["history"][-30:]

            return jsonify({
                "message": reply,
                "shark":   shark["name"],
                "stage":   "collecting",
                "field_collected": current_field,
                "next_field":      next_field,
                "fields_done":     len(fields),
                "fields_total":    len(REQUIRED_FIELDS)
            })

        else:
            # All fields collected — run scoring + Gemini verdict
            scores  = calculate_scores(fields)
            session["scores"] = scores
            session["stage"]  = "analyzing"

            # Get Gemini verdict
            ai_response = call_gemini(shark_key, fields, user_message, session["history"], mode="verdict")

            session["history"].append({"role": "assistant", "content": ai_response})
            session["history"] = session["history"][-30:]

            return jsonify({
                "message":  ai_response,
                "shark":    shark["name"],
                "stage":    "analyzing",
                "scores":   scores,
                "analysis": {
                    "scores":                 scores,
                    "investment_probability": scores["probability"],
                    "decision": {
                        "decision": "DEAL" if scores["probability"] >= 70 else ("CONDITIONAL DEAL" if scores["probability"] >= 45 else "NO DEAL"),
                        "color":    "green" if scores["probability"] >= 70 else ("orange" if scores["probability"] >= 45 else "red")
                    },
                    "extracted_data": {
                        "industry_detected": fields.get("sector", "—").upper()
                    }
                }
            })

    # ── STAGE: analyzing / followup — free Gemini chat ───────────
    else:
        session["chat_count"] += 1

        # Recalculate scores with accumulated conversation context
        # Build a richer text from all conversation
        all_text = " ".join(fields.values()) + " " + " ".join(
            m["content"] for m in session["history"] if m["role"] == "user"
        )
        updated_scores = calculate_scores({"description": all_text})
        session["scores"] = updated_scores

        ai_response = call_gemini(shark_key, fields, user_message, session["history"], mode="chat")

        session["history"].append({"role": "assistant", "content": ai_response})
        session["history"] = session["history"][-30:]

        # Reset if user wants new pitch
        if any(w in user_message.lower() for w in ["new pitch", "start over", "restart", "reset"]):
            SESSIONS[session_id] = {
                "history":       [],
                "stage":         "collecting",
                "shark":         shark_key,
                "pitch_fields":  {},
                "scores":        None,
                "chat_count":    0,
                "current_field": "name"
            }
            reset_msg = f"Alright, fresh start! {shark['greeting']}\n\nFirst — {FIELD_QUESTIONS['name']}"
            return jsonify({
                "message": reset_msg,
                "shark":   shark["name"],
                "stage":   "collecting",
            })

        return jsonify({
            "message":        ai_response,
            "shark":          shark["name"],
            "stage":          "followup",
            "updated_scores": updated_scores,
        })


if __name__ == "__main__":
    print("=" * 55)
    print("  SharkAI — Merged Backend")
    print("  Open http://127.0.0.1:5000 in your browser")
    print("  Make sure GEMINI_API_KEY is set!")
    print("=" * 55)
    app.run(debug=True, port=5000)
