import pandas as pd
import numpy as np
import time
import sys
from pathlib import Path
from typing import Dict, Any, List

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from api.predict import RiskPredictor
from tests.noisy_data_generator import generate_noisy_test_data

def calculate_metrics(y_true, y_pred):
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    accuracy = (tp + tn) / len(y_true)
    
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": accuracy,
        "fp": fp,
        "fn": fn,
        "tp": tp,
        "tn": tn
    }

def run_noisy_validation():
    print("\n" + "="*65)
    print("   NOISY REALISTIC FRAUD DETECTION VALIDATION")
    print("="*65)
    
    data_path = "noisy_test_data.csv"
    if not Path(data_path).exists():
        generate_noisy_test_data(8000, data_path)
    
    df = pd.read_csv(data_path)
    predictor = RiskPredictor()
    
    results_wo_graph = []
    results_with_graph = []
    detailed_scores = []
    
    print(f"Processing {len(df)} noisy samples...")
    start_time = time.time()
    
    # Pre-warm graph with some transactions to simulate history
    for i in range(min(500, len(df))):
        row = df.iloc[i]
        predictor.graph_engine.add_transaction(row['sender_id'], row['receiver_id'], row['amount'])

    for idx, row in df.iterrows():
        # Get standard prediction (With Graph)
        data = row.to_dict()
        res = predictor.predict(data)
        
        # Extract individual scores
        ml_s = res["ml_score"]
        rule_s = res["rule_score"]
        graph_s = res["graph_score"]
        
        # Calculate "Without Graph" score (0.7*ML + 0.3*Rules)
        score_wo = 0.7 * ml_s + 0.3 * rule_s
        decision_wo = "HIGH" if score_wo >= 0.7 else "MEDIUM" if score_wo >= 0.4 else "LOW"
        
        pred_wo = 1 if decision_wo in ["HIGH", "MEDIUM"] else 0
        pred_with = 1 if res["decision"] in ["HIGH", "MEDIUM"] else 0
        
        results_wo_graph.append(pred_wo)
        results_with_graph.append(pred_with)
        
        detailed_scores.append({
            "scenario": row["scenario"],
            "label": row["label"],
            "ml_score": ml_s,
            "rule_score": rule_s,
            "graph_score": graph_s,
            "score_wo": score_wo,
            "score_with": res["risk_score"],
            "pred_wo": pred_wo,
            "pred_with": pred_with,
            "decision": res["decision"]
        })

    m_wo = calculate_metrics(df["label"], results_wo_graph)
    m_with = calculate_metrics(df["label"], results_with_graph)

    # 1. MAIN METRICS
    print("\n" + "-"*65)
    print(f"{'Metric':<15} | {'Without Graph':<15} | {'With Graph':<15}")
    print("-"*65)
    for k in ["accuracy", "precision", "recall", "f1"]:
        print(f"{k.capitalize():<15} | {m_wo[k]*100:>14.2f}% | {m_with[k]*100:>14.2f}%")
    print(f"{'FP Count':<15} | {m_wo['fp']:>15} | {m_with['fp']:>15}")
    print(f"{'FN Count':<15} | {m_wo['fn']:>15} | {m_with['fn']:>15}")

    # 2. SCENARIO PERFORMANCE
    print("\n" + "-"*65)
    print(f"{'Scenario Group':<25} | {'Accuracy (With Graph)':<20}")
    print("-"*65)
    
    results_df = pd.DataFrame(detailed_scores)
    # Group scenarios
    results_df['group'] = results_df['scenario'].apply(lambda x: 
        'Normal' if 'normal' in x and 'noisy' not in x else 
        'Noisy Normal' if 'noisy_normal' in x else
        'Fraud (Stealth/Partial)' if 'stealth' in x or 'partial' in x or 'low_degree' in x else
        'Fraud (Burst)' if 'burst' in x else 'Other'
    )
    
    for group in results_df['group'].unique():
        group_df = results_df[results_df['group'] == group]
        acc = (group_df['label'] == group_df['pred_with']).mean()
        print(f"{group:<25} | {acc*100:>19.2f}%")

    # 3. GRAPH IMPACT ANALYSIS
    print("\n" + "="*65)
    print("   GRAPH IMPACT ANALYSIS (NOISY ENVIRONMENT)")
    print("="*65)
    print(f"* Recall improvement:   { (m_with['recall'] - m_wo['recall'])*100:+.2f}%")
    print(f"* Precision change:     { (m_with['precision'] - m_wo['precision'])*100:+.2f}%")
    print(f"* FP increase:          { (m_with['fp'] - m_wo['fp']):+d}")

    # 4. HARD CASE ANALYSIS (10 difficult cases)
    print("\n" + "="*65)
    print("   HARD CASE ANALYSIS (TOP 10 CONFUSED)")
    print("="*65)
    # Filter cases where prediction != label
    hard_cases = results_df[results_df['pred_with'] != results_df['label']].copy()
    
    # Sort by some measure of confusion (e.g., score being far from label but still on the wrong side)
    hard_cases['confusion'] = abs(hard_cases['score_with'] - (1 - hard_cases['label']))
    hard_cases = hard_cases.sort_values('confusion', ascending=False).head(10)
    
    print(f"{'Scenario':<25} | {'Lbl':<3} | {'Pred':<4} | {'ML':<4} | {'Rule':<4} | {'Graph':<5} | {'Reason'}")
    print("-" * 110)
    for _, case in hard_cases.iterrows():
        reason = "FN: Pattern too weak" if case['label'] == 1 else "FP: High suspicious noise"
        if "label_noise" in case['scenario']:
            reason = "Label noise (Flipped)"
        elif "normal_new_user" in case['scenario']:
            reason = "FP: New user penalty"
            
        print(f"{case['scenario'][:25]:<25} | {int(case['label']):<3} | {int(case['pred_with']):<4} | "
              f"{case['ml_score']:.2f} | {case['rule_score']:.2f} | {case['graph_score']:.2f} | {reason}")

    # 5. FINAL OUTPUT SUMMARY
    print("\n" + "="*65)
    print("   FINAL OUTPUT SUMMARY")
    print("="*65)
    
    stable = m_with['precision'] >= 0.85
    recall_ok = m_with['recall'] >= 0.60
    
    print(f"* Is model stable under noise?   {'YES' if stable and m_with['accuracy'] > 0.8 else 'NO'}")
    print(f"* Is precision high (>=85%)?     {'YES' if stable else 'NO'} ({m_with['precision']*100:.1f}%)")
    print(f"* Is recall acceptable (>=60%)?  {'YES' if recall_ok else 'NO'} ({m_with['recall']*100:.1f}%)")
    
    fail_areas = []
    if m_with['recall'] < 0.7: fail_areas.append("Stealth/Partial Fraud Detection")
    if m_with['fp'] > 100: fail_areas.append("Noisy Normal False Positives")
    if not fail_areas: fail_areas = ["None (System is robust)"]
    
    print(f"* Primary failure areas:         {', '.join(fail_areas)}")
    
    print(f"\nTotal Validation Time: {time.time() - start_time:.2f}s")
    print("="*65 + "\n")

if __name__ == "__main__":
    run_noisy_validation()
