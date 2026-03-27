# backend/ai_engine.py
# ─────────────────────────────────────────────────────────────────
# This file contains ALL the intelligence of the app.
# No paid APIs needed. Pure Python logic + keyword analysis.
# ─────────────────────────────────────────────────────────────────

import re
import csv
import os
import random

# ── 1. KEYWORD DICTIONARIES ───────────────────────────────────────
# These are words the AI looks for in the pitch text.
# Each category has positive signals and negative signals.

REVENUE_KEYWORDS = {
    "positive": [
        "revenue", "profit", "sales", "income", "earning",
        "crore", "lakh", "million", "turnover", "mrr", "arr",
        "monthly recurring", "annual recurring", "profitable",
        "break even", "breakeven", "cash flow positive"
    ],
    "negative": [
        "no revenue", "pre-revenue", "zero revenue", "no sales",
        "not profitable", "losses", "burning cash", "no income"
    ]
}

GROWTH_KEYWORDS = {
    "positive": [
        "growing", "growth", "scaling", "expanding", "doubling",
        "tripling", "10x", "5x", "3x", "month on month", "yoy",
        "year on year", "users growing", "rapid", "exponential",
        "hockey stick", "traction", "momentum"
    ],
    "negative": [
        "slow growth", "stagnant", "declining", "decreasing",
        "shrinking", "no growth", "flat"
    ]
}

BUSINESS_MODEL_KEYWORDS = {
    "saas":        ["saas", "subscription", "monthly fee", "annual plan", "recurring"],
    "marketplace": ["marketplace", "platform", "two-sided", "buyers and sellers", "commission"],
    "d2c":         ["d2c", "direct to consumer", "direct-to-consumer", "ecommerce", "online store"],
    "b2b":         ["b2b", "business to business", "enterprise", "corporate clients", "companies"],
    "b2c":         ["b2c", "consumers", "end users", "retail", "customers"],
    "franchise":   ["franchise", "franchising", "license", "licensing model"],
    "freemium":    ["freemium", "free tier", "premium", "upsell", "upgrade"],
}

RISK_KEYWORDS = [
    "competition", "competitor", "crowded market", "regulated",
    "regulation", "patent pending", "no patent", "dependency",
    "single customer", "seasonal", "high burn", "debt", "loan",
    "legal issue", "lawsuit", "copied", "commodity"
]

POSITIVE_KEYWORDS = [
    "patent", "patented", "proprietary", "first mover", "unique",
    "exclusive", "award", "won", "featured", "partnership",
    "tie-up", "government contract", "backed", "celebrity",
    "viral", "organic growth", "word of mouth", "repeat customers",
    "high retention", "nps", "waitlist"
]

SCALABILITY_KEYWORDS = [
    "scalable", "scale", "pan india", "global", "international",
    "expand", "franchise", "white label", "api", "automated",
    "technology", "platform", "app", "software", "digital"
]

# ── 2. INDUSTRY QUESTION BANK ─────────────────────────────────────
# Investor questions tailored to each industry type.

