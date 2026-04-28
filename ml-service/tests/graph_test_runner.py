import pandas as pd
import numpy as np
import time
import sys
from pathlib import Path
from typing import Dict, Any, List

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from api.predict import RiskPredictor
from tests.graph_test_data import generate_graph_test_data

def calculate_metrics(y_true, y_pred):
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "fp": fp,
        "fn": fn,
        "tp": tp,
        "tn": tn
    }

def run_validation(mode="MINI"):
    """
    Main testing pipeline for Graph Intelligence.
    """
    print("\n" + "="*60)
    print(f"   GRAPH INTELLIGENCE VALIDATION PIPELINE - {mode} MODE")
    print("="*60)
    
    start_time = time.time()
    
    # 1. DATA PREPARATION
    data_path = f"graph_test_data_{mode.lower()}.csv"
    if not Path(data_path).exists():
        generate_graph_test_data(mode, data_path)
    
    df = pd.read_csv(data_path)
    predictor = RiskPredictor()
    predictor.graph_engine.reset()
    
    print(f"Dataset: {len(df)} samples")
    
    # 2. EVALUATION LOOP
    results_with = []
    results_without = []
    debug_samples = []
    
    for i, (_, row) in enumerate(df.iterrows()):
        data = row.to_dict()
        
        # System Prediction (WITH GRAPH)
        res = predictor.predict(data)
        
        # Update graph engine with actual result (for neighbor risk)
        predictor.graph_engine.update_user_risk(
            user_id=data["sender_id"],
            risk_score=res["risk_score"],
            is_flagged=(res["decision"] == "HIGH")
        )
        
        # WITHOUT GRAPH Calculation (0.7 * ML + 0.3 * Rules)
        ml_score = res.get("ml_score", 0.0)
        rule_score = res.get("rule_score", 0.0)
        final_wo = (0.7 * ml_score) + (0.3 * rule_score)
        
        # Decision for WITHOUT GRAPH
        decision_wo = "LOW"
        if final_wo >= 0.65: decision_wo = "HIGH"
        elif final_wo >= 0.35: decision_wo = "MEDIUM"
        
        results_with.append({
            "pred": 1 if res["decision"] == "HIGH" else 0,
            "score": res["risk_score"],
            "graph_score": res.get("graph_score", 0.0),
            "label": data["label"],
            "scenario": data["scenario"],
            "res": res,
            "final_wo": final_wo,
            "decision_wo": decision_wo
        })
        
        results_without.append({
            "pred": 1 if decision_wo == "HIGH" else 0,
            "score": final_wo,
            "label": data["label"],
            "scenario": data["scenario"]
        })
        
        # Capture 10 debug samples
        if len(debug_samples) < 10:
            debug_samples.append({
                "ml": ml_score,
                "rule": rule_score,
                "graph": res.get("graph_score", 0.0),
                "final_with": res["risk_score"],
                "final_wo": final_wo,
                "dec_with": res["decision"],
                "dec_wo": decision_wo,
                "scenario": data["scenario"]
            })

    # 3. METRICS
    m_with = calculate_metrics([r["label"] for r in results_with], [r["pred"] for r in results_with])
    m_wo = calculate_metrics([r["label"] for r in results_without], [r["pred"] for r in results_without])
    
    print("\n" + "-"*60)
    print(f"{'Metric':<15} | {'Without Graph':<15} | {'With Graph':<15}")
    print("-"*60)
    for k in ["precision", "recall", "f1"]:
        print(f"{k.capitalize():<15} | {m_wo[k]:>15.2%} | {m_with[k]:>15.2%}")
    for k in ["fp", "fn"]:
        print(f"{k.upper():<15} | {m_wo[k]:>15} | {m_with[k]:>15}")

    # 4. SCENARIO PERFORMANCE TABLE
    print("\n" + "-"*60)
    print(f"{'Scenario':<20} | {'Without Graph':<15} | {'With Graph':<15} | {'Improve'}")
    print("-"*60)
    
    scenarios = df["scenario"].unique()
    scenario_mapping = {
        "graph_mule": "Mule Detection",
        "graph_ring": "Ring Detection",
        "graph_hub": "Hub Detection",
        "salary": "Normal Safety",
        "monthly_repayment": "Normal Safety",
        "family_transfer": "Normal Safety",
        "trusted_transfer": "Normal Safety"
    }
    
    scenario_stats = {}
    for s in scenarios:
        display_name = scenario_mapping.get(s, s)
        if display_name not in scenario_stats:
            scenario_stats[display_name] = {"wo": [], "with": []}
            
        s_with = [r for r in results_with if r["scenario"] == s]
        s_wo = [r for r in results_without if r["scenario"] == s]
        
        # For Normal Safety, we measure 1 - FP_rate
        if "Normal" in display_name:
            rec_with = 1 - (sum(r["pred"] for r in s_with) / len(s_with))
            rec_wo = 1 - (sum(r["pred"] for r in s_wo) / len(s_wo))
        else:
            rec_with = sum(r["pred"] for r in s_with) / len(s_with)
            rec_wo = sum(r["pred"] for r in s_wo) / len(s_wo)
            
        scenario_stats[display_name]["wo"].append(rec_wo)
        scenario_stats[display_name]["with"].append(rec_with)

    for name, stats in scenario_stats.items():
        avg_wo = np.mean(stats["wo"])
        avg_with = np.mean(stats["with"])
        diff = avg_with - avg_wo
        print(f"{name:<20} | {avg_wo:>15.1%} | {avg_with:>15.1%} | {diff:>+7.1%}")

    # 5. GRAPH IMPACT ANALYSIS
    print("\n" + "="*60)
    print("   GRAPH IMPACT ANALYSIS")
    print("="*60)
    print(f"* Recall improvement:   {m_with['recall'] - m_wo['recall']:>+7.2%}")
    print(f"* Precision change:     {m_with['precision'] - m_wo['precision']:>+7.2%}")
    print(f"* FP increase/decrease: {m_with['fp'] - m_wo['fp']:>+7}")
    print(f"* FN decrease:          {m_wo['fn'] - m_with['fn']:>+7}")

    # 6. DEBUG SAMPLE
    print("\n" + "="*60)
    print("   DEBUG SAMPLE (10 TRANSACTIONS)")
    print("="*60)
    print(f"{'Scenario':<20} | {'ML':<4} | {'Rule':<4} | {'Graph':<5} | {'F-WO':<5} | {'F-WITH':<6} | {'Decision'}")
    print("-"*60)
    for s in debug_samples:
        print(f"{s['scenario'][:20]:<20} | {s['ml']:.2f} | {s['rule']:.2f} | {s['graph']:<5.2f} | {s['final_wo']:.2f} | {s['final_with']:<6.2f} | {s['dec_with']}")

    # 7. GRAPH VALIDATION TESTS
    print("\n" + "="*60)
    print("   GRAPH VALIDATION TESTS")
    print("="*60)
    
    def run_micro_test(name, transactions, target_user, expected_decision, stability=0.5):
        predictor.graph_engine.reset()
        for s, r, a in transactions:
            predictor.graph_engine.add_transaction(s, r, a)
        
        # Use a dummy transaction to check target user risk
        res = predictor.predict({
            "sender_id": target_user, 
            "receiver_id": "dummy", 
            "amount": 100,
            "relationship_stability_score": stability
        })
        passed = res["decision"] == expected_decision
        print(f"* {name:<30}: {'PASS' if passed else 'FAIL'} (Got: {res['decision']}, Exp: {expected_decision})")
        return passed

    # Small cycle (3 users) -> LOW
    run_micro_test("Small cycle (3 users)", 
                   [("A", "B", 100), ("B", "C", 100), ("C", "A", 100)], "C", "LOW", stability=0.8)
    
    # Large cycle (7 users) -> HIGH
    run_micro_test("Large cycle (7 users)", 
                   [(f"U{i}", f"U{i+1}", 1000) for i in range(7)] + [("U7", "U0", 1000)], "U7", "HIGH", stability=0.2)
    
    # Mule pattern (12 senders) -> HIGH
    run_micro_test("Mule pattern (12 senders)", 
                   [(f"S{i}", "RCV", 1500) for i in range(12)], "RCV", "HIGH", stability=0.1)

    # 8. OUTPUT SUMMARY
    print("\n" + "="*60)
    print("   FINAL CONCLUSION")
    print("="*60)
    recall_improved = m_with['recall'] > m_wo['recall']
    fp_controlled = (m_with['fp'] - m_wo['fp']) < (len(df) * 0.05)
    
    print(f"* Did graph improve recall?      {'YES' if recall_improved else 'NO'}")
    print(f"* Did FP increase significantly? {'NO' if fp_controlled else 'YES'}")
    print(f"* Is system balanced?            {'YES' if recall_improved and fp_controlled else 'NO'}")
    
    print(f"\nTotal Execution Time: {time.time() - start_time:.2f}s")
    print("="*60 + "\n")

if __name__ == "__main__":
    import sys
    mode = "MINI"
    if len(sys.argv) > 1:
        mode = sys.argv[1].upper()
    run_validation(mode)
