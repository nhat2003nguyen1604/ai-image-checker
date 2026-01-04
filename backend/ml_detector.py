from __future__ import annotations

from typing import Dict, Any, Tuple
import os
import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForImageClassification

# Model that predicts AI-generated vs Real (image classifier)
# HF page: dima806/ai_vs_real_image_detection
MODEL_ID = os.getenv("HF_IMAGE_DETECTOR_MODEL", "dima806/ai_vs_real_image_detection")

_processor = None
_model = None
_device = None


def _get_device() -> torch.device:
    # Prefer Apple Silicon GPU (MPS) if available, else CPU
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def load_model() -> None:
    global _processor, _model, _device
    if _model is not None and _processor is not None:
        return

    _device = _get_device()
    _processor = AutoImageProcessor.from_pretrained(MODEL_ID)
    _model = AutoModelForImageClassification.from_pretrained(MODEL_ID)
    _model.to(_device)
    _model.eval()


@torch.inference_mode()
def predict_ai_probability(img: Image.Image) -> Tuple[float, Dict[str, Any]]:
    """
    Returns:
      p_ai: float in [0,1] (probability the image is AI-generated)
      meta: debug info (top label probs)
    """
    load_model()

    inputs = _processor(images=img, return_tensors="pt")
    inputs = {k: v.to(_device) for k, v in inputs.items()}

    outputs = _model(**inputs)
    logits = outputs.logits[0]
    probs = torch.softmax(logits, dim=-1)

    # Build label -> prob map using model config
    id2label = _model.config.id2label
    label_probs = {id2label[i]: float(probs[i].item()) for i in range(probs.shape[0])}

    # Try to infer which label means "AI"
    # Many models use labels like "Fake/Real" or "AI/Real".
    # We'll treat any label containing these keywords as AI/fake.
    ai_keys = ["fake", "ai", "generated", "deepfake", "synthetic"]

    p_ai = None
    for lbl, p in label_probs.items():
        if any(k in lbl.lower() for k in ai_keys):
            p_ai = p
            break

    # Fallback: if we can't detect label name, assume class 0 is AI-like
    if p_ai is None:
        p_ai = float(probs[0].item())

    # For debugging: top-2
    top = sorted(label_probs.items(), key=lambda x: x[1], reverse=True)[:2]
    meta = {"model_id": MODEL_ID, "device": str(_device), "top2": top}

    return float(p_ai), meta

