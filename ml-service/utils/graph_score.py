from typing import Dict, Any, List
from .graph_engine import GraphEngine
from .graph_features import compute_graph_features
from .graph_rules import get_graph_rules_risk

def calculate_graph_score(
    user_id: str, 
    relationship_stability: float, 
    engine: GraphEngine,
    is_first_transaction: bool = False,
    account_age_hours: float = 0.0
) -> Dict[str, Any]:
    """
    Computes the final graph_score (0-1) (SENSITIVE but CONTROLLED):
    - Balanced scoring across 4 components
    - Tiered risk levels
    - Neighbor risk propagation
    """
    features = compute_graph_features(user_id, engine)
    rules_result = get_graph_rules_risk(user_id, features, relationship_stability, engine)
    
    # 1. Connectivity Risk (More sensitive scaling)
    # Start triggering at 3+ connections
    connectivity_risk = min(1.0, (features["in_degree"] + features["out_degree"]) / 6.0)
    
    # 2. Neighbor Risk Propagation
    # Increase score if connected to risky users (Network Influence)
    # Goal: Detect stealth fraud via network influence
    base_neighbor_risk = (features["avg_neighbor_risk"] * 0.6) + (features["percent_flagged_neighbors"] * 0.4)
    neighbor_risk = base_neighbor_risk
    if features["avg_neighbor_risk"] > 0.3 or features["percent_flagged_neighbors"] > 0.15:
        # Significant boost for network influence as requested (graph_score += 0.2 equivalent)
        neighbor_risk = min(1.0, neighbor_risk + 0.4)
    
    # 3. Temporal Risk (More sensitive to bursts & slow patterns)
    burst_risk = min(1.0, features["burst_count_24h"] / 4.0) # More sensitive (from 5.0 to 4.0)
    
    # NEW: Slow patterns/Repeated low-value (contribute to MEDIUM risk)
    slow_pattern_risk = 0.0
    if features.get("low_value_repeated_count", 0) >= 3:
        slow_pattern_risk += 0.4
    if features.get("high_freq_connections", 0) >= 3:
        slow_pattern_risk += 0.3
        
    temporal_risk = max(burst_risk, min(1.0, slow_pattern_risk))
    
    # 4. Structural Risk (Directly from rules)
    structural_risk = rules_result["structural_risk"]
    
    # Updated Weighted Scoring (Balanced 0.25 each)
    raw_score = (
        0.25 * connectivity_risk + 
        0.25 * neighbor_risk + 
        0.25 * temporal_risk + 
        0.25 * structural_risk
    )
    
    # If structural risk is high, it should still have a strong influence
    if structural_risk >= 0.6:
        raw_score = max(raw_score, structural_risk * 0.8)
    
    graph_score = min(1.0, raw_score)
    
    # Tiering logic for debug/classification
    if graph_score < 0.3:
        risk_level = "LOW"
    elif graph_score < 0.6:
        risk_level = "MEDIUM"
    else:
        risk_level = "HIGH"

    # FP Safety Rules
    if relationship_stability > 0.7:
        # Trusted repeated interaction suppresses graph
        graph_score *= 0.3
    
    # NEW USER HANDLING (Controlled)
    if is_first_transaction:
        graph_score *= 0.4 # Significant reduction
    elif account_age_hours < 24:
        graph_score *= 0.6 # Moderate reduction

    return {
        "graph_score": round(float(graph_score), 4),
        "risk_level": risk_level,
        "reasons": rules_result["reasons"],
        "features": features,
        "components": {
            "connectivity": round(connectivity_risk, 4),
            "neighbor": round(neighbor_risk, 4),
            "temporal": round(temporal_risk, 4),
            "structural": round(structural_risk, 4)
        },
        "debug_info": rules_result["debug_info"]
    }
