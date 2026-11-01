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
from sklearn.calibration import CalibratedClassifierCV
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

# def generate_synthetic_data(n_samples: int = 50000, seed: int = 42) -> Tuple[pd.DataFrame, np.ndarray]:
#     rng = np.random.default_rng(seed)
#     data = []
#     labels = []

#     # Target: ~30% fraud, 70% normal (more realistic imbalance)
#     n_fraud = int(n_samples * 0.2)
#     n_normal = n_samples - n_fraud

#     # --- Generate Normal Cases (with overlap/noise) ---
#     for _ in range(n_normal):
#         case_type = rng.choice(["small_frequent", "monthly_recurring", "standard", "high_value_legit"])
        
#         user_avg = rng.uniform(500, 5000)
#         user_std = rng.uniform(50, 500)
        
#         device_change = 0.0
#         location_anomaly = 0.0
#         receiver_flagged = 0.0
        
#         if case_type == "small_frequent":
#             amount = rng.uniform(10, 200)
#             txn_count_24h = rng.integers(1, 6)
#             is_periodic = False
#         elif case_type == "monthly_recurring":
#             amount = rng.uniform(1000, 5000)
#             txn_count_24h = 1
#             is_periodic = True
#         elif case_type == "high_value_legit":
#             # Legitimate high value (e.g., buying a laptop or paying rent)
#             amount = rng.uniform(10000, 30000)
#             txn_count_24h = rng.integers(1, 3)
#             is_periodic = rng.choice([True, False])
#             # Occasional noise: sometimes legit users use a new device
#             if rng.random() < 0.05: device_change = 1.4
#         else:
#             amount = rng.normal(user_avg, user_std)
#             txn_count_24h = rng.integers(1, 4)
#             is_periodic = False

#         # Add noise to amount and txn_count
#         amount = max(1.0, add_noise(amount, 0.03, rng))
#         txn_count_24h = float(max(1, int(add_noise(txn_count_24h, 0.1, rng))))
        
#         row = {
#             "amount": amount,
#             "txn_count_24h": txn_count_24h,
#             "device_change": device_change,
#             "location_anomaly": location_anomaly,
#             "receiver_flagged": receiver_flagged,
#             "receiver_suspicion_score": rng.beta(2, 15), # Low suspicion
#             "user_avg_amount_30d": user_avg,
#             "user_std_amount_30d": user_std,
#             "amount_zscore": calculate_zscore(amount, user_avg, user_std),
#             "is_first_transaction": 0.0,
#             "user_total_txn": float(rng.integers(5, 1000)),
#             "account_age_hours": float(rng.uniform(72, 17520)),
#             "is_periodic_pattern": 1.0 if is_periodic else 0.0,
#             "day_of_month": float(rng.integers(1, 31)),
#             "relationship_stability_score": rng.uniform(0.4, 1.0),
#             "is_high_amount_global": 1.0 if amount > 50000 else 0.0,
#             "amount_percentile_global": rng.uniform(0.05, 0.75)
#         }
        
#         # Randomly flip some features to create class overlap
#         if rng.random() < 0.02: row["location_anomaly"] = 1.0 # Legit user traveling
#         if rng.random() < 0.01: row["receiver_flagged"] = 1.0 # Legit user accidentally sending to flagged
            
#         data.append(row)
#         labels.append(0)

#     # --- Generate Fraud Cases (with noise/normal-looking fraud) ---
#     for _ in range(n_fraud):
#         fraud_type = rng.choice(["first_txn_high", "ato", "velocity", "high_zscore", "mule", "stealth_fraud"])
        
#         user_avg = rng.uniform(500, 5000)
#         user_std = rng.uniform(50, 500)
        
#         row = {
#             "amount": rng.uniform(100, 5000),
#             "txn_count_24h": float(rng.integers(1, 5)),
#             "device_change": 0.0,
#             "location_anomaly": 0.0,
#             "receiver_flagged": 0.0,
#             "receiver_suspicion_score": rng.beta(5, 5), # Higher suspicion
#             "user_avg_amount_30d": user_avg,
#             "user_std_amount_30d": user_std,
#             "amount_zscore": 0.0,
#             "is_first_transaction": 0.0,
#             "user_total_txn": float(rng.integers(10, 500)),
#             "account_age_hours": float(rng.uniform(72, 8760)),
#             "is_periodic_pattern": 0.0,
#             "day_of_month": float(rng.integers(1, 31)),
#             "relationship_stability_score": rng.uniform(0.0, 0.5),
#             "is_high_amount_global": 0.0,
#             "amount_percentile_global": rng.uniform(0.6, 0.99)
#         }

