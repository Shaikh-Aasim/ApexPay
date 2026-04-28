from typing import Dict, Any, List
from utils.graph_engine import GraphEngine
from utils.graph_score import calculate_graph_score

def combine_scores(ml_score: float, rule_score: float, graph_score: float) -> float:
    """
    Combines ML, Rules, and Graph scores using weighted averaging.
    PRODUCTION WEIGHTS: 0.6 * ML + 0.25 * Rules + 0.15 * Graph
    
    IMPROVED (ADAPTIVE):
    - If ML is low (<0.3), graph weight increases slightly (0.6 ML, 0.2 Rules, 0.2 Graph)
    - If ML is high (>0.7), graph weight stays low (0.15) to avoid over-trigger.
    """
    if ml_score < 0.3:
        # Increase graph weight slightly when ML is uncertain/low
        final_score = (0.6 * ml_score) + (0.2 * rule_score) + (0.2 * graph_score)
    else:
        # Standard weights
        final_score = (0.6 * ml_score) + (0.25 * rule_score) + (0.15 * graph_score)
        
    return round(float(final_score), 4)

def get_final_decision(final_score: float, rule_decision: str, 
                       graph_score: float, ml_score: float, 
                       signals_count: int, stability: float) -> str:
    """
    Implements decision logic (PRODUCTION READY):
    - LOW: Normal activity
    - MEDIUM: HOLD (OTP verification)
    - HIGH: BLOCK
    
    IMPROVED:
    - Balanced for Precision (>=85%) and Recall (>=50%)
    - Uses stability to filter out noisy business hubs
    """
    # 1. GRAPH + WEAK SIGNAL COMBINATION (INCREASE RECALL)
    # If graph_score >= 0.3 AND at least 1 other signal exists -> upgrade to MEDIUM
    # Note: signals_count includes graph_risk if graph_score >= 0.35, 
    # so signals_count >= 2 means graph + 1 other signal.
    is_weak_graph_combo = graph_score >= 0.3 and signals_count >= 2
    is_stealth_combo = graph_score >= 0.4 and signals_count >= 2 and stability < 0.4
    is_strong_graph_combo = graph_score >= 0.6 and signals_count >= 2
    
    # 2. Base decision from final score
    if final_score < 0.42:
        decision = "LOW"
    elif final_score < 0.78:
        decision = "MEDIUM"
    else:
        decision = "HIGH"

    # 3. Rule 'HIGH' override
    if rule_decision == "HIGH":
        return "HIGH"

    # 4. Graph-driven upgrades (CONTROLLED RECALL)
    if graph_score >= 0.85 and signals_count >= 3:
        decision = "HIGH"
    elif (is_weak_graph_combo or is_stealth_combo or is_strong_graph_combo) and decision == "LOW":
        decision = "MEDIUM"

    # 5. ML Confidence Gating (Safety)
    if ml_score < 0.1 and decision != "HIGH":
        # If ML is confident it's normal, only allow MEDIUM if graph is very strong or stability is very low
        if decision == "MEDIUM" and graph_score < 0.55 and stability > 0.2:
            decision = "LOW"
            
    # 6. MULTI-SIGNAL FILTER (Precision Focus)
    if signals_count < 2 and ml_score < 0.8 and rule_decision != "HIGH":
        if decision == "HIGH":
            decision = "MEDIUM"
        elif decision == "MEDIUM" and graph_score < 0.65:
            decision = "LOW"
            
    return decision

def integrate_graph_intelligence(data: Dict[str, Any], ml_score: float, 
                                 rule_res: Any, engine: GraphEngine) -> Dict[str, Any]:
    """
    Orchestrates the integration of graph intelligence with existing scores.
    Implements multi-signal confirmation, adaptive weighting, and improved recall logic.
    """
    sender_id = data.get("sender_id", "unknown_sender")
    receiver_id = data.get("receiver_id", "unknown_receiver")
    stability = float(data.get("relationship_stability_score", data.get("relationship_stability", 0.5)))
    is_first = bool(data.get("is_first_transaction", False))
    age_hours = float(data.get("account_age_hours", 0.0))
    
    # Calculate graph-based score for both nodes
    g_res_sender = calculate_graph_score(sender_id, stability, engine, is_first, age_hours)
    g_res_receiver = calculate_graph_score(receiver_id, stability, engine, is_first, age_hours)
    
    # Take the riskier side
    g_res = g_res_sender if g_res_sender["graph_score"] >= g_res_receiver["graph_score"] else g_res_receiver
    graph_score = g_res["graph_score"]

    # MULTI-SIGNAL CONFIRMATION logic (Refined for precision)
    signals = []
    # Relaxed zscore slightly to capture stealth fraud (from 2.0 to 1.5)
    if abs(float(data.get("amount_zscore", 0))) >= 1.5: signals.append("high_zscore")
    if int(data.get("device_change", 0)) == 1: signals.append("device_change")
    if graph_score >= 0.35: signals.append("graph_risk") # Slightly more sensitive
    if int(data.get("txn_count_24h", 0)) >= 5: signals.append("velocity_flag")
    if int(data.get("location_anomaly", 0)) == 1: signals.append("location_anomaly")
    
    signals_count = len(signals)

    # Combine everything using ADAPTIVE weighting
    final_score = combine_scores(ml_score, rule_res.risk_score, graph_score)
    
    # Final decision
    decision = get_final_decision(final_score, rule_res.decision, graph_score, ml_score, signals_count, stability)
    
    # Debug Support (Internal)
    debug_support = {
        "signals_count": signals_count,
        "triggered_signals": signals,
        "ml_confidence": round(ml_score, 4),
        "graph_score_raw": g_res["graph_score"],
        "graph_risk_level": g_res["risk_level"],
        "graph_components": g_res["components"],
        "graph_flags": g_res.get("debug_info", {}).get("mule_flags", []) + g_res.get("debug_info", {}).get("ring_flags", []),
        "decision_reason": f"Final score {final_score} with {signals_count} signals"
    }
    
    return {
        "risk_score": final_score,
        "decision": decision,
        "reasons": list(set(rule_res.reasons + g_res["reasons"])),
        "graph_score": round(graph_score, 4),
        "graph_risk_level": g_res["risk_level"],
        "graph_features": g_res["features"],
        "graph_debug": g_res.get("debug_info", {}),
        "debug_support": debug_support
    }
