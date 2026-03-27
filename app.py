# backend/app.py
# Chat-enabled version — remembers conversation history per session

from flask import Flask, request, jsonify
from flask_cors import CORS
from ai_engine import analyze_pitch
import uuid, re, json, os

app = Flask(__name__)
CORS(app)

# ── In-memory conversation store ──────────────────────────────────
# Key = session_id string
# Value = { "history": [...], "pitch_data": {...}, "stage": "..." }
# Stage can be: "greeting" | "collecting" | "analyzing" | "followup"
SESSIONS = {}

# ── Shark personas ────────────────────────────────────────────────
SHARK_PERSONAS = {
    "ashneer": {
        "name": "Ashneer Grover",
        "style": "brutal",
        "greeting": "Bhai, seedha baat kar. What is your business and why should I care?",
        "deal_response": "Theek hai. Numbers make sense. I'm in — but I want my equity protected.",
        "no_deal_response": "Yeh toh bahut ganda pitch tha. Completely out. Next.",
        "conditional_response": "Idea is okay but execution is weak. Come back with better numbers.",
        "follow_ups": [
            "What is your monthly burn rate right now?",
            "How many months of runway do you have left?",
            "Why hasn't a big company already done this?",
            "What happens to my money if this fails in 6 months?",
        ]
    },
    "namita": {
        "name": "Namita Thapar",
        "style": "analytical",
        "greeting": "Hello! Tell me about your startup. I want to understand the problem you are solving and your numbers.",
        "deal_response": "I love the fundamentals here. Strong unit economics and a clear market. I would like to invest.",
        "no_deal_response": "I appreciate your passion but the numbers don't support the valuation. Not for me.",
        "conditional_response": "There is potential but I need clarity on your regulatory compliance and margins before I commit.",
        "follow_ups": [
            "What are your exact gross margins after all costs?",
            "Have you done any clinical or third-party validation?",
            "What is your customer acquisition cost versus lifetime value?",
            "Walk me through your next 18-month roadmap specifically.",
        ]
    },
    "aman": {
        "name": "Aman Gupta",
        "style": "brand-focused",
        "greeting": "Hey! Excited to hear your pitch. Tell me — what is your brand story and who is your customer?",
        "deal_response": "I love the brand potential here. I can see this becoming a household name. I'm in!",
        "no_deal_response": "The brand story isn't strong enough for me. I don't see the mass market potential.",
        "conditional_response": "Love the energy but the brand positioning needs work. Let's talk more about your D2C strategy.",
        "follow_ups": [
            "What is your social media presence and organic reach like?",
            "How are you building brand loyalty beyond the first purchase?",
            "What is your repeat purchase rate and how do you measure brand love?",
            "If I walked into a store, how would your product stand out on the shelf?",
        ]
    }
}