#         if fraud_type == "first_txn_high":
#             row["is_first_transaction"] = 1.0
#             row["amount"] = rng.uniform(5000, 40000)
#             row["user_total_txn"] = 1.0
#             row["account_age_hours"] = rng.uniform(0.1, 12)
#         elif fraud_type == "ato":
#             row["device_change"] = 1.0
#             row["location_anomaly"] = 1.0
#             row["amount"] = rng.uniform(2000, 20000)
#         elif fraud_type == "velocity":
#             row["txn_count_24h"] = float(rng.integers(10, 25))
#         elif fraud_type == "high_zscore":
#             row["amount"] = user_avg + (user_std * rng.uniform(3, 8))
#         elif fraud_type == "mule":
#             row["receiver_flagged"] = 1.0
#             row["receiver_suspicion_score"] = rng.uniform(0.7, 1.0)
#         elif fraud_type == "stealth_fraud":
#             # Fraud that looks normal (small amount, no anomalies)
#             row["amount"] = rng.uniform(50, 300)
#             row["relationship_stability_score"] = rng.uniform(0.3, 0.6)
#             # This will create hard-to-detect cases

#         # Add noise
#         row["amount"] = max(1.0, add_noise(row["amount"], 0.05, rng))
#         row["amount_zscore"] = calculate_zscore(row["amount"], user_avg, user_std)
#         row["is_high_amount_global"] = 1.0 if row["amount"] > 50000 else 0.0
        
#         data.append(row)
#         labels.append(1)

#     df = pd.DataFrame(data)
#     y = np.array(labels)
#     return df, y

def corrupt_features(row, rng):
    """Structured feature corruption (real-world noise)."""
    if rng.random() < 0.15:
        row["device_change"] = rng.choice([0.0, 1.0])
        row["location_anomaly"] = rng.choice([0.0, 1.0])
        row["receiver_flagged"] = rng.choice([0.0, 1.0])
        row["relationship_stability_score"] *= rng.uniform(0.3, 1.7)
    return row


