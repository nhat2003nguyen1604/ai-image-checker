from __future__ import annotations

from typing import Any, Dict, List, Tuple
from PIL import Image

AI_KEYWORDS = [
    "stable diffusion",
    "midjourney",
    "dall-e",
    "comfyui",
    "automatic1111",
    "firefly",
    "generative",
]
EDIT_KEYWORDS = [
    "photoshop",
    "lightroom",
    "snapseed",
    "facetune",
    "pixlr",
]

def _safe_lower(x: Any) -> str:
    try:
        return str(x).lower()
    except Exception:
        return ""

def predict(img: Image.Image, signals: Dict[str, Any]) -> Tuple[str, float, List[str], Dict[str, Any]]:
    """
    Returns: (label, confidence 0..1, reasons[], extra{})
    Conservative: prefers 'unknown' unless strong signals.
    """
    reasons: List[str] = []
    score_ai = 0.0  # 0..1

    exif = signals.get("exif") or {}
    software = (
        _safe_lower(exif.get("Software"))
        or _safe_lower(exif.get("ProcessingSoftware"))
        or _safe_lower(exif.get("ImageDescription"))
    )

    # 1) EXIF software strong signal
    if software:
        if any(k in software for k in AI_KEYWORDS):
            score_ai += 0.70
            reasons.append(f"EXIF Software mentions an AI tool: '{software[:80]}'")
        elif any(k in software for k in EDIT_KEYWORDS):
            score_ai += 0.20
            reasons.append(f"EXIF Software suggests photo editing: '{software[:80]}'")
        else:
            reasons.append("EXIF Software present but not clearly AI-related.")
    else:
        reasons.append("No useful EXIF Software tag found (many platforms strip metadata).")

    # 2) Texture / noise / sharpness heuristics (very imperfect, so small weights)
    sharp = float(signals.get("sharpness", 0.0))
    noise = float(signals.get("noise", 0.0))
    texture = float(signals.get("texture", 0.0))
    clip = float(signals.get("clip", 0.0))

    # AI images often appear "too clean": low noise + low texture
    clean = (noise < 0.10) and (texture < 0.12)
    if clean:
        score_ai += 0.18
        reasons.append("Image looks unusually clean: low noise and low texture.")
    else:
        reasons.append("Noise/texture look normal or mixed (not a strong AI signal).")

    # Over-smoothing (low sharpness) can happen in AI or in heavy compression
    if sharp < 0.08:
        score_ai += 0.08
        reasons.append("Low sharpness could indicate smoothing (AI or heavy compression).")

    # clipping can be from aggressive edits or synthetic rendering
    if clip > 0.25:
        score_ai += 0.06
        reasons.append("High clipping (many pixels near pure black/white) may indicate synthetic render or heavy edits.")

    # 3) EXIF missing reduces confidence
    exif_present = bool(signals.get("exif_present", False))
    if not exif_present:
        score_ai -= 0.08
        reasons.append("Metadata missing reduces confidence (common on social media).")

    # clamp score
    score_ai = max(0.0, min(score_ai, 1.0))

    # 4) Conservative decision thresholds
    LOW = 0.30
    HIGH = 0.72  # require strong signals to call AI

    if score_ai >= HIGH:
        label = "likely_ai"
        # confidence grows from 0.55..0.88
        confidence = 0.55 + 0.33 * ((score_ai - HIGH) / (1.0 - HIGH))
    elif score_ai <= LOW:
        label = "likely_real"
        # confidence grows from 0.55..0.85
        confidence = 0.55 + 0.30 * ((LOW - score_ai) / LOW)
    else:
        label = "unknown"
        confidence = 0.50

    # extra conservative caps (avoid 99% claims)
    confidence = max(0.50, min(confidence, 0.90))

    extra = {
        "score_ai": round(score_ai, 4),
        "thresholds": {"low": LOW, "high": HIGH},
        "software": software[:120] if software else "",
    }

    # Ensure reasons non-empty
    if not reasons:
        reasons = ["Insufficient signals to decide confidently."]

    return label, float(confidence), reasons, extra
