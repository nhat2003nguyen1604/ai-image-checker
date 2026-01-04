from typing import Dict, List, Any


def build_reasons(label: str, signals: Dict[str, Any], extra: Dict[str, Any] | None = None) -> List[str]:
    reasons: List[str] = []

    exif = signals.get("exif") or {}
    sharp = float(signals.get("sharpness_score") or 0.0)
    score_ai = float(signals.get("score_ai") or 0.0)

    # 1) EXIF / software hints
    software = (exif.get("EXIF Software") or exif.get("Image Software") or "")
    if software:
        sw = software.lower()
        ai_keywords = ["stable diffusion", "midjourney", "dall-e", "comfyui", "automatic1111", "firefly", "generative"]
        edit_keywords = ["photoshop", "lightroom", "snapseed", "facetune"]

        if any(k in sw for k in ai_keywords):
            reasons.append(f"EXIF Software indicates an AI tool: “{software}”.")
        elif any(k in sw for k in edit_keywords):
            reasons.append(f"EXIF Software indicates editing software: “{software}”.")
        else:
            reasons.append(f"EXIF Software found: “{software}”.")
    else:
        reasons.append("No EXIF software metadata found (social media often removes EXIF).")

    # 2) Texture / sharpness heuristic
    if sharp < 0.08:
        reasons.append(f"Low texture/sharpness score ({sharp:.3f}) can appear in synthetic or heavily processed images.")
    else:
        reasons.append(f"Texture/sharpness score is moderate ({sharp:.3f}).")

    # 3) Heuristic score
    reasons.append(f"Forensics heuristic score_ai = {score_ai:.3f} (0=real-like, 1=AI-like).")

    # 4) ML info (if you’re using 4B)
    if extra:
        p_ml = extra.get("p_ai_ml")
        p_comb = extra.get("p_ai_combined")
        if p_ml is not None:
            reasons.append(f"Local ML model estimated AI probability ≈ {float(p_ml):.3f}.")
        if p_comb is not None:
            reasons.append(f"Combined probability used for final decision ≈ {float(p_comb):.3f}.")

    # 5) Make it label-aware (short final hint)
    if label == "unknown":
        reasons.append("The prediction is near the uncertain zone, so the system avoids a strong claim.")
    elif label == "likely_ai":
        reasons.append("Multiple signals lean toward AI-generation or AI-editing.")
    elif label == "likely_real":
        reasons.append("Signals lean toward a natural camera-origin image.")

    return reasons