INDUSTRY_QUESTIONS = {
    "tech": [
        "What is your monthly active user count and 30-day retention rate?",
        "How long will this funding last before you need the next round?",
        "What is your customer acquisition cost versus lifetime value?",
        "Who owns the IP — do you have patents or trade secrets?",
        "What stops a well-funded competitor from copying this in 6 months?"
    ],
    "food": [
        "What are your unit economics — cost per unit versus selling price?",
        "Have you cracked offline distribution or are you only online?",
        "What is your shelf life and what are your cold chain logistics?",
        "How do you maintain consistency at scale across locations?",
        "What is your gross margin after COGS and packaging?"
    ],
    "health": [
        "Have you got any clinical validation or regulatory approvals?",
        "What is your liability model if a patient outcome is poor?",
        "Are you working with insurance companies for reimbursement?",
        "What is your doctor or hospital acquisition strategy?",
        "How do you handle data privacy with patient information?"
    ],
    "edtech": [
        "What is your course completion rate — be honest?",
        "How do you prove learning outcomes to paying parents?",
        "What is your student acquisition cost and payback period?",
        "Are you NCERT aligned or completely independent curriculum?",
        "What happens to your business when schools reopen fully?"
    ],
    "finance": [
        "Are you RBI registered or do you hold an NBFC license?",
        "What is your NPA rate — what percentage of loans go bad?",
        "How do you underwrite risk for first-time borrowers?",
        "What is your regulatory moat — can anyone get the same license?",
        "Walk me through your unit economics on a Rs 10,000 loan."
    ],
    "default": [
        "What is your revenue model and how do you make money per transaction?",
        "Who is your biggest competitor and what is your defensible moat?",
        "What will you specifically use this funding for in the next 18 months?",
        "What is your customer acquisition cost and how does it trend?",
        "Why are you the right team to solve this problem?",
        "What does your month-on-month growth look like in hard numbers?",
        "If we don't invest, what happens to this business?",
        "Have you validated this with paying customers or just surveys?"
    ]
}

# ── 3. NUMBER EXTRACTION ──────────────────────────────────────────

def extract_numbers(text):
    """
    Finds revenue/funding numbers in the pitch text.
    Handles formats like: 50 lakh, 2 crore, 1.5 million, Rs 80L, $500K
    Returns a dict with found values converted to a standard number.
    """
    text_lower = text.lower()
    found = {}

    # Pattern: number followed by crore/cr
    crore_match = re.findall(r'(\d+\.?\d*)\s*(?:crore|cr\b)', text_lower)
    if crore_match:
        found["revenue_crore"] = float(crore_match[0])

    # Pattern: number followed by lakh/lac/L
    lakh_match = re.findall(r'(\d+\.?\d*)\s*(?:lakh|lac\b|\bl\b)', text_lower)
    if lakh_match:
        found["revenue_lakh"] = float(lakh_match[0])

    # Pattern: number followed by million
    million_match = re.findall(r'(\d+\.?\d*)\s*million', text_lower)
    if million_match:
        found["revenue_million"] = float(million_match[0])

    # Pattern: percentage equity
    equity_match = re.findall(r'(\d+\.?\d*)\s*%\s*(?:equity|stake)', text_lower)
    if equity_match:
        found["equity_offered"] = float(equity_match[0])

    # Plain large numbers (possible revenue figures)
    plain_numbers = re.findall(r'\b(\d{5,})\b', text_lower)
    if plain_numbers:
        found["large_number"] = int(plain_numbers[0])

    return found

# ── 4. KEYWORD SCORING ENGINE ─────────────────────────────────────

def score_pitch(text):
    """
    Scores the pitch across 5 dimensions.
    Each dimension returns 0–25 points.
    Total max = 100 points.
    Returns a dict of all scores + total.
    """
    text_lower = text.lower()
    scores = {
        "profitability": 0,
        "scalability":   0,
        "uniqueness":    0,
        "risk":          0,   # this score REDUCES the total
        "growth":        0,
    }

    # ── Profitability score (0–25) ──
    prof_score = 0
    for kw in REVENUE_KEYWORDS["positive"]:
        if kw in text_lower:
            prof_score += 5
    for kw in REVENUE_KEYWORDS["negative"]:
        if kw in text_lower:
            prof_score -= 8
    scores["profitability"] = max(0, min(25, prof_score))

    # ── Scalability score (0–25) ──
    scale_score = 0
    for kw in SCALABILITY_KEYWORDS:
        if kw in text_lower:
            scale_score += 4
    scores["scalability"] = max(0, min(25, scale_score))

    # ── Uniqueness score (0–25) ──
    unique_score = 0
    for kw in POSITIVE_KEYWORDS:
        if kw in text_lower:
            unique_score += 5
    scores["uniqueness"] = max(0, min(25, unique_score))

    # ── Risk score (0–25, PENALISES total) ──
    risk_count = 0
    for kw in RISK_KEYWORDS:
        if kw in text_lower:
            risk_count += 1
    scores["risk"] = min(25, risk_count * 6)

    # ── Growth score (0–25) ──
    growth_score = 0
    for kw in GROWTH_KEYWORDS["positive"]:
        if kw in text_lower:
            growth_score += 4
    for kw in GROWTH_KEYWORDS["negative"]:
        if kw in text_lower:
            growth_score -= 6
    scores["growth"] = max(0, min(25, growth_score))

    # ── Total: add positives, subtract risk ──
    total = (
        scores["profitability"] +
        scores["scalability"] +
        scores["uniqueness"] +
        scores["growth"] -
        scores["risk"]
    )
    scores["total"] = max(0, min(100, total))

    return scores

