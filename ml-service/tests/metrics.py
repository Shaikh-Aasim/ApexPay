import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report
)

def print_overall_metrics(y_true: np.ndarray, y_pred: np.ndarray):
    """Prints standard classification metrics."""
    print("\n" + "="*40)
    print("      OVERALL EVALUATION METRICS")
    print("="*40)
    print(f"Accuracy:  {accuracy_score(y_true, y_pred):.4f}")
    print(f"Precision: {precision_score(y_true, y_pred):.4f} (Very Important)")
    print(f"Recall:    {recall_score(y_true, y_pred):.4f}")
    print(f"F1-score:  {f1_score(y_true, y_pred):.4f}")
    
    print("\nConfusion Matrix:")
    print(confusion_matrix(y_true, y_pred))
    
    print("\nClassification Report:")
    print(classification_report(y_true, y_pred))

def run_threshold_testing(y_true: np.ndarray, prob_scores: np.ndarray):
    """Tests different probability thresholds and prints impact on metrics."""
    thresholds = [0.4, 0.5, 0.6, 0.7]
    print("\n" + "="*40)
    print("      THRESHOLD TUNING ANALYSIS")
    print("="*40)
    print(f"{'Threshold':<12} | {'Precision':<10} | {'Recall':<10} | {'F1':<10} | {'FP Count':<10}")
    print("-" * 60)
    
    for t in thresholds:
        preds = (prob_scores >= t).astype(int)
        p = precision_score(y_true, preds, zero_division=0)
        r = recall_score(y_true, preds, zero_division=0)
        f1 = f1_score(y_true, preds, zero_division=0)
        fp = np.sum((preds == 1) & (y_true == 0))
        print(f"{t:<12} | {p:<10.4f} | {r:<10.4f} | {f1:<10.4f} | {fp:<10}")

def analyze_false_positives(df: pd.DataFrame, y_true: np.ndarray, y_pred: np.ndarray):
    """Identifies and explains false positive cases."""
    fp_indices = np.where((y_pred == 1) & (y_true == 0))[0]
    
    print("\n" + "="*40)
    print(f"   FALSE POSITIVE ANALYSIS (Total: {len(fp_indices)})")
    print("="*40)
    
    if len(fp_indices) == 0:
        print("Excellent! No false positives detected.")
        return

    # Analyze top 15 FPs (or all if fewer)
    sample_indices = fp_indices[:15]
    for i, idx in enumerate(sample_indices):
        row = df.iloc[idx]
        print(f"\nFP CASE #{i+1} (Index {idx}):")
        print(f"  - Amount: {row['amount']:.2f} (Global High: {row['is_high_amount_global']})")
        print(f"  - Z-Score: {row['amount_zscore']:.2f}")
        print(f"  - Txn 24h: {row['txn_count_24h']}")
        print(f"  - Device Change: {row['device_change']}, Location Anomaly: {row['location_anomaly']}")
        print(f"  - Periodic Pattern: {row['is_periodic_pattern']}, Stability: {row['relationship_stability_score']:.2f}")
        
        # Simple heuristic explanation
        reasons = []
        if row['amount_zscore'] > 3: reasons.append("High Z-Score deviation")
        if row['device_change'] == 1: reasons.append("New device detected")
        if row['location_anomaly'] == 1: reasons.append("Location anomaly detected")
        if row['txn_count_24h'] > 10: reasons.append("High transaction frequency")
        
        explanation = ", ".join(reasons) if reasons else "Mixed suspicious features"
        print(f"  - Possible Reason for Misclassification: {explanation}")
