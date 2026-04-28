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
    # Always regenerate for fresh test
    generate_noisy_test_data(7000, data_path)
    
    df = pd.read_csv(data_path)
    predictor = RiskPredictor()
    
    results_wo_graph = []
    results_with_graph = []
    detailed_data = []
    
    print(f"Processing {len(df)} noisy samples...")
    print("(Note: Using Heuristic + Graph as ML model is not loaded in this environment)")
    start_time = time.time()
    
    # Pre-warm graph to simulate history (optional but realistic)
    for i in range(min(500, len(df))):
        row = df.iloc[i]
        predictor.graph_engine.add_transaction(row['sender_id'], row['receiver_id'], row['amount'])

    # Efficient processing loop
    for idx, row in df.iterrows():
        data = row.to_dict()
        
        # 1. RUN WITH GRAPH (Production Mode)
        res_with = predictor.predict(data)
        
        # 2. RUN WITHOUT GRAPH (Simulated Mode)
        # Weight Mode A: final_score = 0.7 ML + 0.3 Rule
        ml_s = res_with["ml_score"]
        rule_s = res_with["rule_score"]
        score_wo = (0.7 * ml_s) + (0.3 * rule_s)
        
        # Simple decision for WO mode
        if score_wo < 0.35: decision_wo = "LOW"
        elif score_wo < 0.70: decision_wo = "MEDIUM"
        else: decision_wo = "HIGH"
        
        pred_wo = 1 if decision_wo in ["HIGH", "MEDIUM"] else 0
        pred_with = 1 if res_with["decision"] in ["HIGH", "MEDIUM"] else 0
        
        results_wo_graph.append(pred_wo)
        results_with_graph.append(pred_with)
        
        detailed_data.append({
            "scenario": row["scenario"],
            "label": row["label"],
            "ml_score": ml_s,
            "rule_score": rule_s,
            "graph_score": res_with["graph_score"],
            "final_score": res_with["risk_score"],
            "signals_count": res_with.get("debug_support", {}).get("signals_count", 0),
            "decision_reason": res_with.get("debug_support", {}).get("decision_reason", "N/A"),
            "pred_with": pred_with,
            "decision": res_with["decision"]
        })

    total_time = time.time() - start_time
    m_wo = calculate_metrics(df["label"], results_wo_graph)
    m_with = calculate_metrics(df["label"], results_with_graph)

    # 3. PRINT CORE METRICS
    print("\n==============================")
    print("OVERALL METRICS (WITH GRAPH)")
    print("===============")
    print(f"Accuracy:        {m_with['accuracy']*100:.2f}%")
    print(f"Precision:       {m_with['precision']*100:.2f}%")
    print(f"Recall:          {m_with['recall']*100:.2f}%")
    print(f"F1 Score:        {m_with['f1']*100:.2f}%")
    print(f"False Positives: {m_with['fp']}")
    print(f"False Negatives: {m_with['fn']}")

    # 4. PRINT COMPARISON
    print("\n==============================")
    print("WITH vs WITHOUT GRAPH")
    print("=====================")
    print(f"Recall Improvement: { (m_with['recall'] - m_wo['recall'])*100:+.2f}%")
    print(f"Precision Change:   { (m_with['precision'] - m_wo['precision'])*100:+.2f}%")
    print(f"FP Change:          { (m_with['fp'] - m_wo['fp']):+d}")
    print(f"FN Reduction:       { (m_wo['fn'] - m_with['fn']):+d}")

    # 5. SCENARIO PERFORMANCE
    print("\n==============================")
    print("SCENARIO BREAKDOWN")
    print("==================")
    rdf = pd.DataFrame(detailed_data)
    
    scenarios = {
        "Normal Cases": rdf[rdf['scenario'].str.contains('normal_standard')],
        "Fraud Cases": rdf[rdf['label'] == 1],
        "Noisy Normal": rdf[rdf['scenario'].str.contains('noisy_normal')],
        "Stealth Fraud": rdf[rdf['scenario'].str.contains('fraud_stealth')]
    }
    
    for name, group in scenarios.items():
        if len(group) > 0:
            acc = (group['label'] == group['pred_with']).mean()
            print(f"{name:<15}: {acc*100:>6.2f}% (n={len(group)})")

    # 6. CRITICAL CHECKS
    print("\n==============================")
    print("CRITICAL CHECKS")
    print("===============")
    print(f"* Is precision >= 80% ?      {'PASS' if m_with['precision'] >= 0.8 else 'FAIL'} ({m_with['precision']*100:.1f}%)")
    print(f"* Is recall >= 50% ?         {'PASS' if m_with['recall'] >= 0.5 else 'FAIL'} ({m_with['recall']*100:.1f}%)")
    fpr = m_with['fp'] / (m_with['fp'] + m_with['tn']) if (m_with['fp'] + m_with['tn']) > 0 else 0
    print(f"* Is FP rate acceptable?     {'YES' if fpr < 0.05 else 'NO'} ({fpr*100:.2f}%)")

    # 7. DEBUG SAMPLE OUTPUT (10 cases)
    print("\n==============================")
    print("DEBUG SAMPLE OUTPUT (10 CASES)")
    print("===============")
    samples = rdf.sample(10)
    for _, s in samples.iterrows():
        print(f"Scenario: {s['scenario']:<25} | Label: {s['label']} | Pred: {int(s['pred_with'])} | "
              f"ML: {s['ml_score']:.2f} | Rule: {s['rule_score']:.2f} | Graph: {s['graph_score']:.2f} | "
              f"Final: {s['final_score']:.2f} | Signals: {s['signals_count']} | Reason: {s['decision_reason']}")

    # 8. HARD CASE ANALYSIS (10 misclassified)
    print("\n==============================")
    print("HARD CASE ANALYSIS (10 MISCLASSIFIED)")
    print("===============")
    misclassified = rdf[rdf['label'] != rdf['pred_with']].sample(min(10, len(rdf[rdf['label'] != rdf['pred_with']])))
    for _, m in misclassified.iterrows():
        err_type = "FP" if m['label'] == 0 else "FN"
        reason = "Weak signals" if m['signals_count'] < 2 else "Graph suppressed" if m['graph_score'] < 0.3 else "Label noise" if "label_noise" in m['scenario'] else "Ambiguous"
        print(f"Type: {err_type:<3} | Scenario: {m['scenario']:<25} | Reason: {reason:<15} | Score: {m['final_score']:.2f}")

    # 9. FINAL SUMMARY
    print("\n==============================")
    print("FINAL SYSTEM EVALUATION")
    print("=======================")
    stability = "GOOD" if m_with['accuracy'] > 0.85 and abs(m_with['precision'] - m_wo['precision']) < 0.1 else "NEEDS IMPROVEMENT"
    print(f"* Model Stability: {stability}")
    print(f"* Precision Status: {'OK' if m_with['precision'] >= 0.8 else 'LOW'}")
    print(f"* Recall Status:    {'OK' if m_with['recall'] >= 0.5 else 'LOW'}")
    
    rec = "System is robust." if stability == "GOOD" else "Refine thresholds for stealth fraud."
    print(f"* Recommendation:  {rec}")
    
    print(f"\nExecution Time: {total_time:.2f}s")
    print("="*65 + "\n")

if __name__ == "__main__":
    run_noisy_validation()
