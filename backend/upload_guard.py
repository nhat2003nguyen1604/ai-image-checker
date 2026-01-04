from __future__ import annotations

from typing import Tuple
from fastapi import HTTPException
from PIL import Image, ImageFile
import io

# Avoid issues with truncated images (optional: you can set False to be strict)
ImageFile.LOAD_TRUNCATED_IMAGES = False

# Hard limits (tune as you like)
MAX_MB = 10
MAX_PIXELS = 12_000_000  # 12 megapixels (e.g., 4000x3000)


def _is_jpeg(b: bytes) -> bool:
    return len(b) >= 3 and b[0:3] == b"\xFF\xD8\xFF"


def _is_png(b: bytes) -> bool:
    return len(b) >= 8 and b[0:8] == b"\x89PNG\r\n\x1a\n"


def _is_webp(b: bytes) -> bool:
    # WEBP is RIFF container: "RIFF....WEBP"
    return len(b) >= 12 and b[0:4] == b"RIFF" and b[8:12] == b"WEBP"


def sniff_image_type(content: bytes) -> str:
    """
    Returns 'jpeg' | 'png' | 'webp' or raises 400.
    """
    if _is_jpeg(content):
        return "jpeg"
    if _is_png(content):
        return "png"
    if _is_webp(content):
        return "webp"
    raise HTTPException(status_code=400, detail="Unsupported image type (only JPEG/PNG/WebP)")


def enforce_size_limit(content: bytes, max_mb: int = MAX_MB) -> None:
    if len(content) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File too large (max {max_mb}MB)")


def safe_decode_image(content: bytes) -> Tuple[Image.Image, str]:
    """
    Validates bytes -> real image, verifies header consistency, enforces pixel limit.
    Returns: (PIL Image RGB, image_type)
    """
    enforce_size_limit(content, MAX_MB)
    img_type = sniff_image_type(content)

    # Pillow decompression bomb protection: also enforce our own pixel limit
    # (Pillow has Image.MAX_IMAGE_PIXELS but it raises warnings/errors inconsistently across versions)
    try:
        bio = io.BytesIO(content)

        # Step 1: verify file integrity (doesn't decode full image)
        im = Image.open(bio)
        im.verify()

        # Step 2: reopen and decode (verify() leaves file in unusable state)
        bio2 = io.BytesIO(content)
        im2 = Image.open(bio2)

        w, h = im2.size
        if w <= 0 or h <= 0:
            raise HTTPException(status_code=400, detail="Invalid image dimensions")

        if (w * h) > MAX_PIXELS:
            raise HTTPException(
                status_code=400,
                detail=f"Image too large ({w}x{h}). Max pixels = {MAX_PIXELS:,}.",
            )

        # Decode into a consistent format
        im2 = im2.convert("RGB")
        return im2, img_type

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or corrupted image file")

