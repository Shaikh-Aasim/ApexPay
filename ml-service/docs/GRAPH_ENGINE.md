# ApexPay Graph Intelligence Engine & Network Fraud Topology

## 1. Architectural Motivation

Financial fraud within payment networks frequently operates across coordinated multi-party topologies rather than isolated single-point accounts:
- **Money Mules:** Dormant or complicit accounts that receive funds from multiple victims and immediately funnel or withdraw the proceeds.
- **Circular Laundering Rings:** Chains of transactions designed to obscure the origin of stolen funds by routing money through multiple intermediate hops ($A \to B \to C \to D \to A$).
- **Smurfing (Structuring):** Breaking large illicit sums into small transfers below regulatory monitoring thresholds.

The ApexPay **Graph Intelligence Engine** (`utils/graph_engine.py`, `utils/graph_features.py`, `utils/graph_rules.py`, `utils/graph_score.py`) models the payment network as a directed multigraph, continuously computing topological and temporal network features in real time.

---

## 2. Directed Multigraph Data Structures

```
              ┌────────────────────────────────────────────────────────┐
              │                   GraphEngine In-Memory                │
              │                                                        │
              │   adj_list: Dict[sender_id, List[EdgeState]]           │
              │   reverse_adj_list: Dict[receiver_id, Set[sender_id]]  │
              │   user_risk_data: Dict[user_id, (score, ts, flagged)]  │
              │   seen_txn_ids: Set[txn_id]                            │
              └───────────────────────────┬────────────────────────────┘
                                          │ Sync
                                          ▼
              ┌────────────────────────────────────────────────────────┐
              │              Durable SQLite (WAL Mode)                 │
              │                 data/graph_store.db                    │
              │                                                        │
              │   - graph_transactions: (txn_id, sender, receiver...) │
              │   - user_risk_profiles: (user_id, risk_score, ts...)   │
              └────────────────────────────────────────────────────────┘
```

### 2.1 The `EdgeState` Abstraction
Instead of collapsing multiple payments between two accounts into a single static edge with an overwritten timestamp, the engine maintains discrete transaction arrays inside each `EdgeState`:

```python
@dataclass
class EdgeState:
    target_user_id: str
    txn_timestamps: List[float] = field(default_factory=list)
    txn_amounts: List[float] = field(default_factory=list)
    lifetime_count: int = 0
    lifetime_amount: float = 0.0
    risk_flags: List[str] = field(default_factory=list)
```

---

## 3. Discrete Multi-Window Velocity Aggregation

A critical flaw in legacy fraud engines is the **Historical Conflation Bug**: treating a counterparty's total historical transaction count as occurring within the past 24 hours.

ApexPay resolves this by filtering chronological timestamp arrays using strict binary cutoffs:

$$\text{Count}(u \to v, W) = \sum_{i=1}^n \mathbb{I}\left(t_i \ge t_{\text{now}} - W\right)$$

```python
def get_window_metrics(self, now: float, window_seconds: float) -> Tuple[int, float]:
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
```

### Window Specifications:
1. **1-Hour Burst Window ($W = 3,600\text{ s}$):** Detects immediate bot-driven script execution and rapid credential harvesting.
2. **24-Hour Velocity Window ($W = 86,400\text{ s}$):** Evaluates daily aggregation limits and active counterparty count.
3. **7-Day Velocity Window ($W = 604,800\text{ s}$):** Tracks weekly structural patterns and gradual smurfing.
4. **Lifetime History:** Retained for cumulative relationship stability scoring without inflating recent velocity metrics.

---

## 4. Network Pattern Detection Algorithms

### 4.1 Money Mule Aggregation (Fan-In Funnels)
Money mules exhibit high in-degree centrality with low relationship stability. Incoming payments originate from multiple distinct payers within short time windows:

```
Victim 1 ────┐
Victim 2 ────┼───> [ MULE ACCOUNT ] ───> [ Cash-Out / Off-Ramp ]
Victim 3 ────┘
```

- **Critical Funnel:** $\ge 10$ unique senders in 24 hours $\implies \text{Structural Risk} = 0.95$ (immediate hard override to `HIGH`).
- **Confirmed Mule:** $\ge 5$ unique senders in 24 hours AND burst $> 3$ AND stability $< 0.40 \implies \text{Structural Risk} = 0.90$.
- **Suspected Mule:** $\ge 5$ senders OR in-degree $\ge 6$ with low stability $\implies \text{Structural Risk} = 0.55$.

### 4.2 Circular Laundering Rings & Social Triangles
Laundering rings route funds in directed cycles to disguise origin:

```
[ A ] ───> [ B ] ───> [ C ] ───> [ D ] ───> [ E ] ───> [ A ]
```

The engine employs a bounded Depth-First Search (DFS) algorithm with a strict step budget (maximum 150 traversal steps, maximum depth 6) to detect closed loops in $< 1.0\text{ ms}$:

```python
unique_participants = len(set(cycle_path))
```

#### Social Triangle Discounting:
- **3-Node Cycles ($A \to B \to C \to A$):** Ubiquitous in legitimate consumer behavior (e.g., three friends splitting restaurant bills or roommates paying utility shares). The engine explicitly exempts 3-node cycles from laundering penalties:
  $$\text{unique\_nodes} \le 3 \implies \text{Structural Risk} = 0.05 \quad (\text{social\_triangle})$$
- **4-Node Cycles:** Moderate laundering risk ($\text{Risk} = 0.40$).
- **5-Node & Extended Cycles ($N \ge 5$):** Severe circular laundering ring ($\text{Risk} = 0.95$).

---

## 5. Neighbor Risk Contagion & Temporal Half-Life Decay

Direct association with known fraudulent counterparties propagates risk. However, indefinite contagion creates permanent toxic feedback loops that unfairly penalize legitimate users who unknowingly transacted with a flagged merchant.

### 5.1 Propagation Formula
$$\text{RawNeighborRisk}(u) = 0.6 \cdot \overline{\text{Risk}}_{\text{neighbors}} + 0.4 \cdot \text{PercentFlagged}_{\text{neighbors}}$$

### 5.2 Exponential Half-Life Decay
Risk associated with flagged nodes decays exponentially over time using a 14-day half-life ($\lambda = 1,209,600\text{ seconds}$):

$$\text{DecayedRisk}(u, t) = \text{Risk}_0 \cdot \left(\frac{1}{2}\right)^{\frac{t - t_0}{\lambda}}$$

If an account maintains a clean record for 30 days following an isolated incident, its neighbor contagion contribution drops below $0.05$.

---

## 6. Durable Persistence & Idempotency

- **SQLite WAL Backing Store:** Transactions and user risk updates are committed to `data/graph_store.db` using WAL mode for concurrent multi-worker read/write safety.
- **Idempotency Safeguard:** Network retries and duplicate payment callbacks are indexed by `seen_txn_ids`. Duplicate transaction IDs are acknowledged without creating duplicate graph edges.
- **Identity Sanitization:** Missing or placeholder identifiers (`unknown_sender`, `unknown_receiver`, `dummy`, `""`) are rejected by `is_valid_identity()`, completely preventing the formation of artificial super-nodes.
