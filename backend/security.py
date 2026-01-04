import os
import time
from typing import Dict, List, Tuple
from fastapi import HTTPException, Request

# -----------------------
# API KEY
# -----------------------
API_KEY = os.getenv("APP_API_KEY", "")  # set in terminal: export APP_API_KEY="your_key"

def require_api_key(request: Request) -> None:
    # If no key configured, allow (dev mode)
    if not API_KEY:
        return

    provided = request.headers.get("x-api-key", "")
    if not provided or provided != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized: invalid API key")


# -----------------------
# SIMPLE IN-MEMORY RATE LIMIT
# -----------------------
# Limit per IP per endpoint (very simple memory-based limiter)
# Good enough for demo / resume. For production: Redis, etc.
WINDOW_SECONDS = 60
MAX_REQ_PER_WINDOW = 15

_hits: Dict[Tuple[str, str], List[float]] = {}  # (ip, path) -> timestamps


def rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    path = request.url.path
    key = (ip, path)

    now = time.time()
    arr = _hits.get(key, [])

    # keep only timestamps inside window
    arr = [t for t in arr if now - t < WINDOW_SECONDS]

    if len(arr) >= MAX_REQ_PER_WINDOW:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: max {MAX_REQ_PER_WINDOW} req / {WINDOW_SECONDS}s",
        )

    arr.append(now)
    _hits[key] = arr

