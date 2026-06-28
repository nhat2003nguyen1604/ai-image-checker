import os

from ml_features import extract_features_from_bytes, FEATURE_KEYS

MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.joblib")


class Predictor:
    def __init__(self):
        self.pack = None

    def load(self):
        if not os.path.exists(MODEL_PATH):
            self.pack = None
            return
        try:
            import joblib  # lazy import
        except Exception:
            self.pack = None
            return

        self.pack = joblib.load(MODEL_PATH)

    def ready(self) -> bool:
        return self.pack is not None

    def predict(self, img_bytes: bytes):
        if not self.pack:
            raise RuntimeError("Model not loaded")

        feat = extract_features_from_bytes(img_bytes)
        keys = self.pack.get("feature_keys", FEATURE_KEYS)
        X = [[feat.get(k, 0.0) for k in keys]]

        model = self.pack["model"]
        proba = model.predict_proba(X)[0]
        classes = list(model.classes_)

        idx = int(proba.argmax())
        label = classes[idx]
        confidence = float(proba[idx])

        reasons = [
            "ML calibrated prediction using ELA / residual / FFT / image stats features.",
            f"Top class: {label} ({confidence:.3f})",
        ]

        return label, confidence, feat, reasons

