from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple
from PIL import Image

# Lazy import to keep boot fast
_PIPE = None

@dataclass
class MLResult:
    prob_ai: float
    model_name: str

def _load_pipeline(model_name: str):
    global _PIPE
    if _PIPE is not None:
        return _PIPE

    from transformers import pipeline

    # CPU ok
    _PIPE = pipeline(
        task="image-classification",
        model=model_name,
        device=-1
    )
    return _PIPE

def predict_prob_ai(img: Image.Image, model_name: str = "Ateeqq/ai-vs-human-image-detector") -> MLResult:
    """
    Returns probability that image is AI-generated (0..1)
    Model outputs labels; we map to AI-vs-real.
    """
    pipe = _load_pipeline(model_name)
    preds = pipe(img)

    # preds: list[{"label": "...", "score": ...}]
    # We try common label patterns.
    prob_ai = None
    for p in preds:
        label = str(p.get("label", "")).lower()
        score = float(p.get("score", 0.0))
        if "ai" in label or "generated" in label or "fake" in label:
            prob_ai = score
            break

    if prob_ai is None:
        # fallback: if labels are "human"/"real"
        for p in preds:
            label = str(p.get("label", "")).lower()
            score = float(p.get("score", 0.0))
            if "human" in label or "real" in label or "photograph" in label:
                prob_ai = 1.0 - score
                break

    if prob_ai is None:
        # last fallback: take top-1 and guess
        top = preds[0] if preds else {"score": 0.5}
        prob_ai = float(top.get("score", 0.5))

    prob_ai = max(0.0, min(prob_ai, 1.0))
    return MLResult(prob_ai=prob_ai, model_name=model_name)
