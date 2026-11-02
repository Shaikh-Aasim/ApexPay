from typing import Dict, List, Any, Set, Optional
from .graph_engine import GraphEngine

def detect_mule_pattern(features: Dict[str, Any], relationship_stability: float) -> Dict[str, Any]:
    """
    Tiered Money Mule Detection:
    - CRITICAL: >= 10 senders in 24h -> 0.95 (High-velocity aggregation funnel)
    - HIGH risk: >= 5 senders in 24h AND burst > 3 AND stability < 0.4 -> 0.90
    - MEDIUM risk: >= 3 senders AND stability < 0.4 -> 0.50
    """
    risk = 0.0
    flags = []
    
    senders_24h = features.get("unique_senders_24h", features.get("unique_senders", 0))
    burst_24h = features.get("burst_count_24h", 0)
    is_unstable = relationship_stability < 0.40

    if senders_24h >= 10:
        risk = 0.95
        flags.append("critical_mule_funnel")
    elif senders_24h >= 5 and burst_24h > 3 and is_unstable:
        risk = 0.90
        flags.append("mule_pattern_confirmed")
    elif (senders_24h >= 5 or features.get("in_degree", 0) >= 6) and is_unstable:
        risk = 0.55
        flags.append("mule_pattern_suspected")
    elif (senders_24h >= 3 or burst_24h >= 4) and is_unstable:
        risk = 0.35
        flags.append("mule_soft_signal")
    
    if features.get("in_degree", 0) >= 5:
        flags.append("high_in_degree")
        
    return {"risk": risk, "flags": flags}

def detect_fraud_ring(user_id: str, engine: GraphEngine, relationship_stability: float, depth: int = 8) -> Dict[str, Any]:
    """
    Fraud Ring / Circular Laundering Detection:
    - Analyzes unique participant count in cycle (strictly distinct entities).
    - Social Triangles (unique nodes <= 3, e.g. A -> B -> C -> A): Natural social bill-splitting -> 0.05
    - Intermediate Ring (unique nodes == 4): 0.40
    - Extended Laundering Ring (unique nodes >= 5): 0.95
    - Bounded DFS with step budget to guarantee sub-millisecond execution in dense networks.
    """
    step_budget = [0]
    MAX_STEPS = 150

    def find_cycle(current_id: str, target_id: str, visited: Set[str], path: List[str]) -> Optional[List[str]]:
        step_budget[0] += 1
        if step_budget[0] > MAX_STEPS or len(path) > depth:
            return None
        
        neighbors = [e.target_user_id for e in engine.get_neighbors(current_id)]
        
        # Check for cycle completion
        if target_id in neighbors and len(path) >= 3:
            return path + [target_id]
            
        for neighbor in neighbors:
            if neighbor not in visited and step_budget[0] <= MAX_STEPS:
                new_visited = visited.copy()
                new_visited.add(neighbor)
                result = find_cycle(neighbor, target_id, new_visited, path + [neighbor])
                if result:
                    return result
        return None

    cycle_path = find_cycle(user_id, user_id, {user_id}, [user_id])
    
    risk = 0.0
    flags = []
    # Count strictly UNIQUE participants in the cycle (avoid counting start node twice)
    unique_nodes = set(cycle_path) if cycle_path else set()
    path_len = len(unique_nodes)
    
    if cycle_path and path_len >= 3:
        if relationship_stability < 0.40:
            if path_len >= 5:
                risk = 0.95
                flags.append("high_density_ring")
            elif path_len == 4:
                risk = 0.40
                flags.append("moderate_ring_pattern")
            else:
                # Small 3-node cycle (A -> B -> C -> A): natural social triangle, negligible fraud risk
                risk = 0.05
                flags.append("social_triangle")
        elif relationship_stability < 0.65:
            risk = 0.25 if path_len >= 5 else 0.05
            flags.append("weak_ring_signal")
        else:
            risk = 0.02
            flags.append("stable_cycle")

    return {"risk": risk, "flags": flags, "path_len": path_len}

def detect_suspicious_hub(features: Dict[str, Any], relationship_stability: float) -> Dict[str, Any]:
    """
    Suspicious Hub Detection:
    - Identifies high-volume aggregation nodes with unstable counterparty relationships.
    """
    risk = 0.0
    flags = []
    senders_24h = features.get("unique_senders_24h", features.get("unique_senders", 0))
    
    if senders_24h >= 8 and relationship_stability < 0.30:
        risk = 0.85
        flags.append("unstable_high_volume_hub")
    elif senders_24h >= 5 and relationship_stability < 0.40:
        risk = 0.60
        flags.append("moderate_unstable_hub")
    elif senders_24h >= 3 and relationship_stability < 0.50:
        risk = 0.35
        flags.append("minor_unstable_hub")
        
    return {"risk": risk, "flags": flags}

def get_graph_rules_risk(user_id: str, features: Dict[str, Any], 
                         relationship_stability: float, engine: GraphEngine) -> Dict[str, Any]:
    """
    Combines graph rules and returns structural risk components.
    """
    mule_res = detect_mule_pattern(features, relationship_stability)
    ring_res = detect_fraud_ring(user_id, engine, relationship_stability)
    hub_res = detect_suspicious_hub(features, relationship_stability)
    
    mule_risk = mule_res["risk"]
    ring_risk = ring_res["risk"]
    hub_risk = hub_res["risk"]
    
    # FP Safety: If stability is very high (> 0.75), suppress structural graph risk
    if relationship_stability > 0.75:
        return {
            "structural_risk": 0.05,
            "reasons": ["High relationship stability suppresses graph risk"],
            "mule_risk": 0.0,
            "ring_risk": 0.0,
            "hub_risk": 0.0,
            "debug_info": {"ignored": True, "reason": "high_stability"}
        }

    structural_risk = max(mule_risk, ring_risk, hub_risk)

    reasons = []
    if mule_risk >= 0.75:
        reasons.append(f"Mule pattern detected: {', '.join(mule_res['flags'])}")
    elif mule_risk >= 0.40:
        reasons.append("Moderate mule-like activity")

    if ring_risk >= 0.75:
        reasons.append(f"Fraud ring pattern detected: unique_nodes={ring_res['path_len']}")
    elif ring_risk >= 0.35:
        reasons.append("Partial fraud ring signature")

    if hub_risk >= 0.75:
        reasons.append("High-risk transaction hub detected")
    elif hub_risk >= 0.40:
        reasons.append("Moderate hub suspicious activity")

    debug_info = {
        "mule_flags": mule_res["flags"],
        "ring_flags": ring_res["flags"],
        "hub_flags": hub_res["flags"],
        "path_len": ring_res.get("path_len", 0),
        "structural_risk": structural_risk
    }
    
    return {
        "structural_risk": structural_risk,
        "reasons": reasons,
        "mule_risk": mule_risk,
        "ring_risk": ring_risk,
        "hub_risk": hub_risk,
        "debug_info": debug_info
    }
