from __future__ import annotations

import os
import json
import time
from typing import Dict, Any, List, Tuple

from PIL import Image

# Reuse your existing pipeline pieces
from upload_guard import safe_decode_image
from forensics import read_exif, is_jpeg, sharpness_score
from model import predict_label_confidence
from explain import build_reasons


SUPPORTED_EXT = (".jpg", ".jpeg", ".png", ".webp")


def iter_images(folder: str) -> List[str]:
    paths: List[str] = []
    for root, _, files in os.walk(folder):
        for fn in files:
            if fn.lower().endswith(SUPPORTED_EXT):
                paths.append(os.path.join(root, fn))
    paths.sort()
    return paths


def compute_signals_and_predict(path: str) -> Dict[str, Any]:
    with open(path, "rb") as f:
        content = f.read()

    # Hardened decode + type
    img, img_type = safe_decode_image(content)
    w, h = img.size

    # Forensics
    exif = read_exif(content)
    jpeg = is_jpeg(content)
    sharp = sharpness_score(img)

    # baseline heuristic score_ai (same logic as main.py)
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

    # Your model decision (4B): returns (label, confidence, extra)
    label, confidence, extra = predict_label_confidence(signals, img)
    reasons = build_reasons(label, signals, extra)

    return {
        "path": path,
        "label": label,
        "confidence": float(confidence),
        "signals": signals,
        "extra": extra,
        "reasons": reasons,
    }


def map_to_binary(label: str) -> str:
    """
    Map your app outputs into binary classes for evaluation:
    - positive = AI-like
    - negative = real-like
    - unknown = abstain
    """
    if label == "likely_ai":
        return "ai"
    if label == "likely_real":
        return "real"
    return "unknown"


def confusion_counts(items: List[Dict[str, Any]]) -> Dict[str, int]:
    # binary confusion with "unknown" tracked separately
    # TP: predicted ai, gt ai
    # TN: predicted real, gt real
    # FP: predicted ai, gt real
    # FN: predicted real, gt ai
    # U: unknown predictions
    c = {"tp": 0, "tn": 0, "fp": 0, "fn": 0, "unknown": 0, "total": 0}
    for it in items:
        gt = it["gt"]          # "ai" or "real"
        pred = it["pred_bin"]  # "ai" or "real" or "unknown"
        c["total"] += 1
        if pred == "unknown":
            c["unknown"] += 1
            continue
        if pred == "ai" and gt == "ai":
            c["tp"] += 1
        elif pred == "real" and gt == "real":
            c["tn"] += 1
        elif pred == "ai" and gt == "real":
            c["fp"] += 1
        elif pred == "real" and gt == "ai":
            c["fn"] += 1
    return c


def safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def metrics_from_counts(c: Dict[str, int]) -> Dict[str, float]:
    tp, tn, fp, fn, unk, total = c["tp"], c["tn"], c["fp"], c["fn"], c["unknown"], c["total"]
    decided = total - unk

    accuracy = safe_div(tp + tn, decided)  # accuracy over decided samples
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    f1 = safe_div(2 * precision * recall, (precision + recall))
    abstain_rate = safe_div(unk, total)

    return {
        "decided_samples": decided,
        "total_samples": total,
        "abstain_rate": round(abstain_rate, 4),
        "accuracy_decided": round(accuracy, 4),
        "precision_ai": round(precision, 4),
        "recall_ai": round(recall, 4),
        "f1_ai": round(f1, 4),
    }


def print_confusion(c: Dict[str, int]) -> None:
    print("\nConfusion Matrix (binary, excluding unknown from accuracy)")
    print("GT\\Pred     AI        REAL      UNKNOWN")
    print(f"AI       {c['tp']:>6}    {c['fn']:>6}    (counted in unknown separately)")
    print(f"REAL     {c['fp']:>6}    {c['tn']:>6}    (counted in unknown separately)")
    print(f"UNKNOWN (total) = {c['unknown']}")


def main():
    # Expect folders relative to project root
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    data_root = os.path.join(project_root, "eval_data")

    real_dir = os.path.join(data_root, "real")
    ai_dir = os.path.join(data_root, "ai")
    edited_dir = os.path.join(data_root, "edited")

    if not (os.path.isdir(real_dir) and os.path.isdir(ai_dir) and os.path.isdir(edited_dir)):
        print("Missing eval_data folders. Create:")
        print("  eval_data/real, eval_data/ai, eval_data/edited")
        return

    real_imgs = iter_images(real_dir)
    ai_imgs = iter_images(ai_dir)
    edited_imgs = iter_images(edited_dir)

    print("Found images:")
    print(f"  real:   {len(real_imgs)}")
    print(f"  ai:     {len(ai_imgs)}")
    print(f"  edited: {len(edited_imgs)}")

    # We evaluate as binary AI vs REAL:
    # - ai folder => gt=ai
    # - real folder => gt=real
    # - edited folder => gt=ai (treat edits as "not purely real") for stricter behavior
    #   If you prefer edited to be separate class, we can change later.
    tasks: List[Tuple[str, str]] = []
    tasks += [(p, "real") for p in real_imgs]
    tasks += [(p, "ai") for p in ai_imgs]
    tasks += [(p, "ai") for p in edited_imgs]

    results: List[Dict[str, Any]] = []
    t_start = time.time()

    for i, (path, gt) in enumerate(tasks, start=1):
        try:
            out = compute_signals_and_predict(path)
            pred_bin = map_to_binary(out["label"])
            results.append({
                "path": os.path.relpath(path, project_root),
                "gt": gt,
                "pred_label": out["label"],
                "pred_bin": pred_bin,
                "confidence": round(out["confidence"], 4),
                "signals": out["signals"],
                "extra": out.get("extra"),
                "reasons": out.get("reasons", [])[:5],
            })
        except Exception as e:
            results.append({
                "path": os.path.relpath(path, project_root),
                "gt": gt,
                "pred_label": "error",
                "pred_bin": "unknown",
                "confidence": 0.0,
                "error": str(e),
            })

        if i % 20 == 0:
            print(f"Processed {i}/{len(tasks)}...")

    elapsed = time.time() - t_start
    print(f"\nDone. Time: {elapsed:.2f}s for {len(tasks)} images")

    # Compute summary metrics
    eval_items = [r for r in results if r.get("pred_label") != "error"]
    c = confusion_counts([{"gt": r["gt"], "pred_bin": r["pred_bin"]} for r in eval_items])
    m = metrics_from_counts(c)

    # Print summary
    print("\nSummary Metrics:")
    for k, v in m.items():
        print(f"  {k}: {v}")

    print_confusion(c)

    # Save report
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
        "counts": {
            "real": len(real_imgs),
            "ai": len(ai_imgs),
            "edited": len(edited_imgs),
            "total": len(tasks),
        },
        "confusion": c,
        "metrics": m,
        "notes": {
            "binary_definition": "ai vs real (unknown = abstain)",
            "edited_handling": "edited images treated as gt=ai (stricter)",
        },
        "samples": results,
    }

    out_path = os.path.join(project_root, "eval_report.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\nSaved report to: {out_path}")


if __name__ == "__main__":
    main()

