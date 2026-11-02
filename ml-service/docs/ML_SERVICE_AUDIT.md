# ApexPay ML Service - Comprehensive Architecture & Codebase Audit

**Audit Date:** November 2026  
**Auditor:** Senior Machine Learning Engineer & Financial Fraud Architect  
**Project:** ApexPay – Intelligent Payment Gateway Fraud Detection Microservice  
**Service Root:** `d:\SPIT\Major Project\Final Clone\ApexPay\ml-service`

---

## 1. Executive Summary

The ApexPay ML Service is designed as a low-latency, real-time risk assessment engine guarding against payment fraud in UPI-style peer-to-peer (P2P) and peer-to-merchant (P2M) transactions. The service employs a **three-layer defense-in-depth architecture**:
1. **Layer 1: Heuristic Rule Engine** (Deterministic domain rules, ATO safeguards, blacklist checks).
2. **Layer 2: Calibrated Machine Learning Model** (Random Forest Classifier evaluated across 17 tabular features).
3. **Layer 3: Graph Intelligence Engine** (Directed multigraph analyzing transaction topology, money mules, circular layering rings, and counterparty contagion).

This audit documents confirmed bugs, architectural weaknesses, mathematical desynchronizations, and operational vulnerabilities identified across all service components, along with concrete remediation blueprints.

---

## 2. Complete Execution Trace (End-to-End Flow)

```
[Transaction Request Initiated in ApexPay Backend]
       │
       ▼
[paymentService.ts: Query user 30d history, velocity, device/IP changes, receiver risk]
       │
       ▼
[HTTP POST /predict-risk (api/main.py)]
       │
       ▼
[RiskRequest Pydantic Validation]
       │
       ▼
[RiskPredictor.predict() (api/predict.py)]
  ├── 1. Graph State Ingestion (GraphEngine.add_transaction)
  ├── 2. Feature Extraction & Dynamic Z-score (utils/features.py)
  ├── 3. Layer 1: Heuristic Risk Evaluation (utils/risk_rules.py)
  ├── 4. Layer 2: Machine Learning Inference (RandomForest.predict_proba)
  ├── 5. Anti-False-Negative Safeguards & Hard Overrides
  └── 6. Layer 3: Graph Intelligence & Social Network Topology (utils/graph_*.py)
       │
       ▼
[Score Integration & Adaptive Fusion (api/integration.py)]
  ├── Adaptive Weighting (ML + Rule + Graph)
  ├── Multi-Signal Confirmation Matrix
  └── Decision Harmonization (LOW / MEDIUM / HIGH)
       │
       ▼
[FastAPI JSON Response: RiskResponse (api/main.py)]
       │
       ▼
[ApexPay Backend Action in paymentService.ts]
  ├── LOW    ──> Status: REQUESTED (Cleared immediately)
  ├── MEDIUM ──> Status: HOLD, otp_required = true (Step-Up Authentication)
  └── HIGH   ──> Status: FAILED, failureReason = RISK_REJECTED (Blocked)
```

---

## 3. Confirmed Audit Findings & Defect Catalog

### Finding 1: Historical Edge Aggregation Corrupting 24-Hour Velocity
* **Component:** `utils/graph_engine.py` & `utils/graph_features.py`
* **Severity:** **CRITICAL (High False Positive Rate)**
* **Problem:** In `GraphEngine.add_transaction()`, subsequent transactions between the same pair updated `existing_edge.amount += amount`, `existing_edge.txn_count += 1`, and `existing_edge.timestamp = now`. In `compute_graph_features()`, temporal burst was computed as:
  ```python
  recent_out = [edge for edge in out_edges if (now - edge.timestamp) < window_seconds]
  burst_count = sum(edge.txn_count for edge in recent_out)
  ```
  If a sender transacted 25 times over the past year with a landlord or spouse, and sent ₹100 today, the condition `(now - edge.timestamp) < 86400` evaluated to `True`. The entire lifetime count (26 transactions) was summed into `burst_count_24h`!
* **Consequence:** Legitimate long-term users were falsely flagged as automated velocity attackers.
* **Correction:** Introduce time-bucketed event storage (1h, 24h, 7d, lifetime) recording discrete transaction timestamps rather than a single overwriting edge timestamp.

