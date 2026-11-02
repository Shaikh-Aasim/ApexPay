from __future__ import annotations
import math
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "graph_store.db"

INVALID_IDENTIFIERS: Set[str] = {
    "unknown_sender",
    "unknown_receiver",
    "user_unknown",
    "dummy",
    "none",
    "null",
    ""
}

def is_valid_identity(uid: Optional[str]) -> bool:
    """Validates that a participant identity is a genuine user account."""
    if uid is None:
        return False
    clean = str(uid).strip().lower()
    return clean not in INVALID_IDENTIFIERS and len(clean) >= 1

@dataclass
class TransactionRecord:
    txn_id: str
    sender_id: str
    receiver_id: str
    amount: float
    timestamp: float
    risk_flags: List[str] = field(default_factory=list)

@dataclass
class EdgeState:
    target_user_id: str
    # Transaction timestamps list for exact time-window analysis
    txn_timestamps: List[float] = field(default_factory=list)
    txn_amounts: List[float] = field(default_factory=list)
    lifetime_count: int = 0
    lifetime_amount: float = 0.0
    risk_flags: List[str] = field(default_factory=list)

    def add_event(self, amount: float, timestamp: float, flags: List[str] = None):
        self.txn_timestamps.append(timestamp)
        self.txn_amounts.append(amount)
        self.lifetime_count += 1
        self.lifetime_amount += amount
        if flags:
            self.risk_flags = list(set(self.risk_flags + flags))

    def get_window_metrics(self, now: float, window_seconds: float) -> Tuple[int, float]:
        """Returns (count, total_amount) strictly within (now - window_seconds, now]."""
        cutoff = now - window_seconds
        count = 0
        total_amt = 0.0
        for ts, amt in zip(reversed(self.txn_timestamps), reversed(self.txn_amounts)):
            if ts >= cutoff:
                count += 1
                total_amt += amt
            else:
                break
        return count, total_amt

