from __future__ import annotations
import json
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, f1_score, precision_score, recall_score, 
    confusion_matrix, classification_report
)
from sklearn.model_selection import train_test_split, cross_val_score

from utils.features import FEATURES, calculate_zscore
from utils.risk_rules import heuristic_risk

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "model"
MODEL_PATH = MODEL_DIR / "risk_model.joblib"
METRICS_PATH = MODEL_DIR / "metrics.json"

def add_noise(val: float, noise_level: float = 0.05, rng: np.random.Generator = None) -> float:
    """Adds random Gaussian noise to a numerical value."""
    if rng is None: rng = np.random.default_rng()
    return val * (1 + rng.normal(0, noise_level))

def generate_synthetic_data(n_samples: int = 10000, seed: int = 42) -> Tuple[pd.DataFrame, np.ndarray]:
    rng = np.random.default_rng(seed)
    data = []
    labels = []

    # Target: ~30% fraud, 70% normal (more realistic imbalance)
    n_fraud = int(n_samples * 0.3)
    n_normal = n_samples - n_fraud

    # --- Generate Normal Cases (with overlap/noise) ---
    for _ in range(n_normal):
        case_type = rng.choice(["small_frequent", "monthly_recurring", "standard", "high_value_legit"])
        
        user_avg = rng.uniform(500, 5000)
        user_std = rng.uniform(50, 500)
        
        device_change = 0.0
        location_anomaly = 0.0
        receiver_flagged = 0.0
        
        if case_type == "small_frequent":
            amount = rng.uniform(10, 200)
            txn_count_24h = rng.integers(1, 6)
            is_periodic = False
        elif case_type == "monthly_recurring":
            amount = rng.uniform(1000, 5000)
            txn_count_24h = 1
            is_periodic = True
        elif case_type == "high_value_legit":
            # Legitimate high value (e.g., buying a laptop or paying rent)
            amount = rng.uniform(10000, 30000)
            txn_count_24h = rng.integers(1, 3)
            is_periodic = rng.choice([True, False])
            # Occasional noise: sometimes legit users use a new device
            if rng.random() < 0.05: device_change = 1.0
        else:
            amount = rng.normal(user_avg, user_std)
            txn_count_24h = rng.integers(1, 4)
            is_periodic = False

        # Add noise to amount and txn_count
        amount = max(1.0, add_noise(amount, 0.03, rng))
        txn_count_24h = float(max(1, int(add_noise(txn_count_24h, 0.1, rng))))
        
        row = {
            "amount": amount,
            "txn_count_24h": txn_count_24h,
            "device_change": device_change,
            "location_anomaly": location_anomaly,
            "receiver_flagged": receiver_flagged,
            "receiver_suspicion_score": rng.beta(2, 15), # Low suspicion
            "user_avg_amount_30d": user_avg,
            "user_std_amount_30d": user_std,
            "amount_zscore": calculate_zscore(amount, user_avg, user_std),
            "is_first_transaction": 0.0,
            "user_total_txn": float(rng.integers(5, 1000)),
            "account_age_hours": float(rng.uniform(72, 17520)),
            "is_periodic_pattern": 1.0 if is_periodic else 0.0,
            "day_of_month": float(rng.integers(1, 31)),
            "relationship_stability_score": rng.uniform(0.4, 1.0),
            "is_high_amount_global": 1.0 if amount > 50000 else 0.0,
            "amount_percentile_global": rng.uniform(0.05, 0.75)
        }
        
        # Randomly flip some features to create class overlap
        if rng.random() < 0.02: row["location_anomaly"] = 1.0 # Legit user traveling
        if rng.random() < 0.01: row["receiver_flagged"] = 1.0 # Legit user accidentally sending to flagged
            
        data.append(row)
        labels.append(0)

    # --- Generate Fraud Cases (with noise/normal-looking fraud) ---
    for _ in range(n_fraud):
        fraud_type = rng.choice(["first_txn_high", "ato", "velocity", "high_zscore", "mule", "stealth_fraud"])
        
        user_avg = rng.uniform(500, 5000)
        user_std = rng.uniform(50, 500)
        
        row = {
            "amount": rng.uniform(100, 5000),
            "txn_count_24h": float(rng.integers(1, 5)),
            "device_change": 0.0,
            "location_anomaly": 0.0,
            "receiver_flagged": 0.0,
            "receiver_suspicion_score": rng.beta(5, 5), # Higher suspicion
            "user_avg_amount_30d": user_avg,
            "user_std_amount_30d": user_std,
            "amount_zscore": 0.0,
            "is_first_transaction": 0.0,
            "user_total_txn": float(rng.integers(10, 500)),
            "account_age_hours": float(rng.uniform(72, 8760)),
            "is_periodic_pattern": 0.0,
            "day_of_month": float(rng.integers(1, 31)),
            "relationship_stability_score": rng.uniform(0.0, 0.5),
            "is_high_amount_global": 0.0,
            "amount_percentile_global": rng.uniform(0.6, 0.99)
        }

        if fraud_type == "first_txn_high":
            row["is_first_transaction"] = 1.0
            row["amount"] = rng.uniform(5000, 40000)
            row["user_total_txn"] = 1.0
            row["account_age_hours"] = rng.uniform(0.1, 12)
        elif fraud_type == "ato":
            row["device_change"] = 1.0
            row["location_anomaly"] = 1.0
            row["amount"] = rng.uniform(2000, 20000)
        elif fraud_type == "velocity":
            row["txn_count_24h"] = float(rng.integers(10, 25))
        elif fraud_type == "high_zscore":
            row["amount"] = user_avg + (user_std * rng.uniform(3, 8))
        elif fraud_type == "mule":
            row["receiver_flagged"] = 1.0
            row["receiver_suspicion_score"] = rng.uniform(0.7, 1.0)
        elif fraud_type == "stealth_fraud":
            # Fraud that looks normal (small amount, no anomalies)
            row["amount"] = rng.uniform(50, 300)
            row["relationship_stability_score"] = rng.uniform(0.3, 0.6)
            # This will create hard-to-detect cases

        # Add noise
        row["amount"] = max(1.0, add_noise(row["amount"], 0.05, rng))
        row["amount_zscore"] = calculate_zscore(row["amount"], user_avg, user_std)
        row["is_high_amount_global"] = 1.0 if row["amount"] > 50000 else 0.0
        
        data.append(row)
        labels.append(1)

    df = pd.DataFrame(data)
    y = np.array(labels)
    return df, y