# ── Conversation response generator ──────────────────────────────
def generate_chat_response(session_id, user_message):
    """
    Core chatbot logic. Reads conversation history,
    figures out what stage we are at, and generates
    the next appropriate response.
    """
    session   = SESSIONS.get(session_id, {})
    history   = session.get("history", [])
    stage     = session.get("stage", "greeting")
    pitch_data = session.get("pitch_data", {})
    shark_key = session.get("shark", "namita")
    shark     = SHARK_PERSONAS[shark_key]

    msg_lower = user_message.lower()

    # ── Stage: greeting — first message ──────────────────────────
    if stage == "greeting" or len(history) == 0:
        # Check if user chose a shark
        if "ashneer" in msg_lower:
            shark_key = "ashneer"
        elif "aman" in msg_lower:
            shark_key = "aman"
        else:
            shark_key = "namita"

        shark = SHARK_PERSONAS[shark_key]
        SESSIONS[session_id]["shark"]  = shark_key
        SESSIONS[session_id]["stage"]  = "collecting"

        return {
            "message": shark["greeting"],
            "shark":   shark["name"],
            "stage":   "collecting",
            "type":    "shark_message"
        }

    # ── Stage: collecting — gather pitch info ─────────────────────
    if stage == "collecting":
        # Check if we have enough info to analyze
        has_revenue   = any(w in msg_lower for w in ["crore","lakh","revenue","sales","million","profit"])
        has_business  = len(user_message.split()) >= 15
        has_ask       = any(w in msg_lower for w in ["asking","invest","equity","stake","%"])

        if has_business and (has_revenue or has_ask):
            # We have enough — run the AI engine
            analysis = analyze_pitch(user_message)
            SESSIONS[session_id]["pitch_data"] = analysis
            SESSIONS[session_id]["stage"]      = "analyzing"
            SESSIONS[session_id]["full_pitch"] = user_message

            # Build shark-style response based on decision
            decision = analysis.get("decision", {})
            verdict  = decision.get("decision", "NO DEAL")
            prob     = analysis.get("investment_probability", 0)
            scores   = analysis.get("scores", {})

            if verdict == "DEAL":
                shark_comment = shark["deal_response"]
            elif verdict == "CONDITIONAL DEAL":
                shark_comment = shark["conditional_response"]
            else:
                shark_comment = shark["no_deal_response"]

            # Pick one relevant follow-up question
            import random
            follow_up = random.choice(shark["follow_ups"])

            response_text = (
                f"{shark_comment}\n\n"
                f"My analysis: {analysis.get('revenue_analysis','')}\n\n"
                f"But I have one important question — {follow_up}"
            )

            return {
                "message":     response_text,
                "shark":       shark["name"],
                "stage":       "analyzing",
                "type":        "analysis",
                "analysis":    analysis,
                "follow_up":   follow_up
            }

        else:
            # Need more information — ask a clarifying question
            clarify_questions = [
                "Interesting. But give me the numbers — what is your revenue right now?",
                "Okay, I hear you. But what is your business model? How exactly do you make money?",
                "Tell me more. How much are you asking for and what equity are you offering?",
                "What problem are you solving and who is paying you for it right now?",
            ]
            import random
            clarify = random.choice(clarify_questions)

            return {
                "message": clarify,
                "shark":   shark["name"],
                "stage":   "collecting",
                "type":    "clarification"
            }

    # ── Stage: analyzing — handle follow-up conversation ─────────
    if stage == "analyzing":
        analysis = pitch_data
        scores   = analysis.get("scores", {})
        prob     = analysis.get("investment_probability", 0)
        import random

        # Detect what the user is responding to
        if any(w in msg_lower for w in ["thank","thanks","okay","ok","understood","got it"]):
            return {
                "message": (
                    f"Good. Now remember — {random.choice(shark['follow_ups'])} "
                    f"These are the things that will make or break your deal. "
                    f"Your overall score is {scores.get('total_score',0)}/100. "
                    f"Type 'new pitch' to start over or keep asking me questions."
                ),
                "shark": shark["name"],
                "stage": "followup",
                "type":  "followup"
            }

        elif any(w in msg_lower for w in ["why","explain","reason","how","what"]):
            # User wants explanation
            questions = analysis.get("investor_questions", [])
            q_text    = "\n".join(f"• {q}" for q in questions[:3])
            return {
                "message": (
                    f"Here is why I gave this verdict:\n\n"
                    f"Profitability score: {scores.get('profitability',0)}/25\n"
                    f"Scalability score: {scores.get('scalability',0)}/25\n"
                    f"Growth score: {scores.get('growth',0)}/25\n"
                    f"Uniqueness score: {scores.get('uniqueness',0)}/25\n"
                    f"Risk penalty: -{scores.get('risk_penalty',0)}/25\n\n"
                    f"The key questions you still need to answer:\n{q_text}"
                ),
                "shark": shark["name"],
                "stage": "analyzing",
                "type":  "explanation"
            }

        elif any(w in msg_lower for w in ["new pitch","restart","start over","reset","another"]):
            # Reset session
            SESSIONS[session_id] = {
                "history": [],
                "stage":   "greeting",
                "shark":   shark_key,
                "pitch_data": {}
            }
            return {
                "message": f"Alright, let's hear the next pitch. Go ahead — {shark['greeting']}",
                "shark":   shark["name"],
                "stage":   "collecting",
                "type":    "reset"
            }

        elif any(w in msg_lower for w in ["improve","better","suggestion","advice","tip"]):
            # User wants improvement advice
            advice = analysis.get("pitch_score", {}).get("advice", [])
            if not advice:
                # Generate advice from scores
                advice = []
                if scores.get("profitability", 0) < 15:
                    advice.append("Strengthen your financial story — exact revenue, margins, and burn rate.")
                if scores.get("scalability", 0) < 15:
                    advice.append("Show how this scales — technology, automation, or franchise model.")
                if scores.get("uniqueness", 0) < 10:
                    advice.append("Define your moat — patent, proprietary tech, or exclusive partnerships.")
                if scores.get("growth", 0) < 10:
                    advice.append("Quantify your growth — month on month numbers, not vague claims.")

            advice_text = "\n".join(f"• {a}" for a in advice[:4])
            return {
                "message": (
                    f"Here is how you can improve this pitch before coming back:\n\n"
                    f"{advice_text}\n\n"
                    f"Your current probability is {prob}%. Fix these and it could go up significantly."
                ),
                "shark": shark["name"],
                "stage": "analyzing",
                "type":  "advice"
            }

        else:
            # General follow-up conversation
            follow_up = random.choice(shark["follow_ups"])
            return {
                "message": (
                    f"That's noted. But my biggest concern remains — {follow_up} "
                    f"Answer that and we can talk further."
                ),
                "shark": shark["name"],
                "stage": "analyzing",
                "type":  "followup"
            }

    # Fallback
    return {
        "message": "Tell me about your startup and I will give you my honest verdict.",
        "shark":   shark["name"],
        "stage":   "collecting",
        "type":    "fallback"
    }

