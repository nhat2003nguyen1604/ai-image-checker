import io
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional

from PIL import Image


AI_WORDS = [
    "fake",
    "ai",
    "generated",
    "synthetic",
    "artificial",
    "computer",
]

REAL_WORDS = [
    "real",
    "human",
    "natural",
    "photo",
    "photograph",
    "authentic",
]


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


def _as_dict(result: Any) -> Dict[str, Any]:
    """
    Accepts dict or Pydantic-like objects.
    """
    if isinstance(result, dict):
        return dict(result)

    if hasattr(result, "model_dump"):
        return result.model_dump()

    if hasattr(result, "dict"):
        return result.dict()

    return {
        "label": "unknown",
        "confidence": 0.5,
        "reasons": ["Base detector result could not be parsed."],
        "signals": {},
        "extra": {},
    }


def _normalize_model_label(label: str) -> str:
    text = str(label or "").lower()

    if any(word in text for word in AI_WORDS):
        return "ai"

    if any(word in text for word in REAL_WORDS):
        return "real"

    return "unknown"


def _base_ai_score(base: Dict[str, Any]) -> float:
    """
    Converts the existing detector output into an AI probability.
    likely_ai  + confidence 0.8 => 0.8 AI score
    likely_real + confidence 0.8 => 0.2 AI score
    unknown => 0.5
    """
    label = str(base.get("label", "unknown")).lower()

    try:
        confidence = float(base.get("confidence", 0.5))
    except Exception:
        confidence = 0.5

    confidence = max(0.0, min(1.0, confidence))

    if "ai" in label or "fake" in label or "synthetic" in label:
        return confidence

    if "real" in label or "human" in label:
        return 1.0 - confidence

    return 0.5


def _final_label_from_ai_score(ai_score: float) -> str:
    if ai_score >= 0.65:
        return "likely_ai"

    if ai_score <= 0.35:
        return "likely_real"

    return "unknown"


def _final_confidence(ai_score: float, label: str) -> float:
    if label == "likely_ai":
        return round(ai_score, 4)

    if label == "likely_real":
        return round(1.0 - ai_score, 4)

    return 0.5


def _open_image_from_bytes(image_bytes: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(image_bytes))
    return image.convert("RGB")


@lru_cache(maxsize=1)
def _get_pipeline():
    """
    Lazy-loads the Hugging Face model once.
    If loading fails, returns the exception object so app can fallback safely.
    """
    enabled = _env_bool("ENABLE_MODEL_DETECTOR", default=True)

    if not enabled:
        return None

    model_name = os.getenv("HF_MODEL_NAME", "capcheck/ai-image-detection")

    try:
        from transformers import pipeline

        # CPU mode is safest for Mac/Windows/Linux local development.
        # It may be slower, but avoids device-specific errors.
        return pipeline("image-classification", model=model_name)
    except Exception as e:
        return e


def run_model_detector(image_bytes: bytes) -> Dict[str, Any]:
    """
    Runs the pretrained model and returns normalized AI score.
    """
    pipe = _get_pipeline()

    if pipe is None:
        return {
            "enabled": False,
            "ok": False,
            "error": "Model detector is disabled.",
            "ai_score": None,
            "raw": [],
        }

    if isinstance(pipe, Exception):
        return {
            "enabled": True,
            "ok": False,
            "error": str(pipe),
            "ai_score": None,
            "raw": [],
        }

    try:
        image = _open_image_from_bytes(image_bytes)

        try:
            raw = pipe(image, top_k=5)
        except TypeError:
            raw = pipe(image)

        if isinstance(raw, dict):
            outputs: List[Dict[str, Any]] = [raw]
        else:
            outputs = list(raw)

        ai_score: Optional[float] = None
        real_score: Optional[float] = None

        for item in outputs:
            label = str(item.get("label", ""))
            score = float(item.get("score", 0.0))
            kind = _normalize_model_label(label)

            if kind == "ai":
                ai_score = max(ai_score or 0.0, score)

            if kind == "real":
                real_score = max(real_score or 0.0, score)

        if ai_score is None and real_score is not None:
            ai_score = 1.0 - real_score

        if ai_score is None:
            ai_score = 0.5

        ai_score = max(0.0, min(1.0, float(ai_score)))

        model_label = _final_label_from_ai_score(ai_score)

        return {
            "enabled": True,
            "ok": True,
            "model_name": os.getenv("HF_MODEL_NAME", "capcheck/ai-image-detection"),
            "ai_score": round(ai_score, 4),
            "model_label": model_label,
            "model_confidence": _final_confidence(ai_score, model_label),
            "raw": outputs,
        }

    except Exception as e:
        return {
            "enabled": True,
            "ok": False,
            "error": str(e),
            "ai_score": None,
            "raw": [],
        }


def apply_hybrid_model(base_result: Any, image_bytes: bytes) -> Dict[str, Any]:
    """
    Combines existing detector result with pretrained model result.
    Safe fallback: if model fails, returns base detector result with a warning.
    """
    base = _as_dict(base_result)

    reasons = list(base.get("reasons") or [])
    signals = dict(base.get("signals") or {})
    extra = dict(base.get("extra") or {})

    model_result = run_model_detector(image_bytes)

    extra["model_detector"] = model_result

    if not model_result.get("ok"):
        reasons.append(
            "Pretrained model detector was unavailable, so the result used the original forensic/metadata detector."
        )
        signals["hybrid_detector"] = {
            "used_model": False,
            "error": model_result.get("error"),
        }

        base["reasons"] = reasons
        base["signals"] = signals
        base["extra"] = extra
        return base

    base_score = _base_ai_score(base)
    model_score = float(model_result.get("ai_score", 0.5))

    model_weight = _env_float("MODEL_DETECTOR_WEIGHT", 0.65)
    model_weight = max(0.0, min(1.0, model_weight))
    base_weight = 1.0 - model_weight

    hybrid_ai_score = (model_score * model_weight) + (base_score * base_weight)
    hybrid_ai_score = max(0.0, min(1.0, hybrid_ai_score))

    final_label = _final_label_from_ai_score(hybrid_ai_score)
    final_confidence = _final_confidence(hybrid_ai_score, final_label)

    reasons.append(
        f"Pretrained vision model estimated AI probability at {round(model_score * 100, 1)}%."
    )
    reasons.append(
        "Hybrid result combines the pretrained model with forensic and metadata signals."
    )

    if final_label == "unknown":
        reasons.append(
            "The final result is Unknown because the model and forensic signals are not strong enough for a confident label."
        )

    signals["model_detector"] = {
        "model_name": model_result.get("model_name"),
        "ai_score": model_result.get("ai_score"),
        "model_label": model_result.get("model_label"),
        "model_confidence": model_result.get("model_confidence"),
    }

    signals["hybrid_detector"] = {
        "used_model": True,
        "model_weight": model_weight,
        "base_weight": round(base_weight, 4),
        "base_ai_score": round(base_score, 4),
        "model_ai_score": round(model_score, 4),
        "hybrid_ai_score": round(hybrid_ai_score, 4),
    }

    base["label"] = final_label
    base["confidence"] = final_confidence
    base["reasons"] = reasons
    base["signals"] = signals
    base["extra"] = extra

    return base
