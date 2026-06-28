from __future__ import annotations

SYSTEM_STYLE = (
    "You are a helpful support chatbot for the AI Image Checker website. "
    "Be friendly, concise, and practical. "
    "Only answer questions related to using the website, scan results, feedback, admin dashboard, or troubleshooting. "
    "If the user asks unrelated questions, politely refuse and ask them to contact the site owner."
)

FAQ = [
    ("how accurate", "This detector is an indicator, not a proof. If an image was compressed or metadata removed, confidence may drop. Use the reasons + signals, and treat 'Unknown' as normal."),
    ("unknown", "Unknown means signals are weak or conflicting. This is intentional to avoid false certainty."),
    ("why ai", "Common reasons: AI-tool metadata, AI-detector model score high, or forensic signals that match synthetic patterns."),
    ("feedback", "If the result is wrong, click Wrong and leave a short note. It will be sent to admin to improve detection."),
    ("admin", "Admin dashboard is for the site owner only. It requires an admin token and shows user feedback."),
    ("error", "Most common fixes: restart backend, check NEXT_PUBLIC_BACKEND_URL, and ensure CORS allows http://localhost:3000."),
]

def reply(user_message: str, last_result: dict | None = None) -> str:
    msg = (user_message or "").strip()
    low = msg.lower()

    # Refuse unrelated topics
    allowed_keywords = [
        "scan", "analyze", "upload", "image", "result", "confidence", "unknown",
        "feedback", "wrong", "correct", "admin", "token", "backend", "frontend",
        "error", "cors", "api key", "reason", "signals"
    ]
    if not any(k in low for k in allowed_keywords):
        return (
            "I can only help with questions about this website (scan results, feedback, errors, admin). "
            "For other topics, please contact the site owner."
        )

    # Context-aware help
    if last_result and ("result" in low or "why" in low or "reason" in low):
        label = last_result.get("label")
        conf = last_result.get("confidence")
        reasons = last_result.get("reasons") or []
        rtxt = "\n".join([f"- {r}" for r in reasons[:6]]) if reasons else "- (no reasons returned)"
        return (
            f"Your last scan looks like: {label} with confidence {conf}. "
            f"Here are the main reasons:\n{rtxt}\n"
            "If you believe it's wrong, click Wrong and leave a short note."
        )

    for k, ans in FAQ:
        if k in low:
            return ans

    return "Tell me what you’re trying to do (upload/scan/feedback/admin/troubleshooting) and what you see on screen."