---

### Finding 2: Artificial Graph Super-Nodes via Shared Placeholders
* **Component:** `api/predict.py` & `api/main.py`
* **Severity:** **HIGH (Graph Topology Distortion)**
* **Problem:** If a request arrived without `sender_id` or `receiver_id`, the system defaulted to `"unknown_sender"` and `"unknown_receiver"`. Over time, thousands of unrelated transactions were recorded between these identical string identifiers.
* **Consequence:** The graph engine created an artificial "super-mule" hub connecting unrelated customers, causing neighbor risk propagation to poison unrelated accounts.
* **Correction:** Validate `sender_id` and `receiver_id`. If identifiers are missing or invalid, bypass graph topological updates and execute graceful fallback scoring without polluting the graph.

---

### Finding 3: In-Memory Graph Volatility (Single-Process Limitation)
* **Component:** `utils/graph_engine.py`
* **Severity:** **HIGH (Production Reliability & Multi-Worker Desync)**
* **Problem:** The graph state resided entirely within Python dictionaries (`adj_list`, `reverse_adj_list`). A service restart or multi-worker deployment (`uvicorn --workers 4`) wiped out or desynchronized the transaction network. Replaying requests created duplicate edges.
* **Correction:** Implement a persistent graph storage interface backed by an ACID-compliant durable storage engine (SQLite/PostgreSQL) with in-memory caching and transaction deduplication via `transaction_id` or idempotency keys.

---

### Finding 4: Graph Cycle Participant Miscounting & Small Triangle Penalization
* **Component:** `utils/graph_rules.py`
* **Severity:** **MEDIUM (False Positive on Peer Groups)**
* **Problem:** DFS cycle search returned `path + [target_id]`. A 3-node cycle ($A \rightarrow B \rightarrow C \rightarrow A$) resulted in a path length of 4 (`[A, B, C, A]`), miscounting the number of distinct participants. Furthermore, 3-node cycles were assigned `risk = 0.50`, flagging normal bill-splitting between roommates as a fraud ring.
* **Correction:** Calculate cycle length based strictly on unique participants (`len(set(cycle_path))`). Treat 3-node cycles as natural social triangles with near-zero structural risk (`0.05`), reserving fraud ring alerts for complex layering ($\ge 4$ or $\ge 5$ distinct hops).

---

### Finding 5: Context Conflation Between Senders and Receivers
* **Component:** `api/integration.py`
* **Severity:** **HIGH (Incorrect Risk Evaluation)**
* **Problem:** `integrate_graph_intelligence()` called:
  ```python
  g_res_sender = calculate_graph_score(sender_id, stability, engine, is_first, age_hours)
  g_res_receiver = calculate_graph_score(receiver_id, stability, engine, is_first, age_hours)
  ```
  The sender's `is_first_transaction` and `account_age_hours` were passed into the receiver's evaluation.
* **Consequence:** If a new account paid an established corporate utility or verified merchant, the merchant was evaluated as a brand new account making its first transaction.
* **Correction:** Decouple sender context from receiver context. Pass separate sender and receiver metadata.

---

### Finding 6: Stale Neighbour Risk in Production Flow
* **Component:** `api/predict.py`
* **Severity:** **MEDIUM (Graph Stagnation)**
* **Problem:** `update_user_risk()` was only invoked in test runner loops, never inside the live FastAPI `POST /predict-risk` lifecycle. Receiver suspicion scores never updated dynamically after risk inference.
* **Correction:** Implement post-prediction risk updates with temporal decay so risk scores fade over time if no further suspicious activity occurs.

---

### Finding 7: Binary vs. 3-Tier Decision Gating
* **Component:** `api/predict.py`
* **Severity:** **CRITICAL (Payment Flow Broken)**
* **Problem:** `predict.py` previously contained `decision = "HIGH" if final_score >= 0.25 else "LOW"`.
* **Consequence:** `MEDIUM` (OTP Hold) was completely eliminated. Any score $\ge 0.25$ resulted in instant transaction rejection, breaking the payment gateway's 2FA step-up flow.
* **Correction:** Restore the 3-tier business decision spectrum: `LOW` ($< 0.42$), `MEDIUM` ($0.42 - 0.74$), `HIGH` ($\ge 0.75$).

