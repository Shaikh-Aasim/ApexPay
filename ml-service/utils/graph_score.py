from typing import Dict, Any, List
from .graph_engine import GraphEngine, is_valid_identity
from .graph_features import compute_graph_features
from .graph_rules import get_graph_rules_risk

def calculate_graph_score(
    user_id: str, 
    relationship_stability: float, 
    engine: GraphEngine,
    is_first_transaction: bool = False,
    account_age_hours: float = 720.0
) -> Dict[str, Any]:
    """
    Computes the final graph_score (0-1):
    - Balanced scoring across 4 components (connectivity, neighbor, temporal, structural)
    - Dominant structural risk propagation for rings/mules
    - Counterparty stability suppression for legitimate users
    - Graceful fallback when identity is invalid or missing
    """
    if not is_valid_identity(user_id):
        return {
            "graph_score": 0.0,
            "risk_level": "LOW",
            "reasons": [],
            "features": {
                "in_degree": 0, "out_degree": 0, "burst_count_1h": 0, "burst_count_24h": 0,
                "burst_count_7d": 0, "lifetime_txns": 0, "unique_senders_24h": 0,
                "unique_receivers_24h": 0, "avg_neighbor_risk": 0.0, "percent_flagged_neighbors": 0.0
            },
            "components": {
                "connectivity": 0.0,
                "neighbor": 0.0,
                "temporal": 0.0,
                "structural": 0.0
            },
            "debug_info": {"status": "identity_unavailable_or_invalid"}
        }

    features = compute_graph_features(user_id, engine)
    rules_result = get_graph_rules_risk(user_id, features, relationship_stability, engine)
    
    # 1. Connectivity Risk (meaningful only beyond standard 1-2 contacts)
    total_conns = features["in_degree"] + features["out_degree"]
    connectivity_risk = min(1.0, max(0.0, total_conns - 2) / 6.0) if total_conns > 2 else 0.0
    
    # 2. Neighbor Risk Propagation
    base_neighbor_risk = (features["avg_neighbor_risk"] * 0.6) + (features["percent_flagged_neighbors"] * 0.4)
    neighbor_risk = base_neighbor_risk
    if features["avg_neighbor_risk"] > 0.3 or features["percent_flagged_neighbors"] > 0.15:
        neighbor_risk = min(1.0, neighbor_risk + 0.4)
    
    # 3. Temporal Risk (Bursts start having risk only at 3+ txns in 24h)
    burst_risk = min(1.0, max(0.0, features["burst_count_24h"] - 2) / 4.0) if features["burst_count_24h"] > 2 else 0.0
    slow_pattern_risk = 0.0
    if features.get("low_value_repeated_count", 0) >= 3:
        slow_pattern_risk += 0.4
    if features.get("high_freq_connections", 0) >= 3:
        slow_pattern_risk += 0.3
        
    temporal_risk = max(burst_risk, min(1.0, slow_pattern_risk))
    
    # 4. Structural Risk (Directly from rules)
    structural_risk = rules_result["structural_risk"]
    
    # 4-Component Weighted Scoring
    raw_score = (
        0.25 * connectivity_risk + 
        0.25 * neighbor_risk + 
        0.25 * temporal_risk + 
        0.25 * structural_risk
    )
    
    # Dominant structural risk overrides
    if structural_risk >= 0.85:
        raw_score = max(raw_score, structural_risk)
    elif structural_risk >= 0.60:
        raw_score = max(raw_score, structural_risk * 0.85)
    
    graph_score = min(1.0, raw_score)
    
    # Tiering logic for debug/classification
    if graph_score < 0.35:
        risk_level = "LOW"
    elif graph_score < 0.70:
        risk_level = "MEDIUM"
    else:
        risk_level = "HIGH"

    # FP Safety Rules: High relationship stability strongly dampens graph risk
    if relationship_stability > 0.70:
        graph_score *= 0.25
    
    # Cold-Start New User Handling
    if is_first_transaction:
        graph_score *= 0.40
    elif account_age_hours < 24:
        graph_score *= 0.60

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
