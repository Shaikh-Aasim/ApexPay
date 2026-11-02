from typing import Dict, Any, List
from utils.graph_engine import GraphEngine
from utils.graph_score import calculate_graph_score

def combine_scores(ml_score: float, rule_score: float, graph_score: float) -> float:
    """
    Combines ML, Rules, and Graph scores using adaptive weighted averaging.
    Output is strictly clamped in [0.0, 1.0].
    
    ADAPTIVE WEIGHTING:
    - If ML is uncertain (< 0.25): Rules and Graph provide foundation (0.45 ML, 0.30 Rules, 0.25 Graph).
    - If ML is very confident (> 0.75): ML weight increases (0.65 ML, 0.20 Rules, 0.15 Graph).
    - Standard balanced weights: (0.55 ML, 0.25 Rules, 0.20 Graph).
    """
    if ml_score < 0.25:
        final_score = (0.45 * ml_score) + (0.30 * rule_score) + (0.25 * graph_score)
    elif ml_score > 0.75:
        final_score = (0.65 * ml_score) + (0.20 * rule_score) + (0.15 * graph_score)
    else:
        final_score = (0.55 * ml_score) + (0.25 * rule_score) + (0.20 * graph_score)
        
    return round(float(max(0.0, min(1.0, final_score))), 4)

def get_final_decision(final_score: float, rule_decision: str, 
                       graph_score: float, ml_score: float, 
                       signals_count: int, stability: float) -> str:
    """
    Implements production-grade 3-tier decision logic:
    - LOW: Normal activity, approved immediately [0.0, 0.42)
    - MEDIUM: HOLD for OTP / Step-Up Authentication [0.42, 0.75)
    - HIGH: BLOCK / Reject [0.75, 1.0]
    
    Balances high recall for real threats with high precision for legitimate users.
    """
    # 1. Base decision from final score
    if final_score < 0.42:
        decision = "LOW"
    elif final_score < 0.75:
        decision = "MEDIUM"
    else:
        decision = "HIGH"

    # 2. Rule 'HIGH' override takes absolute priority
    if rule_decision == "HIGH":
        return "HIGH"

    # 3. Rule 'MEDIUM' override (Step-Up Safeguard)
    if rule_decision == "MEDIUM":
        if stability > 0.85 and ml_score < 0.20 and graph_score < 0.30:
            decision = "LOW"
        else:
            decision = "MEDIUM"

    # 4. Graph-driven upgrades
    if graph_score >= 0.85:
        return "HIGH"
    elif graph_score >= 0.70 and signals_count >= 1:
        decision = "HIGH"
    elif (graph_score >= 0.40 and signals_count >= 1 and stability < 0.4) and decision == "LOW":
        decision = "MEDIUM"
    elif graph_score >= 0.55 and decision == "LOW":
        decision = "MEDIUM"

    # 5. ML Confidence Gating
    if ml_score >= 0.75 and decision == "LOW":
        decision = "MEDIUM"
    if ml_score >= 0.88 and signals_count >= 1:
        decision = "HIGH"

    # 6. Multi-Signal Confirmation & False Positive Filtering (Precision Protection)
    if stability > 0.75 and rule_decision == "LOW":
        if decision == "HIGH" and ml_score < 0.85:
            decision = "MEDIUM"
        elif decision == "MEDIUM" and ml_score < 0.45 and graph_score < 0.50:
            decision = "LOW"

    if signals_count < 2 and ml_score < 0.80 and rule_decision == "LOW" and graph_score < 0.85:
        if decision == "HIGH":
            decision = "MEDIUM"
        elif decision == "MEDIUM" and graph_score < 0.50 and stability > 0.4:
            decision = "LOW"

    return decision

