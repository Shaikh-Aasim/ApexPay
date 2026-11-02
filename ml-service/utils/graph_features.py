import time
from typing import Dict, Any, List, Set, Optional
from .graph_engine import GraphEngine, EdgeState

def compute_graph_features(
    user_id: str, 
    engine: GraphEngine, 
    current_time: Optional[float] = None
) -> Dict[str, Any]:
    """
    Computes rigorous graph-based topological and temporal features for an entity:
    - Discrete multi-window velocity (1-hour, 24-hour, 7-day, lifetime).
    - Separation of recent counterparty activity from lifetime interactions.
    - Decayed neighbour risk propagation to avoid persistent toxic feedback.
    - Repeated micro-transactions (smurfing/fan-in) detection.
    """
    now = float(current_time) if current_time is not None else time.time()
    
    # 1. Connectivity (Lifetime)
    out_edges: List[EdgeState] = engine.get_neighbors(user_id)
    senders: Set[str] = engine.get_senders(user_id)
    
    lifetime_unique_senders = len(senders)
    lifetime_unique_receivers = len(out_edges)
    lifetime_in_degree = lifetime_unique_senders
    lifetime_out_degree = lifetime_unique_receivers

    # Collect incoming edges
    incoming_edges: List[EdgeState] = []
    for s_id in senders:
        for edge in engine.get_neighbors(s_id):
            if edge.target_user_id == user_id:
                incoming_edges.append(edge)

    # 2. Precise Time-Window Metrics (1 Hour, 24 Hours, 7 Days)
    out_1h_count = sum(edge.get_window_metrics(now, 3600)[0] for edge in out_edges)
    in_1h_count = sum(edge.get_window_metrics(now, 3600)[0] for edge in incoming_edges)
    burst_count_1h = out_1h_count + in_1h_count

    out_24h_count = 0
    out_24h_amount = 0.0
    active_receivers_24h = 0
    for edge in out_edges:
        c, a = edge.get_window_metrics(now, 86400)
        if c > 0:
            out_24h_count += c
            out_24h_amount += a
            active_receivers_24h += 1

    in_24h_count = 0
    in_24h_amount = 0.0
    active_senders_24h = 0
    for edge in incoming_edges:
        c, a = edge.get_window_metrics(now, 86400)
        if c > 0:
            in_24h_count += c
            in_24h_amount += a
            active_senders_24h += 1

    burst_count_24h = out_24h_count + in_24h_count
    
    out_7d_count = sum(edge.get_window_metrics(now, 7 * 86400)[0] for edge in out_edges)
    in_7d_count = sum(edge.get_window_metrics(now, 7 * 86400)[0] for edge in incoming_edges)
    burst_count_7d = out_7d_count + in_7d_count

    lifetime_out_txns = sum(edge.lifetime_count for edge in out_edges)
    lifetime_in_txns = sum(edge.lifetime_count for edge in incoming_edges)
    lifetime_total_txns = lifetime_out_txns + lifetime_in_txns

    avg_txn_per_receiver = (lifetime_out_txns / lifetime_out_degree) if lifetime_out_degree > 0 else 0.0

    # 3. Repeated Micro-Transaction Patterns (Structured Smurfing)
    all_edges = out_edges + incoming_edges
    low_value_repeated_count = 0
    high_freq_connections = 0
    for edge in all_edges:
        if edge.lifetime_count >= 3 and (edge.lifetime_amount / max(1, edge.lifetime_count)) < 500:
            low_value_repeated_count += 1
        if edge.lifetime_count >= 5:
            high_freq_connections += 1

    # 4. Decayed Neighbour Risk Propagation (Temporal Contagion)
    neighbor_risk_scores: List[float] = []
    flagged_neighbors_count = 0
    
    # Receivers
    for edge in out_edges:
        score, flagged = engine.get_decayed_user_risk(edge.target_user_id, now=now)
        neighbor_risk_scores.append(score)
        if flagged:
            flagged_neighbors_count += 1

    # Senders
    for s_id in senders:
        score, flagged = engine.get_decayed_user_risk(s_id, now=now)
        neighbor_risk_scores.append(score)
        if flagged:
            flagged_neighbors_count += 1

    total_neighbors = len(neighbor_risk_scores)
    avg_neighbor_risk = (sum(neighbor_risk_scores) / total_neighbors) if total_neighbors > 0 else 0.0
    percent_flagged_neighbors = (flagged_neighbors_count / total_neighbors) if total_neighbors > 0 else 0.0

    return {
        # Active Window Metrics (Current Threat Window)
        "unique_senders_24h": active_senders_24h,
        "unique_receivers_24h": active_receivers_24h,
        "burst_count_1h": burst_count_1h,
        "burst_count_24h": burst_count_24h,
        "burst_count_7d": burst_count_7d,
        "volume_24h": round(out_24h_amount + in_24h_amount, 2),
        
        # Lifetime Network Topology
        "in_degree": lifetime_in_degree,
        "out_degree": lifetime_out_degree,
        "unique_senders": lifetime_unique_senders,
        "unique_receivers": lifetime_unique_receivers,
        "lifetime_txns": lifetime_total_txns,
        "avg_txn_per_receiver": round(avg_txn_per_receiver, 2),
        
        # Micro-Structuring & Layering
        "low_value_repeated_count": low_value_repeated_count,
        "high_freq_connections": high_freq_connections,
        
        # Contagion & Neighbour Risk
        "avg_neighbor_risk": round(avg_neighbor_risk, 4),
        "percent_flagged_neighbors": round(percent_flagged_neighbors, 4),
        "total_neighbors": total_neighbors
    }