# ── 5. BUSINESS MODEL DETECTOR ────────────────────────────────────

def detect_business_model(text):
    """Identifies what type of business model the pitch describes."""
    text_lower = text.lower()
    found_models = []

    for model, keywords in BUSINESS_MODEL_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                found_models.append(model.upper())
                break

    return found_models if found_models else ["UNCLEAR"]

# ── 6. INDUSTRY DETECTOR ─────────────────────────────────────────

def detect_industry(text):
    """Maps pitch text to an industry category for tailored questions."""
    text_lower = text.lower()

    industry_map = {
        "tech":    ["app", "software", "saas", "platform", "api",
                    "ai", "ml", "algorithm", "tech", "digital", "cloud"],
        "food":    ["food", "restaurant", "snack", "beverage", "eat",
                    "kitchen", "chef", "recipe", "fmcg", "grocery"],
        "health":  ["health", "medical", "doctor", "hospital", "pharma",
                    "wellness", "fitness", "medicine", "clinic", "patient"],
        "edtech":  ["education", "learning", "school", "student", "course",
                    "skill", "training", "coaching", "tutor", "edtech"],
        "finance": ["finance", "fintech", "loan", "lending", "payment",
                    "banking", "insurance", "investment", "money", "credit"]
    }

    for industry, keywords in industry_map.items():
        for kw in keywords:
            if kw in text_lower:
                return industry

    return "default"

# ── 7. REVENUE ANALYSIS GENERATOR ────────────────────────────────

def generate_revenue_analysis(text, numbers, scores):
    """
    Writes a 3–4 sentence human-readable revenue analysis
    based on what was found in the pitch.
    """
    lines = []
    text_lower = text.lower()

    # Check for revenue mentions
    if numbers.get("revenue_crore"):
        val = numbers["revenue_crore"]
        if val >= 5:
            lines.append(
                f"The stated revenue of ₹{val} Crore demonstrates strong commercial traction "
                f"and positions this business well above the early-stage average."
            )
        elif val >= 1:
            lines.append(
                f"Revenue of ₹{val} Crore is a promising early indicator, but investors "
                f"will want to see a clear path to 10x growth within 3 years."
            )
        else:
            lines.append(
                f"With ₹{val} Crore in revenue, the business is still in an early "
                f"commercialisation phase. Sharks will scrutinise unit economics closely."
            )
    elif numbers.get("revenue_lakh"):
        val = numbers["revenue_lakh"]
        lines.append(
            f"Revenue of ₹{val} Lakh has been identified. "
            f"{'This is meaningful early traction.' if val >= 50 else 'Investors may view this as pre-scale stage.'}"
        )
    elif any(kw in text_lower for kw in REVENUE_KEYWORDS["negative"]):
        lines.append(
            "No revenue has been reported. This is a high-risk signal for most investors "
            "unless the product is deeply technology-driven with clear IP protection."
        )
    else:
        lines.append(
            "Revenue figures were not explicitly mentioned in the pitch. "
            "Investors will immediately ask for exact numbers — prepare them."
        )

    # Profitability comment
    if scores["profitability"] >= 20:
        lines.append(
            "The financial signals in this pitch are strong — multiple profitability "
            "indicators suggest a business with real unit economics."
        )
    elif scores["profitability"] >= 10:
        lines.append(
            "Some positive financial indicators are present but the picture is incomplete. "
            "A clear P&L breakdown would strengthen investor confidence."
        )
    else:
        lines.append(
            "The pitch lacks strong financial signals. Before walking into the tank, "
            "prepare exact revenue, margin, and burn rate figures."
        )

    # Growth comment
    if scores["growth"] >= 15:
        lines.append(
            "Growth momentum is clearly articulated — this is one of the strongest "
            "factors for investor conviction."
        )
    elif scores["growth"] >= 5:
        lines.append(
            "Some growth language is present but quantified metrics would be far more "
            "persuasive than qualitative claims."
        )

    return " ".join(lines)