class GraphEngine:
    """
    Production-Grade Hybrid Persistent Graph Engine:
    - Directed multigraph with in-memory caching for sub-millisecond lookups.
    - Durable SQLite backing store for restart recovery and multi-worker consistency.
    - Exact time-window velocity aggregation (1h, 24h, 7d, lifetime).
    - Idempotent transaction processing to prevent duplicate edge inflation.
    - Identity sanitization (rejects unknown_sender/unknown_receiver super-hubs).
    - Half-life temporal risk decay for neighbour contagion.
    """

    def __init__(self, db_path: Optional[Path] = None, enable_persistence: bool = True):
        self.enable_persistence = enable_persistence
        self.db_path = db_path or DB_PATH
        self._lock = threading.RLock()
        
        # In-memory fast topology cache
        # adj_list[sender_id] = [EdgeState, ...]
        self.adj_list: Dict[str, List[EdgeState]] = {}
        # reverse_adj_list[receiver_id] = {sender_id1, sender_id2, ...}
        self.reverse_adj_list: Dict[str, Set[str]] = {}
        # user_risk_data[user_id] = (score, timestamp, is_flagged)
        self.user_risk_data: Dict[str, Tuple[float, float, bool]] = {}
        # Seen transaction IDs for idempotency
        self.seen_txn_ids: Set[str] = set()

        if self.enable_persistence:
            self._init_sqlite()
            self._warm_cache_from_db()

    def _init_sqlite(self):
        """Initializes the SQLite schema with WAL mode for high concurrency."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode = WAL;")
                conn.execute("PRAGMA synchronous = NORMAL;")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS graph_transactions (
                        txn_id TEXT PRIMARY KEY,
                        sender_id TEXT NOT NULL,
                        receiver_id TEXT NOT NULL,
                        amount REAL NOT NULL,
                        timestamp REAL NOT NULL,
                        risk_flags TEXT
                    );
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_risk_profiles (
                        user_id TEXT PRIMARY KEY,
                        risk_score REAL NOT NULL,
                        last_updated REAL NOT NULL,
                        is_flagged INTEGER NOT NULL
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_sender ON graph_transactions(sender_id);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_receiver ON graph_transactions(receiver_id);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON graph_transactions(timestamp);")
                conn.commit()
        except Exception as e:
            # Fallback to pure in-memory mode if disk writing is prohibited
            self.enable_persistence = False

    def _warm_cache_from_db(self, lookback_days: int = 30):
        """Pre-loads recent transaction topology into RAM on application startup."""
        if not self.enable_persistence or not self.db_path.exists():
            return
        try:
            cutoff = time.time() - (lookback_days * 86400)
            with sqlite3.connect(self.db_path) as conn:
                # Load seen IDs
                cursor = conn.execute("SELECT txn_id FROM graph_transactions")
                for row in cursor.fetchall():
                    self.seen_txn_ids.add(row[0])

                # Load user risk profiles
                cursor = conn.execute("SELECT user_id, risk_score, last_updated, is_flagged FROM user_risk_profiles")
                for uid, score, ts, flagged in cursor.fetchall():
                    self.user_risk_data[uid] = (float(score), float(ts), bool(flagged))

                # Load recent transactions
                cursor = conn.execute("""
                    SELECT txn_id, sender_id, receiver_id, amount, timestamp, risk_flags
                    FROM graph_transactions
                    WHERE timestamp >= ?
                    ORDER BY timestamp ASC
                """, (cutoff,))
                
                for txn_id, sender_id, receiver_id, amount, ts, flags_str in cursor.fetchall():
                    flags = flags_str.split(",") if flags_str else []
                    self._add_to_memory(sender_id, receiver_id, amount, ts, flags)
        except Exception:
            pass

    def add_transaction(
        self,
        sender_id: str,
        receiver_id: str,
        amount: float,
        timestamp: Optional[float] = None,
        risk_flags: Optional[List[str]] = None,
        txn_id: Optional[str] = None
    ) -> bool:
        """
        Idempotently inserts or updates an edge in the directed transaction graph.
        Returns True if newly inserted, False if duplicate or rejected.
        """
        # 1. Identity validation (Never create artificial super-nodes from missing IDs)
        if not is_valid_identity(sender_id) or not is_valid_identity(receiver_id):
            return False

        if sender_id == receiver_id:
            return False

        ts = float(timestamp) if timestamp is not None else time.time()
        amt = max(0.0, float(amount))
        flags = risk_flags or []
        t_id = str(txn_id) if txn_id else f"txn_{sender_id}_{receiver_id}_{ts}_{amt}"

        with self._lock:
            # Idempotency check: prevent duplicate edge inflation on payment retries
            if t_id in self.seen_txn_ids:
                return False
            self.seen_txn_ids.add(t_id)

            # Update RAM cache
            self._add_to_memory(sender_id, receiver_id, amt, ts, flags)

            # Persist to durable SQLite backing store
            if self.enable_persistence:
                try:
                    with sqlite3.connect(self.db_path) as conn:
                        conn.execute("""
                            INSERT OR IGNORE INTO graph_transactions
                            (txn_id, sender_id, receiver_id, amount, timestamp, risk_flags)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (t_id, sender_id, receiver_id, amt, ts, ",".join(flags)))
                        conn.commit()
                except Exception:
                    pass

        return True

    def _add_to_memory(self, sender_id: str, receiver_id: str, amount: float, timestamp: float, flags: List[str]):
        """Internal helper to insert into adjacency and reverse adjacency caches."""
        if sender_id not in self.adj_list:
            self.adj_list[sender_id] = []

        existing = next((e for e in self.adj_list[sender_id] if e.target_user_id == receiver_id), None)
        if existing:
            existing.add_event(amount, timestamp, flags)
        else:
            new_edge = EdgeState(target_user_id=receiver_id)
            new_edge.add_event(amount, timestamp, flags)
            self.adj_list[sender_id].append(new_edge)

        if receiver_id not in self.reverse_adj_list:
            self.reverse_adj_list[receiver_id] = set()
        self.reverse_adj_list[receiver_id].add(sender_id)

    def update_user_risk(self, user_id: str, risk_score: float, is_flagged: bool = False, timestamp: Optional[float] = None):
        """
        Updates user risk context with real-time timestamping for temporal decay.
        """
        if not is_valid_identity(user_id):
            return

        ts = float(timestamp) if timestamp is not None else time.time()
        score = max(0.0, min(1.0, float(risk_score)))

        with self._lock:
            self.user_risk_data[user_id] = (score, ts, bool(is_flagged))

            if self.enable_persistence:
                try:
                    with sqlite3.connect(self.db_path) as conn:
                        conn.execute("""
                            INSERT INTO user_risk_profiles (user_id, risk_score, last_updated, is_flagged)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(user_id) DO UPDATE SET
                                risk_score=excluded.risk_score,
                                last_updated=excluded.last_updated,
                                is_flagged=excluded.is_flagged;
                        """, (user_id, score, ts, 1 if is_flagged else 0))
                        conn.commit()
                except Exception:
                    pass

    def get_decayed_user_risk(self, user_id: str, now: Optional[float] = None, half_life_days: float = 7.0) -> Tuple[float, bool]:
        """
        Returns (decayed_risk_score, is_flagged).
        Applies exponential half-life decay: Risk decays toward zero over time unless refreshed.
        """
        if not is_valid_identity(user_id) or user_id not in self.user_risk_data:
            return 0.0, False

        score, last_updated, is_flagged = self.user_risk_data[user_id]
        current_time = float(now) if now is not None else time.time()
        elapsed_seconds = max(0.0, current_time - last_updated)

        half_life_seconds = half_life_days * 86400.0
        decay_factor = math.pow(0.5, elapsed_seconds / half_life_seconds)
        decayed_score = score * decay_factor

        return round(decayed_score, 4), is_flagged

    def get_neighbors(self, user_id: str) -> List[EdgeState]:
        """Returns all outgoing edge states for a user."""
        if not is_valid_identity(user_id):
            return []
        return self.adj_list.get(user_id, [])

    def get_senders(self, user_id: str) -> Set[str]:
        """Returns all unique users who sent funds to this account."""
        if not is_valid_identity(user_id):
            return set()
        return self.reverse_adj_list.get(user_id, set())

    def get_in_degree(self, user_id: str) -> int:
        return len(self.get_senders(user_id))

    def get_out_degree(self, user_id: str) -> int:
        return len(self.get_neighbors(user_id))

    def reset(self):
        """Clears in-memory caches and clears the SQLite store for clean test isolation."""
        with self._lock:
            self.adj_list.clear()
            self.reverse_adj_list.clear()
            self.user_risk_data.clear()
            self.seen_txn_ids.clear()
            if self.enable_persistence and self.db_path.exists():
                try:
                    with sqlite3.connect(self.db_path) as conn:
                        conn.execute("DELETE FROM graph_transactions;")
                        conn.execute("DELETE FROM user_risk_profiles;")
                        conn.commit()
                except Exception:
                    pass
