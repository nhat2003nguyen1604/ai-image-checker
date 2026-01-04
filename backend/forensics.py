import io
from typing import Dict

import exifread
import numpy as np
import cv2
from PIL import Image


def read_exif(raw_bytes: bytes) -> Dict[str, str]:
    """
    Read a few common EXIF fields (if present).
    Many social media platforms strip EXIF, so this may be empty.
    """
    try:
        tags = exifread.process_file(io.BytesIO(raw_bytes), details=False)
        out: Dict[str, str] = {}

        keys = [
            "Image Make",
            "Image Model",
            "EXIF Software",
            "Image Software",
            "EXIF DateTimeOriginal",
        ]
        for k in keys:
            if k in tags:
                out[k] = str(tags[k])
        return out
    except Exception:
        return {}


def is_jpeg(raw_bytes: bytes) -> bool:
    """Quick check: does the file look like a JPEG by magic bytes?"""
    return len(raw_bytes) >= 2 and raw_bytes[0] == 0xFF and raw_bytes[1] == 0xD8


def sharpness_score(pil_img: Image.Image) -> float:
    """
    Rough sharpness/texture estimate using Laplacian variance.
    Returns a normalized score ~ 0..1 (very rough).
    """
    gray = np.array(pil_img.convert("L"))
    v = cv2.Laplacian(gray, cv2.CV_64F).var()

    score = v / 1200.0  # rough normalization constant
    score = max(0.0, min(score, 1.0))
    return float(score)