def integrate_graph_intelligence(data: Dict[str, Any], ml_score: float, 
                                 rule_res: Any, engine: GraphEngine) -> Dict[str, Any]:
    """
    Orchestrates the integration of graph intelligence with ML and heuristic scores.
    Separates sender and receiver context so sender attributes (e.g., first txn,
    account age) are never improperly applied to the receiver.
    Implements multi-signal confirmation, adaptive weighting, and balanced decision gating.
    """
    sender_id = str(data.get("sender_id", ""))
    receiver_id = str(data.get("receiver_id", ""))
    stability = float(data.get("relationship_stability_score", data.get("relationship_stability", 0.0)))
    
    # Decoupled Sender Context
    sender_is_first = bool(data.get("is_first_transaction", data.get("sender_is_first_transaction", False)))
    sender_age_hours = float(data.get("account_age_hours", data.get("sender_account_age_hours", 720.0)))
    
    # Decoupled Receiver Context
    receiver_is_first = bool(data.get("receiver_is_first_transaction", False))
    # RiskRequest intentionally models receiver context as Optional because the
    # caller may not have receiver-history data. dict.get(key, default) does not
    # apply the default when the key exists with value None (as model_dump does).
    # Use the neutral cold-start fallback in that case instead of float(None).
    receiver_age_value = data.get("receiver_account_age_hours")
    receiver_age_hours = float(720.0 if receiver_age_value is None else receiver_age_value)
    
    # Calculate graph-based score for both nodes independently
    g_res_sender = calculate_graph_score(sender_id, stability, engine, sender_is_first, sender_age_hours)
    g_res_receiver = calculate_graph_score(receiver_id, stability, engine, receiver_is_first, receiver_age_hours)
    
    # Select higher risk profile between the counterparties
    if g_res_sender["graph_score"] >= g_res_receiver["graph_score"]:
        g_res = g_res_sender
        primary_graph_node = "sender"
    else:
        g_res = g_res_receiver
        primary_graph_node = "receiver"
        
    graph_score = g_res["graph_score"]

    # MULTI-SIGNAL CONFIRMATION logic
    signals = []
    if abs(float(data.get("amount_zscore", 0))) >= 1.5: signals.append("high_zscore")
    if int(data.get("device_change", 0)) == 1: signals.append("device_change")
    if int(data.get("location_anomaly", 0)) == 1: signals.append("location_anomaly")
    if int(data.get("txn_count_24h", 0)) >= 5: signals.append("velocity_flag")
    if int(data.get("receiver_flagged", 0)) == 1 or float(data.get("receiver_suspicion_score", 0)) >= 0.7: signals.append("receiver_risk")
    if graph_score >= 0.35: signals.append("graph_risk")
    if sender_is_first and float(data.get("amount", 0)) >= 10000: signals.append("first_txn_elevated")
    
    signals_count = len(signals)

    # Combine everything using ADAPTIVE weighting
    final_score = combine_scores(ml_score, rule_res.risk_score, graph_score)
    
    # Final decision
    decision = get_final_decision(final_score, rule_res.decision, graph_score, ml_score, signals_count, stability)
    
    # Harmonize final risk score with authoritative decision band
    if decision == "HIGH":
        final_score = max(final_score, rule_res.risk_score, 0.85)
    elif decision == "MEDIUM":
        final_score = max(0.48, min(0.74, max(final_score, rule_res.risk_score)))
    else:  # LOW
        final_score = min(final_score, 0.38)

    final_score = round(float(max(0.0, min(1.0, final_score))), 4)

    # Internal Debug Support
    debug_support = {
        "signals_count": signals_count,
        "triggered_signals": signals,
        "ml_confidence": round(ml_score, 4),
        "rule_confidence": round(rule_res.risk_score, 4),
        "sender_graph_score": g_res_sender["graph_score"],
        "receiver_graph_score": g_res_receiver["graph_score"],
        "primary_graph_node": primary_graph_node,
        "graph_score_raw": g_res["graph_score"],
        "graph_risk_level": g_res["risk_level"],
        "graph_components": g_res["components"],
        "graph_flags": g_res.get("debug_info", {}).get("mule_flags", []) + g_res.get("debug_info", {}).get("ring_flags", []),
        "decision_reason": f"Final score {final_score:.4f} with {signals_count} confirmed signals"
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
