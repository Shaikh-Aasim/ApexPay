from typing import Dict, List, Any, Set, Optional
from .graph_engine import GraphEngine

def detect_mule_pattern(features: Dict[str, Any], relationship_stability: float) -> Dict[str, Any]:
    """
    Mule Detection (TIERED):
    - HIGH risk: in_degree >= 5 AND unique_senders >= 5 AND txn_count_24h > 3 AND stability < 0.4
    - MEDIUM risk: in_degree >= 3 OR unique_senders >= 3 OR moderate burst
    """
    risk = 0.0
    flags = []
    
    # Core Mule Criteria
    has_high_in_degree = features["in_degree"] >= 5
    has_many_senders = features["unique_senders"] >= 5
    has_burst = features["burst_count_24h"] > 3
    is_unstable = relationship_stability < 0.4

    # Moderate Criteria (Soft Signals)
    is_moderate_in_degree = features["in_degree"] >= 3
    is_moderate_senders = features["unique_senders"] >= 3
    is_moderate_burst = features["burst_count_24h"] >= 2

    # HIGH risk patterns
    if has_high_in_degree and has_many_senders and has_burst and is_unstable:
        risk = 0.85
        flags.append("mule_pattern_confirmed")
    # MEDIUM risk patterns (Partial patterns)
    elif (has_high_in_degree or has_many_senders) and is_unstable:
        risk = 0.5
        flags.append("mule_pattern_suspected")
    # LOW/MEDIUM risk (Soft signals)
    elif (is_moderate_in_degree or is_moderate_senders or is_moderate_burst) and is_unstable:
        risk = 0.35
        flags.append("mule_soft_signal")
    
    if has_high_in_degree:
        flags.append("high_in_degree")
        
    return {"risk": risk, "flags": flags}

def detect_fraud_ring(user_id: str, engine: GraphEngine, relationship_stability: float, depth: int = 10) -> Dict[str, Any]:
    """
    Fraud Ring Detection (TIERED):
    - HIGH risk: node_count >= 5 AND stability < 0.4
    - MEDIUM risk: smaller cycles (3-4 nodes) or moderate stability issues
    """
    path_nodes = set()
    
    def find_cycle(current_id: str, target_id: str, visited: Set[str], path: List[str]) -> Optional[List[str]]:
        if len(path) > depth:
            return None
        
        neighbors = [e.target_user_id for e in engine.get_neighbors(current_id)]
        
        # Check for cycle completion (allow 3+ nodes for broader recall)
        if target_id in neighbors and len(path) >= 3:
            return path + [target_id]
            
        for neighbor in neighbors:
            if neighbor not in visited:
                new_visited = visited.copy()
                new_visited.add(neighbor)
                result = find_cycle(neighbor, target_id, new_visited, path + [neighbor])
                if result:
                    return result
        return None

    cycle_path = find_cycle(user_id, user_id, {user_id}, [user_id])
    
    risk = 0.0
    flags = []
    path_len = len(cycle_path) if cycle_path else 0
    
    if cycle_path:
        if relationship_stability < 0.4:
            if path_len >= 5:
                risk = 0.9
                flags.append("high_density_ring")
            else:
                risk = 0.5
                flags.append("moderate_ring_pattern")
        elif relationship_stability < 0.6:
            risk = 0.3
            flags.append("weak_ring_signal")
        else:
            risk = 0.1
            flags.append("stable_cycle")

    return {"risk": risk, "flags": flags, "path_len": path_len}

def detect_suspicious_hub(features: Dict[str, Any], relationship_stability: float) -> Dict[str, Any]:
    """
    Suspicious Hub Detection (TIERED):
    - HIGH: high unique senders AND low stability
    - MEDIUM: moderate unique senders AND low stability
    """
    risk = 0.0
    flags = []
    
    if features["unique_senders"] >= 5 and relationship_stability < 0.3:
        risk = 0.75
        flags.append("unstable_high_volume_hub")
    elif features["unique_senders"] >= 3 and relationship_stability < 0.5:
        risk = 0.4
        flags.append("moderate_unstable_hub")
        
    return {"risk": risk, "flags": flags}

def get_graph_rules_risk(user_id: str, features: Dict[str, Any], 
                         relationship_stability: float, engine: GraphEngine) -> Dict[str, Any]:
    """
    Combines graph rules and returns risk components.
    IMPROVED: Support tiered risk and partial pattern detection.
    """
    mule_res = detect_mule_pattern(features, relationship_stability)
    ring_res = detect_fraud_ring(user_id, engine, relationship_stability)
    hub_res = detect_suspicious_hub(features, relationship_stability)
    
    mule_risk = mule_res["risk"]
    ring_risk = ring_res["risk"]
    hub_risk = hub_res["risk"]
    
    signals_count = 0
    if mule_risk >= 0.3: signals_count += 1
    if ring_risk >= 0.3: signals_count += 1
    if hub_risk >= 0.3: signals_count += 1
    
    # FP SAFETY: If stability is very high, suppress everything
    if relationship_stability > 0.75:
        return {
            "structural_risk": 0.05, # Negligible
            "reasons": ["High relationship stability suppresses graph risk"],
            "mule_risk": 0.0,
            "ring_risk": 0.0,
            "hub_risk": 0.0,
            "debug_info": {"ignored": True, "reason": "high_stability"}
        }

    # If only one weak signal exists and it's very low, we might still ignore
    # BUT we are more sensitive now (>= 0.3 is considered a signal)
    if signals_count == 0:
        return {
            "structural_risk": 0.0,
            "reasons": [],
            "mule_risk": 0.0,
            "ring_risk": 0.0,
            "hub_risk": 0.0,
            "debug_info": {"signals_count": 0}
        }

    reasons = []
    if mule_risk >= 0.6:
        reasons.append(f"Mule pattern detected: {', '.join(mule_res['flags'])}")
    elif mule_risk >= 0.3:
        reasons.append("Moderate mule-like activity")

    if ring_risk >= 0.6:
        reasons.append(f"Fraud ring pattern detected: nodes={ring_res['path_len']}")
    elif ring_risk >= 0.3:
        reasons.append("Partial fraud ring signature")

    if hub_risk >= 0.6:
        reasons.append("High-risk transaction hub detected")
    elif hub_risk >= 0.4:
        reasons.append("Moderate hub suspicious activity")
        
    structural_risk = max(mule_risk, ring_risk, hub_risk)
    
    debug_info = {
        "mule_flags": mule_res["flags"],
        "ring_flags": ring_res["flags"],
        "hub_flags": hub_res["flags"],
        "path_len": ring_res.get("path_len", 0),
        "signals_count": signals_count
    }
    
    return {
        "structural_risk": structural_risk,
        "reasons": reasons,
        "mule_risk": mule_risk,
        "ring_risk": ring_risk,
        "hub_risk": hub_risk,
        "debug_info": debug_info
    }
