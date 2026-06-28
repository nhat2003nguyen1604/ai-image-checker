import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional

def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def _now_ts() -> int:
    return int(time.time())

def _read_jsonl(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    items: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                continue
    return items

def _append_jsonl(path: str, obj: Dict[str, Any]) -> None:
    _ensure_dir(os.path.dirname(path))
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def new_scan_id() -> str:
    return uuid.uuid4().hex[:16]

def save_scan(data_dir: str, scan: Dict[str, Any]) -> Dict[str, Any]:
    _ensure_dir(data_dir)
    scan = dict(scan)
    scan.setdefault("scan_id", new_scan_id())
    scan.setdefault("ts", _now_ts())
    _append_jsonl(os.path.join(data_dir, "scans.jsonl"), scan)
    return scan

def save_feedback(data_dir: str, fb: Dict[str, Any]) -> Dict[str, Any]:
    _ensure_dir(data_dir)
    fb = dict(fb)
    fb.setdefault("id", uuid.uuid4().hex[:16])
    fb.setdefault("ts", _now_ts())
    _append_jsonl(os.path.join(data_dir, "feedback.jsonl"), fb)
    return fb

def list_feedback(
    data_dir: str,
    limit: int = 200,
    only_wrong: bool = True,
    q: str = "",
) -> List[Dict[str, Any]]:
    items = _read_jsonl(os.path.join(data_dir, "feedback.jsonl"))
    q = (q or "").strip().lower()

    def match(x: Dict[str, Any]) -> bool:
        if only_wrong and x.get("vote") != "wrong":
            return False
        if q:
            blob = f"{x.get('scan_id','')} {x.get('note','')} {x.get('vote','')}".lower()
            return q in blob
        return True

    items = [x for x in items if match(x)]
    items.sort(key=lambda x: int(x.get("ts", 0)), reverse=True)
    return items[: max(1, min(int(limit), 2000))]

def get_scan_by_id(data_dir: str, scan_id: str):
    path = os.path.join(data_dir, "scans.jsonl")

    if not os.path.exists(path):
        return None

    found = None

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                item = json.loads(line)
            except Exception:
                continue

            # Support both old and new formats
            if item.get("scan_id") == scan_id or item.get("id") == scan_id:
                found = item

    return found

# ===== Feedback review status helpers =====

def _feedback_status_path(data_dir: str) -> str:
    return os.path.join(data_dir, "feedback_status.json")


def _feedback_key(item: dict) -> str:
    """
    Creates a stable key for old and new feedback rows.
    New rows may have id. Old rows may not.
    """
    if item.get("id"):
        return str(item.get("id"))

    scan_id = str(item.get("scan_id", ""))
    ts = str(item.get("ts", ""))
    vote = str(item.get("vote", ""))
    return f"{scan_id}_{ts}_{vote}"


def _load_feedback_statuses(data_dir: str) -> dict:
    path = _feedback_status_path(data_dir)

    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_feedback_statuses(data_dir: str, statuses: dict) -> None:
    _ensure_dir(data_dir)
    path = _feedback_status_path(data_dir)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(statuses, f, ensure_ascii=False, indent=2)


def set_feedback_status(data_dir: str, feedback_key: str, status: str) -> dict:
    allowed = {"new", "reviewed", "fixed"}

    if status not in allowed:
        raise ValueError("Invalid status")

    statuses = _load_feedback_statuses(data_dir)
    statuses[feedback_key] = status
    _save_feedback_statuses(data_dir, statuses)

    return {
        "feedback_key": feedback_key,
        "review_status": status,
    }


# ===== Feedback review status helpers =====

def _feedback_status_path(data_dir: str) -> str:
    return os.path.join(data_dir, "feedback_status.json")


def _feedback_key(item: dict) -> str:
    """
    Creates a stable key for old and new feedback rows.
    New rows may have id. Old rows may not.
    """
    if item.get("id"):
        return str(item.get("id"))

    scan_id = str(item.get("scan_id", ""))
    ts = str(item.get("ts", ""))
    vote = str(item.get("vote", ""))
    return f"{scan_id}_{ts}_{vote}"


def _load_feedback_statuses(data_dir: str) -> dict:
    path = _feedback_status_path(data_dir)

    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_feedback_statuses(data_dir: str, statuses: dict) -> None:
    _ensure_dir(data_dir)
    path = _feedback_status_path(data_dir)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(statuses, f, ensure_ascii=False, indent=2)


def set_feedback_status(data_dir: str, feedback_key: str, status: str) -> dict:
    allowed = {"new", "reviewed", "fixed"}

    if status not in allowed:
        raise ValueError("Invalid status")

    statuses = _load_feedback_statuses(data_dir)
    statuses[feedback_key] = status
    _save_feedback_statuses(data_dir, statuses)

    return {
        "feedback_key": feedback_key,
        "review_status": status,
    }


def list_feedback_with_status(
    data_dir: str,
    limit: int = 200,
    only_wrong: bool = False,
    q: str = "",
) -> list:
    items = list_feedback(data_dir, limit=limit, only_wrong=only_wrong, q=q)
    statuses = _load_feedback_statuses(data_dir)

    enriched = []

    for item in items:
        item = dict(item)
        key = _feedback_key(item)
        item["feedback_key"] = key
        item["review_status"] = statuses.get(key, "new")
        enriched.append(item)

    return enriched

def update_feedback_status(data_dir: str, target: dict, status: str):
    """
    Update feedback status in feedback.jsonl.
    Supports matching by id OR scan_id + ts.
    """
    path = os.path.join(data_dir, "feedback.jsonl")

    if not os.path.exists(path):
        return None

    allowed = {"new", "reviewed", "fixed"}
    if status not in allowed:
        raise ValueError("Invalid status")

    rows = []
    updated = None

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                item = json.loads(line)
            except Exception:
                continue

            match = False

            if target.get("id") and item.get("id") == target.get("id"):
                match = True
            elif target.get("scan_id") and str(item.get("scan_id")) == str(target.get("scan_id")):
                if target.get("ts") is None or str(item.get("ts")) == str(target.get("ts")):
                    match = True

            if match:
                item["status"] = status
                item["reviewed_ts"] = int(time.time())
                updated = item

            rows.append(item)

    with open(path, "w", encoding="utf-8") as f:
        for item in rows:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    return updated