# ── 8. QUESTION GENERATOR ─────────────────────────────────────────

def generate_questions(text, scores, industry):
    """
    Picks 4–5 investor-style questions relevant to the pitch.
    Combines industry-specific questions with score-based questions.
    """
    questions = []

    # Always start with industry-specific questions
    industry_qs = INDUSTRY_QUESTIONS.get(industry, INDUSTRY_QUESTIONS["default"])
    questions.extend(random.sample(industry_qs, min(3, len(industry_qs))))

    # Add score-based targeted questions
    if scores["profitability"] < 10:
        questions.append(
            "You haven't mentioned exact revenue numbers — what is your monthly revenue "
            "right now and what were you doing 12 months ago?"
        )

    if scores["risk"] > 15:
        questions.append(
            "I see multiple risk flags in your pitch — walk me through your biggest "
            "existential risk and how you are mitigating it."
        )

    if scores["scalability"] < 10:
        questions.append(
            "How does this business look at 100x the current size — what breaks "
            "and what infrastructure investment does that require?"
        )

    if scores["uniqueness"] < 5:
        questions.append(
            "What is genuinely proprietary here? Why can't a well-capitalised "
            "competitor simply replicate this in 90 days?"
        )

    # Remove duplicates and return 4–5
    seen = set()
    unique_questions = []
    for q in questions:
        if q not in seen:
            seen.add(q)
            unique_questions.append(q)

    return unique_questions[:5]

# ── 9. INVESTMENT PROBABILITY CALCULATOR ─────────────────────────

def calculate_probability(scores, numbers):
    """
    Weighted formula to calculate investment probability (0–100%).
    Weights are based on what real investors care about most.
    """
    # Base probability from scores
    # Weights: Growth 30%, Profitability 30%, Scalability 20%,
    #          Uniqueness 15%, Risk penalty 5%
    weighted = (
        (scores["growth"]        / 25) * 30 +
        (scores["profitability"] / 25) * 30 +
        (scores["scalability"]   / 25) * 20 +
        (scores["uniqueness"]    / 25) * 15 -
        (scores["risk"]          / 25) * 20    # risk reduces probability
    )

    probability = max(5, min(95, weighted))

    # Bonus for mentioned numbers (shows preparedness)
    if numbers.get("revenue_crore") and numbers["revenue_crore"] >= 1:
        probability = min(95, probability + 8)
    if numbers.get("equity_offered"):
        probability = min(95, probability + 3)

    return round(probability)

# ── 10. FINAL DECISION ENGINE ─────────────────────────────────────

def make_decision(probability, scores):
    """
    Converts probability + scores into a final investment decision.
    Returns decision label + reasoning text.
    """
    if probability >= 70:
        decision = "DEAL"
        color = "green"
        reasoning = (
            "This pitch demonstrates strong fundamentals across multiple dimensions. "
            "The combination of revenue traction, growth signals, and scalable model "
            "makes this an attractive investment opportunity."
        )
    elif probability >= 45:
        decision = "CONDITIONAL DEAL"
        color = "orange"
        reasoning = (
            "There is genuine potential here but unresolved concerns prevent an outright deal. "
            "A term sheet could be issued contingent on due diligence — particularly around "
            f"{'financials' if scores['profitability'] < 15 else 'competitive positioning'}."
        )
    else:
        decision = "NO DEAL"
        color = "red"
        reasoning = (
            "In its current form, this pitch does not meet investment thresholds. "
            "The primary gaps are "
            f"{'financial clarity' if scores['profitability'] < 10 else ''}"
            f"{' and ' if scores['profitability'] < 10 and scores['scalability'] < 10 else ''}"
            f"{'scalability evidence' if scores['scalability'] < 10 else ''}. "
            "Revisit the pitch after addressing these fundamentals."
        )

    return {"decision": decision, "color": color, "reasoning": reasoning}