def generate_synthetic_data(n_samples: int = 100000, seed: int = 42):
    rng = np.random.default_rng(seed)
    data = []
    labels = []

    n_fraud = int(n_samples * 0.40)
    n_normal = n_samples - n_fraud

    # ---------------- NORMAL CASES ----------------
    for _ in range(n_normal):
        case_type = rng.choice(["small_frequent", "monthly_recurring", "standard", "high_value_legit"])

        user_avg = rng.lognormal(mean=8.3, sigma=0.7)
        user_std = user_avg * rng.uniform(0.05, 0.6)

        device_change = 1.0 if rng.random() > 0.97 else 0.0
        location_anomaly = 1.0 if rng.random() > 0.97 else 0.0
        receiver_flagged = 1.0 if rng.random() < 0.01 else 0.0

        if case_type == "small_frequent":
            amount = rng.gamma(2.0, 80)
            txn_count_24h = rng.poisson(3)

        elif case_type == "monthly_recurring":
            amount = user_avg * rng.uniform(0.8, 1.2)
            txn_count_24h = 1

        elif case_type == "high_value_legit":
            amount = rng.lognormal(10.2, 0.5)
            txn_count_24h = rng.integers(1, 4)

        else:
            amount = rng.normal(user_avg, user_std)
            txn_count_24h = rng.poisson(2)

        amount = max(1.0, amount)

        # 🔥 increased noise (controlled)
        amount *= (1 + rng.normal(0, 0.25))
        txn_count_24h = max(1, int(txn_count_24h * (1 + rng.normal(0, 0.4))))

        is_periodic = rng.random() < 0.35 if case_type == "monthly_recurring" else False

        row = {
            "amount": amount,
            "txn_count_24h": float(txn_count_24h),
            "device_change": float(device_change),
            "location_anomaly": float(location_anomaly),
            "receiver_flagged": float(receiver_flagged),
            "receiver_suspicion_score": float(rng.beta(2, 10)),
            "user_avg_amount_30d": user_avg,
            "user_std_amount_30d": user_std,
            "amount_zscore": calculate_zscore(amount, user_avg, user_std),
            "is_first_transaction": 0.0,
            "user_total_txn": float(rng.integers(5, 2000)),
            "account_age_hours": float(rng.gamma(2, 2000)),
            "is_periodic_pattern": 1.0 if is_periodic else 0.0,
            "day_of_month": float(rng.integers(1, 31)),
            "relationship_stability_score": float(rng.uniform(0.2, 1.0)),
            "is_high_amount_global": 0.0,
            "amount_percentile_global": float(rng.uniform(0.0, 0.9))
        }

        # 🔥 feature corruption
        row = corrupt_features(row, rng)

        # 🔥 harder negatives (normal behaving like fraud)
        if rng.random() < 0.1:
            row["txn_count_24h"] = float(rng.integers(10, 25))

        # 🔥 label noise increased (controlled)
        label = 0
        if rng.random() < 0.06:
            label = 1

        labels.append(label)
        data.append(row)

    # ---------------- FRAUD CASES ----------------
    for _ in range(n_fraud):
        fraud_type = rng.choice([
            "first_txn_high", "ato", "velocity",
            "high_zscore", "mule", "stealth_fraud", "ultra_stealth"
        ])

        user_avg = rng.lognormal(8.2, 0.8)
        user_std = user_avg * rng.uniform(0.1, 0.8)

        amount = rng.lognormal(9.5, 1.0)
        txn_count_24h = rng.poisson(2)

        device_change = 0.0
        location_anomaly = 0.0
        receiver_flagged = 0.0

        if fraud_type == "first_txn_high":
            amount *= rng.uniform(3, 10)
            txn_count_24h = 1

        elif fraud_type == "ato":
            device_change = 1.0
            location_anomaly = 1.0
            amount *= rng.uniform(2, 6)

        elif fraud_type == "velocity":
            txn_count_24h = rng.integers(8, 30)

        elif fraud_type == "high_zscore":
            amount = user_avg + user_std * rng.uniform(4, 12)

        elif fraud_type == "mule":
            receiver_flagged = 1.0

        elif fraud_type == "stealth_fraud":
            amount = rng.normal(user_avg * rng.uniform(0.8, 1.3), user_std)

        elif fraud_type == "ultra_stealth":
            # 🔥 extremely hard fraud (almost identical to normal)
            amount = user_avg * rng.uniform(0.9, 1.1)
            txn_count_24h = rng.poisson(2)

        amount = max(1.0, amount)

        # 🔥 stronger noise
        amount *= (1 + rng.normal(0, 0.25))

        row = {
            "amount": amount,
            "txn_count_24h": float(txn_count_24h),
            "device_change": float(device_change),
            "location_anomaly": float(location_anomaly),
            "receiver_flagged": float(receiver_flagged),
            "receiver_suspicion_score": float(rng.beta(5, 5)),
            "user_avg_amount_30d": user_avg,
            "user_std_amount_30d": user_std,
            "amount_zscore": calculate_zscore(amount, user_avg, user_std),
            "is_first_transaction": float(rng.random() < 0.15),
            "user_total_txn": float(rng.integers(1, 500)),
            "account_age_hours": float(rng.gamma(2, 1000)),
            "is_periodic_pattern": 0.0,
            "day_of_month": float(rng.integers(1, 31)),
            "relationship_stability_score": float(rng.uniform(0.0, 0.8)),
            "is_high_amount_global": float(amount > 40000), # amount > 40k
            "amount_percentile_global": float(rng.uniform(0.3, 1.0))
        }

        # 🔥 feature corruption
        row = corrupt_features(row, rng)

        # 🔥 label noise
        label = 1
        if rng.random() < 0.05:
            label = 0

        labels.append(label)
        data.append(row)

    df = pd.DataFrame(data)
    y = np.array(labels)

    return df, y
def evaluate_thresholds(model, X_test, y_test):
    """Evaluates different probability thresholds for precision-recall trade-off."""
    probs = model.predict_proba(X_test)[:, 1]
    # thresholds = [0.45]
    thresholds = [0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6]

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

