import time
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field

@dataclass
class Edge:
    target_user_id: str
    amount: float
    timestamp: float
    txn_count: int
    risk_flags: List[str] = field(default_factory=list)

class GraphEngine:
    """
    Manages a directed graph of users and transactions using an adjacency list.
    Designed for real-time incremental updates and efficient querying.
    """
    def __init__(self):
        # adjacency_list[sender_id] = [Edge(receiver_id, ...), ...]
        self.adj_list: Dict[str, List[Edge]] = {}
        # reverse_adj_list[receiver_id] = [sender_id1, sender_id2, ...]
        self.reverse_adj_list: Dict[str, Set[str]] = {}
        # user_risk_scores[user_id] = score
        self.user_risk_scores: Dict[str, float] = {}
        # user_flagged[user_id] = bool
        self.user_flagged: Dict[str, bool] = {}

    def add_transaction(self, sender_id: str, receiver_id: str, amount: float, 
                        timestamp: Optional[float] = None, risk_flags: List[str] = None):
        """
        Adds or updates a directed edge from sender to receiver.
        """
        if timestamp is None:
            timestamp = time.time()
        if risk_flags is None:
            risk_flags = []

        if sender_id not in self.adj_list:
            self.adj_list[sender_id] = []
        
        # Check if an edge already exists to update it or add a new one
        existing_edge = next((e for e in self.adj_list[sender_id] if e.target_user_id == receiver_id), None)
        
        if existing_edge:
            existing_edge.amount += amount
            existing_edge.timestamp = timestamp
            existing_edge.txn_count += 1
            # Merge risk flags
            existing_edge.risk_flags = list(set(existing_edge.risk_flags + risk_flags))
        else:
            self.adj_list[sender_id].append(Edge(
                target_user_id=receiver_id,
                amount=amount,
                timestamp=timestamp,
                txn_count=1,
                risk_flags=risk_flags
            ))

        # Update reverse adjacency for in-degree calculations
        if receiver_id not in self.reverse_adj_list:
            self.reverse_adj_list[receiver_id] = set()
        self.reverse_adj_list[receiver_id].add(sender_id)

    def update_user_risk(self, user_id: str, risk_score: float, is_flagged: bool = False):
        """
        Updates the risk context for a user node.
        """
        self.user_risk_scores[user_id] = risk_score
        self.user_flagged[user_id] = is_flagged

    def get_neighbors(self, user_id: str) -> List[Edge]:
        """Returns all outgoing edges for a user."""
        return self.adj_list.get(user_id, [])

    def get_senders(self, user_id: str) -> Set[str]:
        """Returns all unique users who sent money to this user."""
        return self.reverse_adj_list.get(user_id, set())

    def get_in_degree(self, user_id: str) -> int:
        """Returns the number of unique senders."""
        return len(self.get_senders(user_id))

    def get_out_degree(self, user_id: str) -> int:
        """Returns the number of unique receivers."""
        return len(self.adj_list.get(user_id, []))

    def reset(self):
        """Clears the graph state."""
        self.adj_list.clear()
        self.reverse_adj_list.clear()
        self.user_risk_scores.clear()
        self.user_flagged.clear()