# ── 11. DATASET COMPARISON ───────────────────────────────────────

def compare_with_dataset(industry_detected, probability):
    """
    Loads the JSON dataset and compares this pitch against
    historical Shark Tank data. Returns stats about deal rates.
    """
    import json

    # Path goes up one folder from backend/ into dataset/
    dataset_path = os.path.join(
        os.path.dirname(__file__), "..", "dataset", "shark_tank_data.json"
    )

    if not os.path.exists(dataset_path):
        return None

    try:
        # Read and parse the JSON file
        with open(dataset_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        startups = data.get("startups", [])
        total    = len(startups)

        if total == 0:
            return None

        # Count deals
        deals = sum(1 for s in startups if s.get("deal_status") == "Deal")
        deal_rate = round((deals / total) * 100)

        # Find similar industry entries
        similar = [
            s for s in startups
            if s.get("industry", "").lower() == industry_detected.lower()
        ]
        similar_deal_rate = None
        if similar:
            similar_deals = sum(
                1 for s in similar if s.get("deal_status") == "Deal"
            )
            similar_deal_rate = round((similar_deals / len(similar)) * 100)

        # Find highest revenue startup that got a deal
        deal_startups = [s for s in startups if s.get("deal_status") == "Deal"]
        top_startup   = max(
            deal_startups, key=lambda x: x.get("revenue", 0), default=None
        )

        return {
            "total_in_dataset":       total,
            "historical_deal_rate":   deal_rate,
            "your_probability_vs_avg": "above" if probability > deal_rate else "below",
            "similar_industry_count": len(similar),
            "similar_deal_rate":      similar_deal_rate,
            "top_deal_example":       top_startup.get("startup_name") if top_startup else None,
        }

    except Exception as e:
        print(f"JSON dataset error: {e}")
        return None

# ── 12. MASTER ANALYZE FUNCTION ──────────────────────────────────

def analyze_pitch(pitch_text):
    """
    THE MAIN FUNCTION — called by Flask.
    Takes raw pitch text, returns complete structured analysis.
    This is the only function Flask needs to call.
    """

    if not pitch_text or len(pitch_text.strip()) < 20:
        return {
            "error": "Pitch text is too short. Please provide at least 2-3 sentences."
        }

    # Run all analysis steps
    numbers        = extract_numbers(pitch_text)
    scores         = score_pitch(pitch_text)
    business_model = detect_business_model(pitch_text)
    industry       = detect_industry(pitch_text)
    probability    = calculate_probability(scores, numbers)
    decision_data  = make_decision(probability, scores)
    revenue_analysis = generate_revenue_analysis(pitch_text, numbers, scores)
    questions      = generate_questions(pitch_text, scores, industry)
    dataset_stats  = compare_with_dataset(industry, probability)

    # Build the final JSON response
    return {
        "status": "success",
        "extracted_data": {
            "numbers_found":    numbers,
            "business_models":  business_model,
            "industry_detected": industry.upper(),
        },
        "scores": {
            "profitability": scores["profitability"],
            "scalability":   scores["scalability"],
            "uniqueness":    scores["uniqueness"],
            "growth":        scores["growth"],
            "risk_penalty":  scores["risk"],
            "total_score":   scores["total"],
        },
        "revenue_analysis": revenue_analysis,
        "investor_questions": questions,
        "investment_probability": probability,
        "decision": decision_data,
        "dataset_comparison": dataset_stats,
    }