def evaluate_thresholds(model, X_test, y_test):
    """Evaluates different probability thresholds for precision-recall trade-off."""
    probs = model.predict_proba(X_test)[:, 1]
    thresholds = [0.4, 0.5, 0.6, 0.7]
    print("\n--- Threshold Tuning ---")
    print(f"{'Threshold':<12} | {'Precision':<10} | {'Recall':<10} | {'F1':<10}")
    print("-" * 50)
    for t in thresholds:
        preds = (probs >= t).astype(int)
        p = precision_score(y_test, preds, zero_division=0)
        r = recall_score(y_test, preds, zero_division=0)
        f1 = f1_score(y_test, preds, zero_division=0)
        print(f"{t:<12} | {p:<10.4f} | {r:<10.4f} | {f1:<10.4f}")

def analyze_false_positives(model, df_test, X_test, y_test):
    """Analyzes and prints sample false positive cases."""
    preds = model.predict(X_test)
    # Predicted fraud (1) but actual normal (0)
    fp_indices = np.where((preds == 1) & (y_test == 0))[0]
    
    print(f"\n--- False Positive Analysis (Total: {len(fp_indices)}) ---")
    if len(fp_indices) == 0:
        print("No false positives found.")
        return

    sample_size = min(10, len(fp_indices))
    sample_indices = np.random.choice(fp_indices, sample_size, replace=False)
    
    fp_samples = df_test.iloc[sample_indices]
    for i, (idx, row) in enumerate(fp_samples.iterrows()):
        print(f"\nFP Case {i+1} (Index {idx}):")
        print(f"  Amount: {row['amount']:.2f}, Z-Score: {row['amount_zscore']:.2f}")
        print(f"  Txn Count 24h: {row['txn_count_24h']}, Device Change: {row['device_change']}")
        print(f"  Periodic: {row['is_periodic_pattern']}, Stability: {row['relationship_stability_score']:.2f}")

def main():
    print("Generating improved synthetic dataset...")
    df, y = generate_synthetic_data(n_samples=10000)
    
    # Stratified split
    X = df[FEATURES].values
    X_train, X_test, y_train, y_test, indices_train, indices_test = train_test_split(
        X, y, np.arange(len(y)), test_size=0.2, random_state=42, stratify=y
    )
    
    df_test = df.iloc[indices_test].copy()

    print("Running 5-fold Cross-Validation...")
    model_cv = RandomForestClassifier(
        n_estimators=250, max_depth=10, class_weight='balanced', random_state=42, n_jobs=-1
    )
    cv_scores = cross_val_score(model_cv, X_train, y_train, cv=5, scoring='f1')
    print(f"CV F1-score: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")

    print("\nTraining final model on training set...")
    model = RandomForestClassifier(
        n_estimators=250, max_depth=10, class_weight='balanced', random_state=42, n_jobs=-1
    )
    model.fit(X_train, y_train)
    
    # Evaluation on Test Set
    y_pred = model.predict(X_test)
    
    print("\n--- Final Model Evaluation (Test Set) ---")
    print(f"Accuracy:  {accuracy_score(y_test, y_pred):.4f}")
    print(f"Precision: {precision_score(y_test, y_pred):.4f}")
    print(f"Recall:    {recall_score(y_test, y_pred):.4f}")
    print(f"F1-score:  {f1_score(y_test, y_pred):.4f}")
    
    print("\nConfusion Matrix:")
    print(confusion_matrix(y_test, y_pred))
    
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))

    # Threshold Tuning
    evaluate_thresholds(model, X_test, y_test)
    
    # False Positive Analysis
    analyze_false_positives(model, df_test, X_test, y_test)

    # Save model and metrics
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "features": FEATURES, "version": "2.1.0"}, MODEL_PATH)
    
    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred)),
        "recall": float(recall_score(y_test, y_pred)),
        "f1_score": float(f1_score(y_test, y_pred)),
        "model_version": "2.1.0"
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=4))
    print(f"\nModel and metrics saved.")

if __name__ == "__main__":
    main()
