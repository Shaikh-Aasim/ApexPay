from __future__ import annotations
import json
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
import sys
from typing import Dict, List, Tuple

# Ensure ml-service root is in sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, f1_score, precision_score, recall_score, 
    confusion_matrix, classification_report
)
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import train_test_split, cross_val_score

from utils.features import FEATURES, calculate_zscore
from tests.test_data_generator import generate_large_scale_test_suite

MODEL_DIR = ROOT / "model"
MODEL_PATH = MODEL_DIR / "risk_model.joblib"
METRICS_PATH = MODEL_DIR / "metrics.json"

def evaluate_thresholds(model, X_test, y_test):
    """Evaluates probability thresholds matching the 3-tier decision matrix."""
    probs = model.predict_proba(X_test)[:, 1]
    thresholds = [0.30, 0.40, 0.45, 0.50, 0.60, 0.70]

    print("\n--- Probability Threshold Sweep ---")
    print(f"{'Threshold':<12} | {'Precision':<10} | {'Recall':<10} | {'F1':<10}")
    print("-" * 50)
    for t in thresholds:
        preds = (probs >= t).astype(int)
        p = precision_score(y_test, preds, zero_division=0)
        r = recall_score(y_test, preds, zero_division=0)
        f1 = f1_score(y_test, preds, zero_division=0)
        print(f"{t:<12.2f} | {p:<10.4f} | {r:<10.4f} | {f1:<10.4f}")

def analyze_false_positives(model, df_test, X_test, y_test):
    """Analyzes sample false positive cases for auditing."""
    probs = model.predict_proba(X_test)[:, 1]
    preds = (probs >= 0.45).astype(int)
    fp_indices = np.where((preds == 1) & (y_test == 0))[0]
    
    print(f"\n--- False Positive Audit (Total FPs: {len(fp_indices)} out of {len(y_test)} test samples) ---")
    if len(fp_indices) == 0:
        print("Zero false positives found.")
        return

    sample_size = min(5, len(fp_indices))
    sample_indices = np.random.choice(fp_indices, sample_size, replace=False)
    
    fp_samples = df_test.iloc[sample_indices]
    for i, (idx, row) in enumerate(fp_samples.iterrows()):
        print(f"FP Case #{i+1} (Amount: INR {row['amount']:.2f}, Z: {row['amount_zscore']:.2f}, Txn24h: {row['txn_count_24h']}, Device: {row['device_change']}, Periodic: {row['is_periodic_pattern']})")

def main():
    print("=" * 60)
    print("      APEXPAY RISK MODEL TRAINING PIPELINE")
    print("=" * 60)

    dataset_path = ROOT / "test_data_large.csv"
    if not dataset_path.exists():
        print("[1/4] Generating canonical dataset...")
        generate_large_scale_test_suite()
    else:
        print(f"[1/4] Loading canonical dataset from {dataset_path}...")

    df = pd.read_csv(dataset_path)
    print(f"Loaded {len(df)} samples with {len(df.columns)} columns.")

    # Validate feature presence
    missing_cols = set(FEATURES) - set(df.columns)
    if missing_cols:
        raise ValueError(f"Dataset missing required features: {missing_cols}")

    # Prepare features and labels
    X = df[FEATURES].values
    y = df["label"].values.astype(int)

    # Stratified Train/Test Split (80% train, 20% test)
    print("\n[2/4] Executing Stratified Train/Test Split (80/20)...")
    X_train, X_test, y_train, y_test, idx_train, idx_test = train_test_split(
        X, y, np.arange(len(y)), test_size=0.20, random_state=42, stratify=y
    )
    df_test = df.iloc[idx_test].copy().reset_index(drop=True)
    
    print(f"Train samples: {len(X_train)} (Fraud: {np.sum(y_train == 1)}), Test samples: {len(X_test)} (Fraud: {np.sum(y_test == 1)})")

    # 5-Fold Cross Validation on Base Random Forest
    print("\n[3/4] Running 5-Fold Cross-Validation on Base RandomForest...")
    base_rf = RandomForestClassifier(
        n_estimators=150,
        max_depth=10,
        min_samples_leaf=4,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1
    )
    cv_scores = cross_val_score(base_rf, X_train, y_train, cv=5, scoring="f1")
    print(f"CV F1-score: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")

    # Train Final Calibrated Model
    print("\n[4/4] Training and Calibrating Final Model (Sigmoid CV=3)...")
    final_rf = RandomForestClassifier(
        n_estimators=150,
        max_depth=10,
        min_samples_leaf=4,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1
    )
    calibrated_model = CalibratedClassifierCV(final_rf, method="sigmoid", cv=3)
    calibrated_model.fit(X_train, y_train)

    # Set n_jobs=1 on underlying estimators for fast single-sample production inference
    for c in calibrated_model.calibrated_classifiers_:
        if hasattr(c, "estimator"):
            c.estimator.n_jobs = 1

    # Evaluate on Test Set
    probs = calibrated_model.predict_proba(X_test)[:, 1]
    threshold = 0.45  # Aligned with MEDIUM / Step-Up boundary
    y_pred = (probs >= threshold).astype(int)

    acc = float(accuracy_score(y_test, y_pred))
    prec = float(precision_score(y_test, y_pred, zero_division=0))
    rec = float(recall_score(y_test, y_pred, zero_division=0))
    f1 = float(f1_score(y_test, y_pred, zero_division=0))

    print("\n" + "=" * 50)
    print("   FINAL TEST SET EVALUATION (Decision Threshold = 0.45)")
    print("=" * 50)
    print(f"Accuracy:  {acc:.4f}")
    print(f"Precision: {prec:.4f}")
    print(f"Recall:    {rec:.4f}")
    print(f"F1-Score:  {f1:.4f}")
    print("\nConfusion Matrix:")
    print(confusion_matrix(y_test, y_pred))
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))

    # Evaluate across threshold spectrum
    evaluate_thresholds(calibrated_model, X_test, y_test)

    # Audit false positives
    analyze_false_positives(calibrated_model, df_test, X_test, y_test)

    # Save trained model and metrics
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_artifact = {
        "model": calibrated_model,
        "features": FEATURES,
        "version": "2.2.0"
    }
    joblib.dump(model_artifact, MODEL_PATH)

    metrics = {
        "accuracy": acc,
        "precision": prec,
        "recall": rec,
        "f1_score": f1,
        "model_version": "2.2.0"
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=4))
    print(f"\nSuccessfully saved model to {MODEL_PATH} and metrics to {METRICS_PATH}")
    print("=" * 60)

if __name__ == "__main__":
    main()
