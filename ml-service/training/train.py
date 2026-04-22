from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split

from utils.risk_rules import heuristic_risk


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "model"
MODEL_PATH = MODEL_DIR / "risk_model.joblib"
METRICS_PATH = MODEL_DIR / "metrics.json"


FEATURES: List[str] = [
    "amount",
    "txn_count_24h",
    "device_change",
    "location_anomaly",
    "receiver_suspicion_score",
    "receiver_flagged",
    "user_avg_amount_30d",
    "user_std_amount_30d",
    "amount_zscore",
]


def make_row(rng: np.random.Generator) -> Tuple[Dict[str, float], int]:
    user_avg = float(rng.uniform(200, 8000))
    user_std = float(max(1.0, rng.uniform(50, 2500)))

    amount = float(rng.lognormal(mean=np.log(max(1.0, user_avg)), sigma=0.8))
    amount = float(min(amount, 150000.0))
    amount_z = (amount - user_avg) / user_std

    txn_count_24h = int(rng.poisson(lam=2.5))
    device_change = int(rng.random() < 0.08)
    location_anomaly = int(rng.random() < 0.08)
    receiver_suspicion_score = float(rng.beta(2, 8))
    receiver_flagged = int(rng.random() < 0.02)

    res = heuristic_risk(
        amount=amount,
        amount_zscore=float(amount_z),
        device_change=device_change,
        location_anomaly=location_anomaly,
        txn_count_24h=txn_count_24h,
        receiver_suspicion_score=receiver_suspicion_score,
        receiver_flagged=receiver_flagged,
    )

    y = 1 if res.risk_score >= 0.70 else 0
    if rng.random() < 0.03:
        y = 1 - y

    row = {
        "amount": amount,
        "txn_count_24h": float(txn_count_24h),
        "device_change": float(device_change),
        "location_anomaly": float(location_anomaly),
        "receiver_suspicion_score": receiver_suspicion_score,
        "receiver_flagged": float(receiver_flagged),
        "user_avg_amount_30d": user_avg,
        "user_std_amount_30d": user_std,
        "amount_zscore": float(amount_z),
    }

    return row, y


def build_dataset(n: int, seed: int = 42) -> Tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    rows: List[Dict[str, float]] = []
    ys: List[int] = []
    for _ in range(n):
        row, y = make_row(rng)
        rows.append(row)
        ys.append(y)
    X = np.array([[float(r[f]) for f in FEATURES] for r in rows], dtype=float)
    y = np.array(ys, dtype=int)
    return X, y


def main() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    X, y = build_dataset(5000)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)

    model = RandomForestClassifier(
        n_estimators=250,
        random_state=42,
        max_depth=10,
        min_samples_leaf=5,
        n_jobs=-1,
        class_weight="balanced_subsample",
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1_score": float(f1_score(y_test, y_pred, zero_division=0)),
        "model_version": "rf-1",
        "features": FEATURES,
        "samples": int(len(y)),
        "positive_rate": float(np.mean(y)),
    }

    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    joblib.dump({"model": model, "features": FEATURES, "version": "rf-1"}, MODEL_PATH)


if __name__ == "__main__":
    main()

