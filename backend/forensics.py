from __future__ import annotations

import io
from typing import Any, Dict, Tuple

import numpy as np
from PIL import Image, ExifTags

_EXIF_TAGS = {v: k for k, v in ExifTags.TAGS.items()}

def read_exif(image_bytes: bytes) -> Dict[str, Any]:
    try:
        img = Image.open(io.BytesIO(image_bytes))
        exif = img.getexif()
        if not exif:
            return {}
        out: Dict[str, Any] = {}
        for tag_id, value in exif.items():
            name = ExifTags.TAGS.get(tag_id, str(tag_id))
            if isinstance(value, bytes):
                continue
            out[name] = value
        return out
    except Exception:
        return {}

def is_jpeg(image_bytes: bytes) -> bool:
    return image_bytes[:2] == b"\xff\xd8"

def pil_to_np_rgb(img: Image.Image) -> np.ndarray:
    if img.mode != "RGB":
        img = img.convert("RGB")
    arr = np.asarray(img).astype(np.float32) / 255.0
    return arr

def sharpness_score(img: Image.Image) -> float:
    # variance of Laplacian (simple focus metric)
    arr = np.asarray(img.convert("L")).astype(np.float32) / 255.0
    k = np.array([[0, 1, 0],
                  [1, -4, 1],
                  [0, 1, 0]], dtype=np.float32)
    lap = _conv2(arr, k)
    v = float(np.var(lap))
    # normalize to rough 0..1 range
    return max(0.0, min(v * 10.0, 1.0))

def _conv2(im: np.ndarray, k: np.ndarray) -> np.ndarray:
    h, w = im.shape
    kh, kw = k.shape
    pad_h, pad_w = kh // 2, kw // 2
    pim = np.pad(im, ((pad_h, pad_h), (pad_w, pad_w)), mode="reflect")
    out = np.zeros_like(im, dtype=np.float32)
    for y in range(h):
        for x in range(w):
            patch = pim[y:y+kh, x:x+kw]
            out[y, x] = float(np.sum(patch * k))
    return out

def noise_level(img: Image.Image) -> float:
    # estimate noise: high-pass residual energy
    arr = np.asarray(img.convert("L")).astype(np.float32) / 255.0
    blur = _box_blur(arr, r=2)
    resid = arr - blur
    e = float(np.mean(np.abs(resid)))
    # typical photos: small but not zero
    return max(0.0, min(e * 4.0, 1.0))

def _box_blur(im: np.ndarray, r: int = 2) -> np.ndarray:
    h, w = im.shape
    pim = np.pad(im, ((r, r), (r, r)), mode="reflect")
    out = np.zeros_like(im, dtype=np.float32)
    k = (2 * r + 1) ** 2
    for y in range(h):
        for x in range(w):
            patch = pim[y:y+2*r+1, x:x+2*r+1]
            out[y, x] = float(np.sum(patch)) / float(k)
    return out

def saturation_clipping(img: Image.Image) -> float:
    # how many pixels are near 0 or 1 in any channel
    arr = np.asarray(img.convert("RGB")).astype(np.float32) / 255.0
    near0 = (arr < 0.01).any(axis=2).mean()
    near1 = (arr > 0.99).any(axis=2).mean()
    v = float(near0 + near1)
    return max(0.0, min(v, 1.0))

def texture_energy(img: Image.Image) -> float:
    # gradient magnitude mean (proxy for texture/detail)
    arr = np.asarray(img.convert("L")).astype(np.float32) / 255.0
    gx = np.abs(arr[:, 1:] - arr[:, :-1])
    gy = np.abs(arr[1:, :] - arr[:-1, :])
    e = float(gx.mean() + gy.mean())
    return max(0.0, min(e * 6.0, 1.0))

def basic_signals(img: Image.Image, image_bytes: bytes) -> Dict[str, Any]:
    w, h = img.size
    exif = read_exif(image_bytes)
    return {
        "width": w,
        "height": h,
        "jpeg": is_jpeg(image_bytes),
        "exif_present": bool(exif),
        "exif": exif,
        "sharpness": round(sharpness_score(img), 4),
        "noise": round(noise_level(img), 4),
        "texture": round(texture_energy(img), 4),
        "clip": round(saturation_clipping(img), 4),
    }