# ---------------- ADD THIS FUNCTION ABOVE main() ----------------
def add_test_noise(df, seed=42):
    """Adds extra noise ONLY to test set (more complex + realistic)."""
    rng = np.random.default_rng(seed)

    df = df.copy()

    # Strong numeric noise
    for col in ["amount", "txn_count_24h", "amount_zscore"]:
        if col in df.columns:
            df[col] = df[col] * (1 + rng.normal(0, 0.4, size=len(df)))

    # Feature corruption
    mask = rng.random(len(df)) < 0.25
    df.loc[mask, "device_change"] = rng.choice([0.0, 1.0], size=mask.sum())
    df.loc[mask, "location_anomaly"] = rng.choice([0.0, 1.0], size=mask.sum())

    # Small label noise
    flip_mask = rng.random(len(df)) < 0.08
    df.loc[flip_mask, "label"] = 1 - df.loc[flip_mask, "label"]

    return df

# def main():
#     print("Generating improved synthetic dataset...")
#     df, y = generate_synthetic_data(n_samples=50000)
    
#     # Stratified split
#     X = df[FEATURES].values
#     X_train, X_test, y_train, y_test, indices_train, indices_test = train_test_split(
#         X, y, np.arange(len(y)), test_size=0.2, random_state=42, stratify=y
#     )
    
#     df_test = df.iloc[indices_test].copy()

#     print("Running 5-fold Cross-Validation...")
#     model_cv = RandomForestClassifier(
#         n_estimators=300, max_depth=7, class_weight={0:1, 1:4}, random_state=42, n_jobs=-1, min_samples_leaf = 5
#     )
#     cv_scores = cross_val_score(model_cv, X_train, y_train, cv=5, scoring='f1')
#     print(f"CV F1-score: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")

#     print("\nTraining final model on training set...")
#     model = RandomForestClassifier(
#         n_estimators=300, max_depth=7, class_weight={0:1, 1:4}, random_state=42, n_jobs=-1,    min_samples_leaf=5
#     )
#     model.fit(X_train, y_train)
    
#     # Evaluation on Test Set
#     # y_pred = model.predict(X_test)
#     probs = model.predict_proba(X_test)[:, 1]
#     threshold = 0.45
#     y_pred = (probs >= threshold).astype(int)
    
#     print("\n--- Final Model Evaluation (Test Set) ---")
#     print(f"Accuracy:  {accuracy_score(y_test, y_pred):.4f}")
#     print(f"Precision: {precision_score(y_test, y_pred):.4f}")
#     print(f"Recall:    {recall_score(y_test, y_pred):.4f}")
#     print(f"F1-score:  {f1_score(y_test, y_pred):.4f}")
    
#     print("\nConfusion Matrix:")
#     print(confusion_matrix(y_test, y_pred))
    
#     print("\nClassification Report:")
#     print(classification_report(y_test, y_pred))

#     # Threshold Tuning
#     evaluate_thresholds(model, X_test, y_test)
    
#     # False Positive Analysis
#     analyze_false_positives(model, df_test, X_test, y_test)

#     # Save model and metrics
#     MODEL_DIR.mkdir(parents=True, exist_ok=True)
#     joblib.dump({"model": model, "features": FEATURES, "version": "2.1.0"}, MODEL_PATH)
    
