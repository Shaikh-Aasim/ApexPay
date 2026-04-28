import time
from typing import Dict, Any, List, Set
from .graph_engine import GraphEngine

def compute_graph_features(user_id: str, engine: GraphEngine, window_seconds: int = 86400) -> Dict[str, Any]:
    """
    Computes graph-based features for a specific user.
    Includes connectivity, relationship strength, temporal patterns, and neighbor risk.
    """
    now = time.time()
    
    # 1. Connectivity
    out_edges = engine.get_neighbors(user_id)
    senders = engine.get_senders(user_id)
    
    in_degree = len(senders) # Number of unique senders
    out_degree = len(out_edges) # Number of unique receivers
    unique_receivers = out_degree
    unique_senders = in_degree

    # 2. Relationship Strength (interaction frequency)
    # Reusing the idea of relationship stability from the main system if available, 
    # but here we compute it based on graph edges.
    total_out_txns = sum(edge.txn_count for edge in out_edges)
    avg_txn_per_receiver = total_out_txns / out_degree if out_degree > 0 else 0

    # 4. Temporal Patterns (burst & slow patterns)
    # Check both incoming and outgoing for bursts
    in_senders_data = engine.reverse_adj_list.get(user_id, set())
    
    incoming_edges = []
    for s_id in in_senders_data:
        edges_from_s = engine.get_neighbors(s_id)
        for edge in edges_from_s:
            if edge.target_user_id == user_id:
                incoming_edges.append(edge)

    recent_out = [edge for edge in out_edges if (now - edge.timestamp) < window_seconds]
    recent_in = [edge for edge in incoming_edges if (now - edge.timestamp) < window_seconds]
    
    burst_count = sum(edge.txn_count for edge in recent_out) + sum(edge.txn_count for edge in recent_in)
    
    # NEW: Slow/Repeated Patterns
    # Repeated low-value transactions
    all_edges = out_edges + incoming_edges
    low_value_count = 0
    for edge in all_edges:
        if edge.txn_count >= 3 and (edge.amount / edge.txn_count) < 500: # Low value repeated
            low_value_count += 1
            
    # Gradual increase in connections (approximated by total connections vs recent)
    total_conns = in_degree + out_degree
    # This is a bit hard without full history, but we can look at txn_counts
    high_frequency_conns = sum(1 for edge in all_edges if edge.txn_count > 5)

    # 5. Neighbor Risk
    neighbor_risk_scores = []
    flagged_neighbors_count = 0
    
    # Check receivers
    for edge in out_edges:
        target_id = edge.target_user_id
        risk = engine.user_risk_scores.get(target_id, 0.0)
        neighbor_risk_scores.append(risk)
        if engine.user_flagged.get(target_id, False):
            flagged_neighbors_count += 1
            
    # Check senders
    for sender_id in senders:
        risk = engine.user_risk_scores.get(sender_id, 0.0)
        neighbor_risk_scores.append(risk)
        if engine.user_flagged.get(sender_id, False):
            flagged_neighbors_count += 1

    total_neighbors = len(neighbor_risk_scores)
    avg_neighbor_risk = sum(neighbor_risk_scores) / total_neighbors if total_neighbors > 0 else 0.0
    percent_flagged_neighbors = flagged_neighbors_count / total_neighbors if total_neighbors > 0 else 0.0

    return {
        "in_degree": in_degree,
        "out_degree": out_degree,
        "unique_senders": unique_senders,
        "unique_receivers": unique_receivers,
        "avg_txn_per_receiver": avg_txn_per_receiver,
        "burst_count_24h": burst_count,
        "low_value_repeated_count": low_value_count,
        "high_freq_connections": high_frequency_conns,
        "avg_neighbor_risk": avg_neighbor_risk,
        "percent_flagged_neighbors": percent_flagged_neighbors,
        "total_neighbors": total_neighbors
    }
