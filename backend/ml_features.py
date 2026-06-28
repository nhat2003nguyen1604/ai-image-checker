import io
import numpy as np
import cv2
from PIL import Image, ImageChops, ImageEnhance


FEATURE_KEYS = [
    "ela_mean", "ela_std", "ela_hot_ratio",
    "residual_energy", "residual_kurtosis",
    "fft_high_mid_ratio",
    "lap_var", "entropy",
]


def _pil_from_bytes(b: bytes) -> Image.Image:
    return Image.open(io.BytesIO(b)).convert("RGB")


def _pil_to_cv(img: Image.Image) -> np.ndarray:
    arr = np.array(img.convert("RGB"))
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def ela_features(img_bytes: bytes, quality: int = 90):
    try:
        im = _pil_from_bytes(img_bytes)
    except Exception:
        return None

    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=quality)
    recompressed = _pil_from_bytes(buf.getvalue())

    diff = ImageChops.difference(im, recompressed)
    diff = ImageEnhance.Contrast(diff).enhance(10)

    diff_np = np.array(diff).astype(np.float32) / 255.0
    intensity = diff_np.mean(axis=2)

    return {
        "ela_mean": float(intensity.mean()),
        "ela_std": float(intensity.std()),
        "ela_hot_ratio": float((intensity > 0.25).mean()),
    }


def residual_features(img: Image.Image):
    cv = _pil_to_cv(img)
    gray = cv2.cvtColor(cv, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0

    kernel = np.array(
        [[-1, -1, -1],
         [-1,  8, -1],
         [-1, -1, -1]],
        dtype=np.float32
    )
    hp = cv2.filter2D(gray, -1, kernel)

    energy = float(np.mean(np.abs(hp)))
    x2 = float(np.mean(hp ** 2) + 1e-8)
    x4 = float(np.mean(hp ** 4))
    kurt = float(x4 / (x2 ** 2))

    return {"residual_energy": energy, "residual_kurtosis": kurt}


def fft_features(img: Image.Image):
    cv = _pil_to_cv(img)
    gray = cv2.cvtColor(cv, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0

    f = np.fft.fft2(gray)
    fshift = np.fft.fftshift(f)
    mag = np.log(np.abs(fshift) + 1e-8)

    h, w = mag.shape
    cy, cx = h // 2, w // 2
    y, x = np.ogrid[:h, :w]
    r = np.sqrt((y - cy) ** 2 + (x - cx) ** 2)
    r = r / (r.max() + 1e-8)

    mid = float(np.mean(mag[(r > 0.15) & (r <= 0.45)])) if np.any((r > 0.15) & (r <= 0.45)) else 0.0
    high = float(np.mean(mag[r > 0.45])) if np.any(r > 0.45) else 0.0
    ratio = float(high / (mid + 1e-8))

    return {"fft_high_mid_ratio": ratio}


def basic_image_stats(img: Image.Image):
    cv = _pil_to_cv(img)
    gray = cv2.cvtColor(cv, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0

    lap = cv2.Laplacian(gray, cv2.CV_32F)
    lap_var = float(lap.var())

    hist = cv2.calcHist([np.uint8(gray * 255)], [0], None, [256], [0, 256]).flatten()
    p = hist / (hist.sum() + 1e-8)
    entropy = float(-np.sum(p * np.log2(p + 1e-12)))

    return {"lap_var": lap_var, "entropy": entropy}


def extract_features_from_bytes(img_bytes: bytes) -> dict:
    img = _pil_from_bytes(img_bytes)

    feat = {}
    ela = ela_features(img_bytes)
    if ela:
        feat.update(ela)

    feat.update(residual_features(img))
    feat.update(fft_features(img))
    feat.update(basic_image_stats(img))

    for k in FEATURE_KEYS:
        feat.setdefault(k, 0.0)

    return feat
