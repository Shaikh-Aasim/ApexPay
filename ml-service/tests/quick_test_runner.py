import pandas as pd
import numpy as np
import time
import sys
from pathlib import Path
from typing import Dict, Any

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from api.predict import RiskPredictor
from tests.mini_test_data_generator import generate_mini_dataset

def run_quick_evaluation():
    """
    Fast testing pipeline for Graph Intelligence validation.
    Compares WITH vs WITHOUT graph signals.
    """
    start_time = time.time()
    
    # 1. DATA PREPARATION
    data_path = "test_data_mini.csv"
    if not Path(data_path).exists():
        generate_mini_dataset(data_path, n_samples=1000)
    
    df = pd.read_csv(data_path)
    predictor = RiskPredictor()
    
    print("\n" + "="*50)
    print("   FAST GRAPH VALIDATION PIPELINE")
    print("="*50)
    print(f"Dataset: {len(df)} samples (40% Fraud)")
    
    # 2. EVALUATION LOOP
    results_with = []
    results_without = []
    debug_cases = []
    
    predictor.graph_engine.reset()
    
    for i, (_, row) in enumerate(df.iterrows()):
        data = row.to_dict()
        
        # Standard Update & Predict (WITH GRAPH)
        predictor.update_graph(
            sender_id=data["sender_id"],
            receiver_id=data["receiver_id"],
            amount=float(data["amount"])
        )
        res_with = predictor.predict(data)
        
        # Update graph engine with actual result for neighbor risk
        predictor.graph_engine.update_user_risk(
            user_id=data["sender_id"],
            risk_score=res_with["risk_score"],
            is_flagged=(res_with["decision"] == "HIGH")
        )
        
        # For comparison, we'll manually re-run the integration logic
        # To get the internal scores, we'll look at the integration results
        # We need to expose them or replicate them.
        # Let's replicate the heuristic risk for comparison
        from utils.risk_rules import heuristic_risk
        h_res = heuristic_risk(
            amount=float(data.get("amount", 0)),
            amount_zscore=float(data.get("amount_zscore", 0)),
            device_change=int(data.get("device_change", 0)),
            location_anomaly=int(data.get("location_anomaly", 0)),
            txn_count_24h=int(data.get("txn_count_24h", 1)),
            receiver_suspicion_score=float(data.get("receiver_suspicion_score", 0)),
            receiver_flagged=int(data.get("receiver_flagged", 0))
        )
        
        # Approximate ML score (since we don't have it easily without running model)
        # We'll assume ml_score = 0.0 for this simple validator unless we want to load model
        ml_score = 0.0
        if predictor.model:
            from utils.features import get_feature_vector
            X = np.array([get_feature_vector(data)])
            ml_score = float(predictor.model.predict_proba(X)[0][1])
            
        g_score = res_with.get("graph_score", 0)
        
        # WITHOUT GRAPH: Use 0.75/0.25 weighting to normalize to 1.0
        final_wo = (ml_score * 0.75) + (h_res.risk_score * 0.25)
        decision_wo = "LOW"
        if h_res.decision == "HIGH": decision_wo = "HIGH"
        elif final_wo >= 0.65: decision_wo = "HIGH"
        elif final_wo >= 0.35: decision_wo = "MEDIUM"
        
        results_with.append({
            "pred": 1 if res_with["decision"] == "HIGH" else 0,
            "score": res_with["risk_score"],
            "graph": g_score,
            "scenario": data["scenario"],
            "label": data["label"]
        })
        
        results_without.append({
            "pred": 1 if decision_wo == "HIGH" else 0,
            "score": final_wo,
            "scenario": data["scenario"],
            "label": data["label"]
        })
        
        # Capture debug cases (first few of each scenario)
        if data["scenario"] not in [c["scenario"] for c in debug_cases] or len([c for c in debug_cases if c["scenario"] == data["scenario"]]) < 2:
            debug_cases.append({
                "ml": round(ml_score, 2),
                "rule": round(h_res.risk_score, 2),
                "graph": round(g_score, 2),
                "final": round(res_with["risk_score"], 2),
                "dec": res_with["decision"],
                "scenario": data["scenario"],
                "g_feat": res_with.get("graph_features", {})
            })

    # 3. METRICS CALCULATION
    def get_metrics(results):
        y_true = [r["label"] for r in results]
        y_pred = [r["pred"] for r in results]
        
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
        tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        return precision, recall, fp, fn

    p_with, r_with, fp_with, fn_with = get_metrics(results_with)
    p_wo, r_wo, fp_wo, fn_wo = get_metrics(results_without)

    # 4. SCENARIO ANALYSIS
    scenarios = df["scenario"].unique()
    print("\n" + "-"*50)
    print(f"{'Scenario':<25} | {'WO Graph':<10} | {'WITH Graph':<10} | {'Improve'}")
    print("-"*50)
    
    for s in scenarios:
        if "normal" in s or "family" in s or "trusted" in s: continue # Focus on fraud detection
        
        s_with = [r for r in results_with if r["scenario"] == s]
        s_wo = [r for r in results_without if r["scenario"] == s]
        
        rec_with = sum(r["pred"] for r in s_with) / len(s_with)
        rec_wo = sum(r["pred"] for r in s_wo) / len(s_wo)
        
        improvement = rec_with - rec_wo
        print(f"{s:<25} | {rec_wo:>8.1%} | {rec_with:>9.1%} | {improvement:>+7.1%}")

    # 5. GRAPH IMPACT SUMMARY
    print("\n" + "="*50)
    print("   GRAPH IMPACT ANALYSIS")
    print("="*50)
    print(f"Recall Improvement:   {r_wo:.1%} -> {r_with:.1%} ({r_with - r_wo:>+5.1%})")
    print(f"FP Change:            {fp_wo} -> {fp_with} ({fp_with - fp_wo:>+2})")
    print(f"FN Change:            {fn_wo} -> {fn_with} ({fn_with - fn_wo:>+2})")
    print(f"Precision:            {p_with:.1%}")

    # 6. DEBUG OUTPUT (5-10 cases)
    print("\n" + "="*50)
    print("   DEBUG: SCORE VERIFICATION")
    print("="*50)
    print(f"{'Scenario':<20} | {'ML':<4} | {'Rule':<4} | {'Graph':<4} | {'Final':<5} | {'Decision'} | {'G-Feat'}")
    for dc in debug_cases:
        feat = dc.get("g_feat", {})
        feat_str = f"In:{feat.get('in_degree',0)} Out:{feat.get('out_degree',0)} B:{feat.get('burst_count_24h',0)}"
        print(f"{dc['scenario'][:20]:<20} | {dc['ml']:<4.2f} | {dc['rule']:<4.2f} | {dc['graph']:<4.2f} | {dc['final']:<5.2f} | {dc['dec']:<8} | {feat_str}")

    # 7. STRESS MICRO TESTS
    print("\n" + "="*50)
    print("   GRAPH STRESS MICRO TESTS")
    print("="*50)
    
    def micro_test(name, transactions, target_user, expected_decision):
        predictor.graph_engine.reset()
        final_dec = "LOW"
        for s, r, a in transactions:
            predictor.update_graph(s, r, a)
            # Evaluate the target user, not necessarily the sender
            res = predictor.predict({"sender_id": target_user, "receiver_id": "dummy", "amount": 0})
            final_dec = res["decision"]
        
        status = "PASSED" if final_dec == expected_decision else "FAILED"
        print(f"{name:<35}: {status} (Got: {final_dec}, Exp: {expected_decision})")

    # Small Cycle (3 users) - Should NOT be fraud
    micro_test("Small Cycle (3 users)", 
               [("A", "B", 100), ("B", "C", 100), ("C", "A", 100)], "C", "LOW")
    
    # Large Cycle (7 users) - SHOULD be fraud
    # Note: Max depth in implementation is currently 5, so this might still fail 
    # unless we tune it.
    micro_test("Large Cycle (7 users)", 
               [(f"U{i}", f"U{i+1}", 1000) for i in range(6)] + [("U6", "U0", 1000)], "U6", "HIGH")
    
    # Many-to-One (12 users) - Mule detection
    micro_test("Mule (12-to-1)", 
               [(f"S{i}", "TARGET", 1200) for i in range(12)], "TARGET", "HIGH")

    end_time = time.time()
    print(f"\nExecution Time: {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    run_quick_evaluation()