#     metrics = {
#         "accuracy": float(accuracy_score(y_test, y_pred)),
#         "precision": float(precision_score(y_test, y_pred)),
#         "recall": float(recall_score(y_test, y_pred)),
#         "f1_score": float(f1_score(y_test, y_pred)),
#         "model_version": "2.1.0"
#     }
#     METRICS_PATH.write_text(json.dumps(metrics, indent=4))
#     print(f"\nModel and metrics saved.")
def main():
    print("Generating improved synthetic dataset...")
    # df, y = generate_synthetic_data(n_samples=100000)
    df = pd. read_csv("test_data_large.csv")

    print(df.columns)
    print(df.head())

    # ---------------- CUSTOM SPLIT ----------------
    df_fraud = df[df["label"] == 1]
    df_normal = df[df["label"] == 0]

    print(f"Fraud: {len(df_fraud)}, Normal: {len(df_normal)}")

    # TRAIN → 40k (target 50-50)
    n_train = 40000

    # ✅ define FIRST
    n_half = n_train // 2   # 20000

    # ✅ keep some fraud for testing (VERY IMPORTANT)
    max_train_fraud = int(len(df_fraud) * 0.8)

    # ✅ safe adjustment
    n_half = min(n_half, max_train_fraud, len(df_normal))

    print(f"Using {n_half} fraud + {n_half} normal for training")

    # ✅ sample safely
    train_fraud = df_fraud.sample(n=n_half, random_state=42)
    train_normal = df_normal.sample(n=n_half, random_state=42)
    # train_fraud = df_fraud.sample(n=n_half, random_state=42)
    # train_normal = df_normal.sample(n=n_half, random_state=42)

    df_train = pd.concat([train_fraud, train_normal]).sample(frac=1).reset_index(drop=True)

    # Remove used samples
    df_fraud_remaining = df_fraud.drop(train_fraud.index)
    df_normal_remaining = df_normal.drop(train_normal.index)

    # TEST → 10k (10% fraud)
    n_test = 10000
    n_fraud_test = int(n_test * 0.1)   # 1000 fraud
    n_normal_test = n_test - n_fraud_test  # 9000 normal

    test_fraud = df_fraud_remaining.sample(
        n=n_fraud_test,
        replace=(len(df_fraud_remaining) < n_fraud_test),
        random_state=42
    )

    test_normal = df_normal_remaining.sample(
        n=n_normal_test,
        replace=(len(df_normal_remaining) < n_normal_test),
        random_state=42
    )

    df_test = pd.concat([test_fraud, test_normal]).sample(frac=1).reset_index(drop=True)
    ###############################

    # TEST → 80% normal / 20% fraud
    # n_test = 10000
    # n_fraud_test = int(n_test * 0.1)
    # n_normal_test = n_test - n_fraud_test

    # # Remove used samples
    # df_fraud_remaining = df_fraud.drop(train_fraud.index)
    # df_normal_remaining = df_normal.drop(train_normal.index)

    # test_fraud = df_fraud_remaining.sample(n=n_fraud_test, random_state=42)
    # test_normal = df_normal_remaining.sample(n=n_normal_test, random_state=42)

    # df_test = pd.concat([test_fraud, test_normal]).sample(frac=1).reset_index(drop=True)

    # 🔥 ADD EXTRA NOISE TO TEST SET
    df_test = add_test_noise(df_test)

    # ---------------- PREPARE DATA ----------------
    X_train = df_train[FEATURES].values
    y_train = df_train["label"].values

    X_test = df_test[FEATURES].values
    y_test = df_test["label"].values

    # ---------------- MODEL TRAINING ----------------
    print("Running 5-fold Cross-Validation...")
    model_cv = RandomForestClassifier(
        n_estimators=500,
        max_depth=12,
        class_weight={0:1, 1:2},
        random_state=42,
        n_jobs=-1,
        min_samples_leaf=3
    )

    cv_scores = cross_val_score(model_cv, X_train, y_train, cv=5, scoring='f1')
    print(f"CV F1-score: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")

    print("\nTraining final model on training set...")
    rf = RandomForestClassifier(
        n_estimators=500,
        max_depth=12,
        class_weight={0:1, 1:2},
        random_state=42,
        n_jobs=-1,
        min_samples_leaf=3
    )
    model = CalibratedClassifierCV(
    rf,
    method='sigmoid',   # use sigmoid (best for your case)
    cv=3                # internal CV for calibration
)
    model.fit(X_train, y_train)

    # ---------------- EVALUATION ----------------
    probs = model.predict_proba(X_test)[:, 1]
    # if amount > 20000:
    threshold = 0.3

    y_pred = (probs >= threshold).astype(int)

    print("\n--- Final Model Evaluation (Test Set) ---")
    print(f"Accuracy:  {accuracy_score(y_test, y_pred):.4f}")
    print(f"Precision: {precision_score(y_test, y_pred):.4f}")
    print(f"Recall:    {recall_score(y_test, y_pred):.4f}")
    print(f"F1-score:  {f1_score(y_test, y_pred):.4f}")

    print("\nConfusion Matrix:")
    print(confusion_matrix(y_test, y_pred))

    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))

    # Threshold tuning
    evaluate_thresholds(model, X_test, y_test)

    # False positives
    analyze_false_positives(model, df_test, X_test, y_test)

    # ---------------- SAVE ----------------
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
