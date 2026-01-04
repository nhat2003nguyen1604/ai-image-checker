from typing import Dict, Tuple
import math

from PIL import Image
from ml_detector import predict_ai_probability

LOW = 0.35
HIGH = 0.65


def _smooth_confidence_from_boundary(p_ai: float) -> float:
    """
    Confidence grows only when p_ai is far outside [LOW, HIGH].
    Returns in [0.50, 0.90] to avoid overclaiming with heuristics/models.
    """
    if p_ai >= HIGH:
        conf = 0.5 + 0.40 * ((p_ai - HIGH) / (1.0 - HIGH))
    elif p_ai <= LOW:
        conf = 0.5 + 0.40 * ((LOW - p_ai) / LOW)
    else:
        conf = 0.50
    return max(0.50, min(conf, 0.90))


def predict_label_confidence(signals: Dict, img: Image.Image) -> Tuple[str, float, Dict]:
    """
    Combines:
      - Local ML model probability (p_ai_ml)
      - Forensics heuristic score (score_ai)
    Returns: (label, confidence, extra_debug)
    """
    score_ai = float(signals.get("score_ai", 0.0))
    exif = signals.get("exif", {}) or {}

    # 1) Local ML model
    p_ai_ml, meta = predict_ai_probability(img)

    # 2) Combine ML + forensics (simple weighted average)
    # ML should dominate; forensics helps when EXIF contains strong hints.
    w_ml = 0.75
    w_fx = 0.25
    p_ai = (w_ml * p_ai_ml) + (w_fx * score_ai)

    # 3) Label
    if p_ai >= HIGH:
        label = "likely_ai"
    elif p_ai <= LOW:
        label = "likely_real"
    else:
        label = "unknown"

    # 4) Confidence (boundary-based)
    confidence = _smooth_confidence_from_boundary(p_ai)

    # If EXIF missing, reduce slightly (common social media)
    if len(exif) == 0 and label != "unknown":
        confidence *= 0.95
        confidence = max(0.50, min(confidence, 0.90))

    extra = {
        "p_ai_ml": round(p_ai_ml, 3),
        "p_ai_combined": round(p_ai, 3),
        "combine_weights": {"ml": w_ml, "forensics": w_fx},
        "ml_meta": meta,
    }
    return label, float(confidence), extra