# ── Routes ────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "SharkAI Chatbot API running", "version": "2.0"})

@app.route("/session/new", methods=["POST"])
def new_session():
    """Creates a new chat session and returns a session ID."""
    session_id = str(uuid.uuid4())[:8]
    data       = request.get_json() or {}
    shark_pref = data.get("shark", "namita").lower()

    if shark_pref not in SHARK_PERSONAS:
        shark_pref = "namita"

    SESSIONS[session_id] = {
        "history":    [],
        "stage":      "greeting",
        "shark":      shark_pref,
        "pitch_data": {}
    }

    shark = SHARK_PERSONAS[shark_pref]
    return jsonify({
        "session_id":  session_id,
        "shark":       shark["name"],
        "opening":     shark["greeting"],
        "shark_style": shark["style"]
    })

@app.route("/chat", methods=["POST"])
def chat():
    """Main chat endpoint — receives message, returns response."""
    data       = request.get_json()

    if not data:
        return jsonify({"error": "No data sent."}), 400

    session_id  = data.get("session_id", "")
    user_message = data.get("message", "").strip()

    if not session_id or session_id not in SESSIONS:
        return jsonify({"error": "Invalid session. Call /session/new first."}), 400

    if not user_message:
        return jsonify({"error": "Message cannot be empty."}), 400

    # Save user message to history
    SESSIONS[session_id]["history"].append({
        "role":    "user",
        "content": user_message
    })

    # Generate response
    response = generate_chat_response(session_id, user_message)

    # Save bot response to history
    SESSIONS[session_id]["history"].append({
        "role":    "assistant",
        "content": response["message"]
    })

    # Trim history to last 20 messages
    SESSIONS[session_id]["history"] = SESSIONS[session_id]["history"][-20:]

    return jsonify(response)

@app.route("/chat/history/<session_id>", methods=["GET"])
def get_history(session_id):
    """Returns full conversation history for a session."""
    if session_id not in SESSIONS:
        return jsonify({"error": "Session not found."}), 404
    return jsonify({
        "history": SESSIONS[session_id]["history"],
        "stage":   SESSIONS[session_id]["stage"],
        "shark":   SESSIONS[session_id].get("shark", "namita")
    })

# Keep old /analyze endpoint working too
@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data."}), 400
    pitch_text = data.get("pitch", "")
    if not pitch_text or len(pitch_text.strip()) < 20:
        return jsonify({"error": "Pitch too short."}), 400
    return jsonify(analyze_pitch(pitch_text))

if __name__ == "__main__":
    print("=" * 50)
    print("  SharkAI Chatbot Backend v2.0")
    print("  Running on http://127.0.0.1:5000")
    print("=" * 50)
    app.run(debug=True, port=5000)