from __future__ import annotations

from model_detector import apply_hybrid_model

import io
import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image

from typing import Any, Dict
from fastapi import Request

from forensics import basic_signals
from detector import predict
from storage import save_scan, save_feedback, list_feedback, list_feedback_with_status, set_feedback_status, get_scan_by_id

def load_dotenv_simple(path: str) -> None:
    # Loads KEY=VALUE lines into os.environ if not already set.
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, v = s.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        return

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv_simple(os.path.join(BASE_DIR, ".env"))

DATA_DIR = os.getenv("DATA_DIR", os.path.join(BASE_DIR, "data"))
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
API_KEY = os.getenv("API_KEY", "")
MAX_MB = int(os.getenv("MAX_MB", "10"))

app = FastAPI(title="ai-image-checker-backend", version="1.0.0")

# dev CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def require_api_key(request: Request) -> None:
    if not API_KEY:
        return
    got = request.headers.get("x-api-key", "")
    if got != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/analyze")
async def analyze(request: Request, file: UploadFile = File(...)):
    require_api_key(request)

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    content = await file.read()

    if len(content) > MAX_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File too large (max {MAX_MB}MB)")

    try:
        img = Image.open(io.BytesIO(content)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image file")

    # 1) Old detector: metadata/forensics/rules
    signals = basic_signals(img, content)
    label, confidence, reasons, extra = predict(img, signals)

    # 2) Create base result object
    result = {
        "filename": file.filename,
        "label": label,
        "confidence": round(float(confidence), 4),
        "reasons": reasons,
        "signals": signals,
        "extra": extra,
    }

    # 3) New hybrid detector:
    #    combines old detector + pretrained model detector
    result = apply_hybrid_model(result, image_bytes=content)

    # 4) Save final hybrid result
    scan_obj = save_scan(DATA_DIR, result)

    # 5) Return final hybrid result to frontend
    return {
        "scan_id": scan_obj["scan_id"],
        "label": result.get("label", "unknown"),
        "confidence": round(float(result.get("confidence", 0.5)), 4),
        "reasons": result.get("reasons", []),
        "signals": result.get("signals", {}),
        "extra": result.get("extra", {}),
    }

@app.post("/feedback")
async def feedback(request: Request, payload: Dict[str, Any]):
    require_api_key(request)

    scan_id = str(payload.get("scan_id") or "").strip()
    vote = str(payload.get("vote") or "").strip().lower()
    note = str(payload.get("note") or "").strip()

    if not scan_id:
        raise HTTPException(status_code=400, detail="scan_id is required")
    if vote not in ("correct", "wrong"):
        raise HTTPException(status_code=400, detail="vote must be 'correct' or 'wrong'")

    fb = save_feedback(DATA_DIR, {
        "scan_id": scan_id,
        "vote": vote,
        "note": note,
    })
    return {"ok": True, "id": fb["id"]}

@app.post("/chat")
async def chat(request: Request, payload: Dict[str, Any]):
    require_api_key(request)

    msg = str(payload.get("message") or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="message is required")

    # Simple helpful chatbot (no external LLM).
    # Only answers about this website / troubleshooting.
    text = msg.lower()

    if any(k in text for k in ["scan", "analyze", "upload"]):
        reply = (
            "To scan an image: click Upload, choose a JPG/PNG/WebP under 10MB, then click Analyze. "
            "You will get label, confidence, and reasons."
        )
    elif any(k in text for k in ["unknown", "confidence", "percent", "reasons"]):
        reply = (
            "Unknown means the detector did not see strong signals. Confidence is conservative (capped). "
            "Reasons list explains which signals were used (EXIF, noise/texture, sharpness)."
        )
    elif any(k in text for k in ["wrong", "feedback"]):
        reply = (
            "If the result is wrong, click Wrong, write a short note (why), then Submit. "
            "Admin will review your note to improve the detector."
        )
    elif any(k in text for k in ["error", "cors", "failed", "500", "network"]):
        reply = (
            "If you see errors: make sure backend is running on port 8000 and frontend on 3000. "
            "Also confirm NEXT_PUBLIC_BACKEND_URL is http://127.0.0.1:8000. "
            "Restart both dev servers after changing .env files."
        )
    else:
        reply = (
            "I can help with questions about this website (scan, results, feedback, troubleshooting). "
            "For other questions, please contact the site owner."
        )

    return {"reply": reply}

@app.get("/admin/feedback")
def admin_feedback(limit: int = 200, only_wrong: int = 0, q: str = "", request: Request = None):
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="ADMIN_TOKEN is not set on server.")

    got = request.headers.get("x-admin-token", "") if request else ""

    if got != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

    items = list_feedback_with_status(DATA_DIR, limit=limit, only_wrong=bool(only_wrong), q=q)
    return {"items": items}

@app.post("/admin/feedback/status")
async def admin_feedback_status(payload: Dict[str, Any], request: Request):
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="ADMIN_TOKEN is not set on server.")

    got = request.headers.get("x-admin-token", "")
    if got != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

    status = str(payload.get("status") or "").strip().lower()

    target = {
        "id": payload.get("id"),
        "scan_id": payload.get("scan_id"),
        "ts": payload.get("ts"),
    }

    try:
        updated = update_feedback_status(DATA_DIR, target, status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status")

    if not updated:
        raise HTTPException(status_code=404, detail="Feedback not found")

    return {
        "ok": True,
        "item": updated,
    }

@app.get("/scan/{scan_id}")
def get_scan(scan_id: str):
    item = get_scan_by_id(DATA_DIR, scan_id)

    if not item:
        raise HTTPException(status_code=404, detail="Scan report not found")

    return item
