from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional


LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
LOG_FILE = os.path.join(LOG_DIR, "audit.jsonl")


def _ensure_dir() -> None:
    os.makedirs(LOG_DIR, exist_ok=True)


def now_iso() -> str:
    # simple ISO time (local)
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())


def write_audit(event: Dict[str, Any]) -> None:
    """
    Append one JSON object per line (JSONL).
    Never throws (best effort).
    """
    try:
        _ensure_dir()
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        # best-effort logging; do not crash app
        pass


def build_base_event(
    *,
    ip: str,
    method: str,
    path: str,
    status_code: int,
    latency_ms: int,
) -> Dict[str, Any]:
    return {
        "ts": now_iso(),
        "ip": ip,
        "method": method,
        "path": path,
        "status_code": status_code,
        "latency_ms": latency_ms,
    }


def audit_analyze(
    *,
    ip: str,
    method: str,
    path: str,
    status_code: int,
    latency_ms: int,
    filename: Optional[str] = None,
    content_type: Optional[str] = None,
    size_bytes: Optional[int] = None,
    image_type: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    label: Optional[str] = None,
    confidence: Optional[float] = None,
    blocked_reason: Optional[str] = None,
) -> None:
    e = build_base_event(
        ip=ip, method=method, path=path, status_code=status_code, latency_ms=latency_ms
    )
    e["event"] = "analyze"
    e["file"] = {
        "filename": filename,
        "content_type": content_type,
        "size_bytes": size_bytes,
        "image_type": image_type,
        "width": width,
        "height": height,
    }
    e["result"] = {"label": label, "confidence": confidence}
    if blocked_reason:
        e["blocked_reason"] = blocked_reason
    write_audit(e)


def audit_chat(
    *,
    ip: str,
    method: str,
    path: str,
    status_code: int,
    latency_ms: int,
    user_msg_len: Optional[int] = None,
    blocked_reason: Optional[str] = None,
) -> None:
    e = build_base_event(
        ip=ip, method=method, path=path, status_code=status_code, latency_ms=latency_ms
    )
    e["event"] = "chat"
    e["chat"] = {"user_msg_len": user_msg_len}
    if blocked_reason:
        e["blocked_reason"] = blocked_reason
    write_audit(e)