---

### Finding 8: Fractional Boolean Flags in Synthetic Datasets
* **Component:** `tests/test_data_generator.py`
* **Severity:** **HIGH (Decision Tree Split Corruption)**
* **Problem:** Synthetic generators assigned `device = 0.5` and `location = 0.5`.
* **Consequence:** Random Forest trees learned invalid split thresholds (e.g. `<= 0.25` or `> 0.45`), degrading tree decisions on production boolean inputs.
* **Correction:** Strictly enforce binary values (`0.0` or `1.0`).

---

### Finding 9: Column Desynchronization Across Benchmark Sets
* **Component:** `tests/mini_test_data_generator.py` & `tests/graph_test_data.py`
* **Severity:** **HIGH (Model Evaluation Failure)**
* **Problem:** `test_data_mini.csv` and `graph_test_data_mini.csv` only had 15 columns instead of the required 22 columns, and named the stability feature `"relationship_stability"` instead of `"relationship_stability_score"`.
* **Consequence:** Features defaulted to `0.0` during evaluation.
* **Correction:** Standardize all dataset generators to output the complete canonical 22-column schema.

---

### Finding 10: Artificial Label Flipping in Test Evaluation
* **Component:** `training/train.py`
* **Severity:** **CRITICAL (Distorted Performance Metrics)**
* **Problem:** `add_test_noise()` randomly inverted 8% of test labels (`1 - label`).
* **Consequence:** The model appeared to have only 54.3% recall because 8% of ground-truth test labels were corrupted.
* **Correction:** Evaluate model on verified, uncorrupted stratified test splits. Apply noise only as training data augmentation.

---

## 4. Remediation Matrix & Implementation Status

| Audit Finding | Affected Modules | Severity | Remediation Strategy | Status |
| :--- | :--- | :---: | :--- | :---: |
| **Edge Time-Windowing** | `graph_engine.py`, `graph_features.py` | CRITICAL | Multi-window counters (1h, 24h, 7d, lifetime) | Implemented |
| **Shared Unknown Nodes** | `predict.py`, `main.py`, `graph_engine.py` | HIGH | Reject/bypass graph for missing IDs | Implemented |
| **Graph Persistence** | `graph_engine.py` | HIGH | SQLite durable edge store + transaction idempotency | Implemented |
| **Cycle Participant Counting** | `graph_rules.py` | MEDIUM | Unique set counting; social triangle exemption | Implemented |
| **Sender/Receiver Decoupling** | `integration.py` | HIGH | Explicit separation of counterparty contexts | Implemented |
| **Neighbour Risk Decay** | `graph_engine.py`, `predict.py` | MEDIUM | Half-life risk decay & live post-predict updates | Implemented |
| **3-Tier Decision Gating** | `predict.py`, `integration.py` | CRITICAL | Calibrated LOW / MEDIUM / HIGH decision policy | Implemented |
| **Fractional Booleans** | `test_data_generator.py` | HIGH | Strict 0.0 / 1.0 boolean constraints | Implemented |
| **Schema Desynchronization**| `mini_test_data_generator.py`, `graph_test_data.py` | HIGH | Universal 22-column canonical format | Implemented |
| **Label Contamination** | `train.py` | CRITICAL | Pristine ground-truth test sets; Stratified CV | Implemented |

---

## 5. Architectural Recommendations

1. **Persistent Multigraph Storage:** Transition the in-memory graph to a durable transactional backing store (e.g. SQLite for single-node / embedded environments, PostgreSQL for cluster deployments) with in-memory caching to guarantee persistence across container restarts.
2. **Transparent Risk Indices:** Return separate values for `ml_probability`, `rule_score`, `graph_score`, and `combined_risk_score` to give the Node.js backend full explainability.
3. **Public Benchmark Provenance:** Maintain clear documentation distinguishing simulated synthetic UPI datasets from real-world benchmarks (PaySim, IEEE-CIS).
