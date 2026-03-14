import os
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.preprocessing import StandardScaler

RISK_MAP     = {"low": 0, "medium": 1, "high": 2, "critical": 3}
RISK_REVERSE = {0: "low", 1: "medium", 2: "high", 3: "critical"}
MODEL_PATH   = os.path.join(os.path.dirname(__file__), "saved_model.joblib")

FEATURE_NAMES = [
    "demand", "supply", "temperature", "deficit",
    "load_ratio", "protected_count", "total_zones",
    "non_protected_demand", "heatwave_active"
]


def extract_features(grid_data: dict) -> list:
    zones  = grid_data["zones"]
    demand = grid_data["demand"]
    supply = grid_data["supply"]
    temp   = grid_data["temperature"]

    return [
        demand,
        supply,
        temp,
        demand - supply,
        demand / supply if supply > 0 else 999.0,
        len([z for z in zones if z.get("protected", False)]),
        len(zones),
        sum(z["demand"] for z in zones if not z.get("protected", False)),
        1 if temp > 40 else 0
    ]


class GridMLModel:
    def __init__(self):
        self.classifier      = RandomForestClassifier(n_estimators=100, random_state=42)
        self.anomaly_detector = IsolationForest(contamination=0.1, random_state=42)
        self.scaler          = StandardScaler()
        self.history_X: list = []
        self.history_y: list = []
        self.is_trained      = False

        if os.path.exists(MODEL_PATH):
            self._load()
        else:
            print("[ML] No saved model found — bootstrapping with synthetic data...")
            self._bootstrap()

    # ── Bootstrap ────────────────────────────────────────────────────────────

    def _bootstrap(self):
        """Seed with realistic synthetic data so model is useful from day 1."""
        np.random.seed(42)
        X, y = [], []

        # Low risk — supply comfortably meets demand
        for _ in range(60):
            d = np.random.uniform(200, 400)
            s = np.random.uniform(d * 1.1, d * 1.4)
            t = np.random.uniform(15, 34)
            X.append([d, s, t, d - s, d / s, 1, 3, 150, 0])
            y.append(0)

        # Medium risk — supply tight, no heatwave
        for _ in range(45):
            d = np.random.uniform(380, 490)
            s = np.random.uniform(d * 0.93, d * 1.05)
            t = np.random.uniform(33, 40)
            X.append([d, s, t, d - s, d / s, 1, 4, 250, 0])
            y.append(1)

        # High risk — demand exceeds supply, heatwave
        for _ in range(35):
            d = np.random.uniform(470, 560)
            s = np.random.uniform(d * 0.82, d * 0.96)
            t = np.random.uniform(40, 45)
            X.append([d, s, t, d - s, d / s, 2, 5, 350, 1])
            y.append(2)

        # Critical — severe overload + extreme heat + cascading conditions
        for _ in range(25):
            d = np.random.uniform(530, 650)
            s = np.random.uniform(d * 0.68, d * 0.84)
            t = np.random.uniform(44, 52)
            X.append([d, s, t, d - s, d / s, 2, 6, 430, 1])
            y.append(3)

        self.history_X = X
        self.history_y = y
        self._train()
        print(f"[ML] Bootstrapped on {len(y)} synthetic samples")

    # ── Training ─────────────────────────────────────────────────────────────

    def _train(self):
        X        = np.array(self.history_X)
        y        = np.array(self.history_y)
        X_scaled = self.scaler.fit_transform(X)
        self.classifier.fit(X_scaled, y)
        self.anomaly_detector.fit(X_scaled)
        self.is_trained = True
        self._save()

    # ── Prediction ────────────────────────────────────────────────────────────

    def predict(self, grid_data: dict) -> dict:
        features = extract_features(grid_data)
        X        = np.array([features])
        X_scaled = self.scaler.transform(X)

        risk_idx    = int(self.classifier.predict(X_scaled)[0])
        risk_proba  = self.classifier.predict_proba(X_scaled)[0]
        anom_score  = float(self.anomaly_detector.score_samples(X_scaled)[0])
        is_anomaly  = bool(self.anomaly_detector.predict(X_scaled)[0] == -1)

        # Safety: clamp risk_idx to valid range
        risk_idx = max(0, min(3, risk_idx))

        # Top contributing features for explainability
        importances  = self.classifier.feature_importances_
        top_features = sorted(
            zip(FEATURE_NAMES, importances), key=lambda x: -x[1]
        )[:3]

        # Full probability map — pad to 4 classes if model hasn't seen all yet
        proba_map = {RISK_REVERSE[i]: 0.0 for i in range(4)}
        for i, cls in enumerate(self.classifier.classes_):
            cls_int = max(0, min(3, int(cls)))  # Safety clamp
            proba_map[RISK_REVERSE[cls_int]] = round(float(risk_proba[i]), 3)

        return {
            "ml_risk_level":    RISK_REVERSE[risk_idx],
            "ml_confidence":    round(float(max(risk_proba)), 3),
            "ml_probabilities": proba_map,
            "anomaly_detected": is_anomaly,
            "anomaly_score":    round(anom_score, 4),
            "top_risk_features": [f[0] for f in top_features],
            "training_samples": len(self.history_y),
            "patterns_learned": len(self.history_y) >= 50
        }

    # ── Online Learning ───────────────────────────────────────────────────────

    def update(self, grid_data: dict, confirmed_risk: str):
        """
        Called after human operator makes a decision.
        Retrains model on the growing real-world history.
        """
        if confirmed_risk not in RISK_MAP:
            print(f"[ML] Unknown risk label '{confirmed_risk}' — skipping update")
            return

        features = extract_features(grid_data)
        self.history_X.append(features)
        self.history_y.append(RISK_MAP[confirmed_risk])
        self._train()
        print(f"[ML] ✅ Model retrained — {len(self.history_y)} real samples now in history")

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save(self):
        joblib.dump({
            "classifier":       self.classifier,
            "anomaly_detector": self.anomaly_detector,
            "scaler":           self.scaler,
            "history_X":        self.history_X,
            "history_y":        self.history_y
        }, MODEL_PATH)

    def _load(self):
        data                  = joblib.load(MODEL_PATH)
        self.classifier       = data["classifier"]
        self.anomaly_detector = data["anomaly_detector"]
        self.scaler           = data["scaler"]
        self.history_X        = data["history_X"]
        self.history_y        = data["history_y"]
        self.is_trained       = True
        print(f"[ML] Model loaded — trained on {len(self.history_y)} samples")


# Singleton — imported everywhere
ml_model = GridMLModel()