import time
from typing import List, Literal

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from forensics import read_exif, is_jpeg, sharpness_score
from upload_guard import safe_decode_image
from model import predict_label_confidence
from explain import build_reasons
from security import require_api_key, rate_limit
from logger import audit_analyze, audit_chat

app = FastAPI()

# Allow Next.js dev server to call FastAPI during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "ok"}


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/analyze")
async def analyze(request: Request, file: UploadFile = File(...)):
    t0 = time.time()
    ip = request.client.host if request.client else "unknown"

    try:
        # --- Security ---
        require_api_key(request)
        rate_limit(request)

        # Quick header check (still keep magic-bytes check in safe_decode_image)
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")

        # Read bytes
        content = await file.read()

        # Hardened upload validation + safe decode
        img, img_type = safe_decode_image(content)
        w, h = img.size

        # ---- Forensics signals ----
        exif = read_exif(content)
        jpeg = is_jpeg(content)
        sharp = sharpness_score(img)

        # ---- Simple heuristic scoring (baseline) ----
        score_ai = 0.0
        software = (exif.get("EXIF Software") or exif.get("Image Software") or "").lower()

        ai_keywords = [
            "stable diffusion",
            "midjourney",
            "dall-e",
            "comfyui",
            "automatic1111",
            "firefly",
            "generative",
        ]
        edit_keywords = ["photoshop", "lightroom", "snapseed", "facetune"]

        if any(k in software for k in ai_keywords):
            score_ai += 0.60

        if any(k in software for k in edit_keywords):
            score_ai += 0.25

        if sharp < 0.08:
            score_ai += 0.15

        if len(exif) == 0:
            score_ai -= 0.10

        score_ai = max(0.0, min(score_ai, 1.0))

        signals = {
            "width": w,
            "height": h,
            "image_type": img_type,
            "jpeg": jpeg,
            "sharpness_score": round(sharp, 3),
            "exif": exif,
            "score_ai": round(score_ai, 3),
        }

        # --- Model decision (4B) ---
        # model.py should define: predict_label_confidence(signals, img) -> (label, confidence, extra)
        label, confidence, extra = predict_label_confidence(signals, img)

        # Explain why
        reasons = build_reasons(label, signals, extra)

        latency_ms = int((time.time() - t0) * 1000)

        # Audit log success
        audit_analyze(
            ip=ip,
            method=request.method,
            path=request.url.path,
            status_code=200,
            latency_ms=latency_ms,
            filename=file.filename,
            content_type=file.content_type,
            size_bytes=len(content),
            image_type=img_type,
            width=w,
            height=h,
            label=label,
            confidence=round(float(confidence), 3),
        )

        return {
            "label": label,
            "confidence": round(float(confidence), 3),
            "signals": signals,
            "extra": extra,
            "reasons": reasons,
        }

    except HTTPException as e:
        latency_ms = int((time.time() - t0) * 1000)
        audit_analyze(
            ip=ip,
            method=request.method,
            path=request.url.path,
            status_code=e.status_code,
            latency_ms=latency_ms,
            filename=getattr(file, "filename", None),
            content_type=getattr(file, "content_type", None),
            blocked_reason=str(e.detail),
        )
        raise

    except Exception:
        latency_ms = int((time.time() - t0) * 1000)
        audit_analyze(
            ip=ip,
            method=request.method,
            path=request.url.path,
            status_code=500,
            latency_ms=latency_ms,
            filename=getattr(file, "filename", None),
            content_type=getattr(file, "content_type", None),
            blocked_reason="Internal server error",
        )
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------
# Chatbot (simple FAQ)
# ---------------------------

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


from typing import Optional, Dict, Any

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    analysis: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    reply: str


def simple_chatbot_reply(user_text: str, analysis: dict | None = None) -> str:
    t = (user_text or "").lower().strip()

    # --------- Scope filter (only questions about this website/app) ----------
    allowed_keywords = [
        "website", "web", "app", "this site", "this tool", "project",
        "upload", "analyze", "scan", "result", "label", "confidence", "unknown",
        "exif", "metadata", "sharpness", "signals", "reasons",
        "api", "endpoint", "backend", "frontend", "fastapi", "next",
        "cors", "error", "failed to fetch", "401", "429", "rate limit",
        "api key", "deploy", "docker", "vercel", "render", "railway", "fly",
        "privacy", "data", "logs", "audit", "security"
    ]

    in_scope = any(k in t for k in allowed_keywords)
    short_ok = len(t.split()) <= 6 and any(x in t for x in ["this", "it", "here", "web", "app"])

    if not in_scope and not short_ok:
        return (
            "I can only help with questions related to this website "
            "(how to use it, what the results mean, or technical issues). "
            "For questions outside this scope, please contact the website owner."
        )

    # --------- If analysis context exists, answer specifically ----------
    # Expected analysis: { label, confidence, reasons, signals, extra }
    if analysis:
        label = analysis.get("label")
        conf = analysis.get("confidence")
        reasons = analysis.get("reasons") or []
        signals = analysis.get("signals") or {}

        def _fmt_conf(x):
            try:
                return f"{float(x) * 100:.1f}%"
            except Exception:
                return "N/A"

        if any(k in t for k in ["why", "explain", "reason"]):
            if reasons:
                top = reasons[:5]
                bullets = "\n".join([f"- {r}" for r in top])
                return (
                    "Here’s an explanation based on the image you just scanned:\n"
                    f"Result: **{label}** (confidence ≈ {_fmt_conf(conf)}).\n"
                    f"Main reasons:\n{bullets}\n"
                    "For higher certainty, try using the original image file "
                    "(not one downloaded from social media) and compare with a few similar images."
                )
            else:
                return (
                    f"The image was classified as **{label}** (confidence ≈ {_fmt_conf(conf)}), "
                    "but no detailed reasons are available yet. "
                    "Please check the “Why this result” section or enable reasons in the backend."
                )

        if "unknown" in t or "uncertain" in t:
            exif = signals.get("exif") or {}
            score_ai = signals.get("score_ai")
            return (
                "The image was classified as **unknown** because the system is not confident enough.\n"
                f"- EXIF metadata: {'present' if len(exif) else 'missing'} "
                "(social media platforms often remove EXIF)\n"
                f"- Forensics score_ai = {score_ai}\n"
                "Using the original camera file usually improves accuracy."
            )

        if "confidence" in t or "%" in t:
            return (
                f"For this image: **{label}**, confidence ≈ {_fmt_conf(conf)}.\n"
                "Confidence reflects relative certainty, not absolute proof. "
                "It increases when signals are far from the uncertain zone."
            )

        if "exif" in t:
            exif = signals.get("exif") or {}
            software = (exif.get("EXIF Software") or exif.get("Image Software") or "")
            if software:
                return (
                    f"The EXIF metadata shows Software: “{software}”. "
                    "This is an important signal when detecting AI pipelines or image editing."
                )
            return (
                "The scanned image contains little or no EXIF metadata. "
                "Many platforms (e.g., Instagram, Facebook) strip EXIF, "
                "which reduces detection certainty."
            )

        if any(k in t for k in ["how", "use", "usage"]):
            return (
                "Quick usage guide:\n"
                "1) Upload an image\n"
                "2) Click Analyze\n"
                "3) Review the label, confidence, and “Why this result” section\n"
                "If the result is unknown, try an original or less-compressed image."
            )

    # --------- General in-scope fallback ----------
    if "failed to fetch" in t or "cors" in t:
        return (
            "This usually means the frontend cannot reach the backend.\n"
            "Quick checks:\n"
            "1) Make sure the backend is running at http://127.0.0.1:8000\n"
            "2) Open http://127.0.0.1:8000/health to confirm it responds\n"
            "3) If it’s a CORS issue, allow http://localhost:3000 and http://127.0.0.1:3000."
        )

    if "401" in t or "unauthorized" in t or "api key" in t:
        return (
            "401 means the API key is missing or invalid. "
            "The frontend must send the `x-api-key` header, "
            "and the backend must be started with `export APP_API_KEY=...`."
        )

    if "429" in t or "rate limit" in t:
        return (
            "429 indicates you hit the rate limit (too many requests in a short time). "
            "Please wait a bit or adjust the limits in `security.py`."
        )

    return (
        "I can help with using this website, understanding results "
        "(label, confidence, explanations), or troubleshooting. "
        "What would you like to know?"
    )

@app.post("/chat", response_model=ChatResponse)
async def chat(request: Request, req: ChatRequest):
    t0 = time.time()
    ip = request.client.host if request.client else "unknown"

    try:
        require_api_key(request)
        rate_limit(request)

        user_msgs = [m.content for m in req.messages if m.role == "user"]
        last = user_msgs[-1] if user_msgs else ""

        reply = simple_chatbot_reply(last)

        latency_ms = int((time.time() - t0) * 1000)
        audit_chat(
            ip=ip,
            method=request.method,
            path=request.url.path,
            status_code=200,
            latency_ms=latency_ms,
            user_msg_len=len(last) if last else 0,
        )

        return ChatResponse(reply=reply)

    except HTTPException as e:
        # best effort: try to log blocked
        user_msgs = [m.content for m in req.messages if m.role == "user"]
        last = user_msgs[-1] if user_msgs else ""

        latency_ms = int((time.time() - t0) * 1000)
        audit_chat(
            ip=ip,
            method=request.method,
            path=request.url.path,
            status_code=e.status_code,
            latency_ms=latency_ms,
            user_msg_len=len(last) if last else 0,
            blocked_reason=str(e.detail),
        )
        raise

    except Exception:
        user_msgs = [m.content for m in req.messages if m.role == "user"]
        last = user_msgs[-1] if user_msgs else ""

        latency_ms = int((time.time() - t0) * 1000)
        audit_chat(
            ip=ip,
            method=request.method,
            path=request.url.path,
            status_code=500,
            latency_ms=latency_ms,
            user_msg_len=len(last) if last else 0,
            blocked_reason="Internal server error",
        )
        raise HTTPException(status_code=500, detail="Internal server error")
