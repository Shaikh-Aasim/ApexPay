# ApexPay ML Service Architecture & System Design

## 1. System Overview

The ApexPay ML Service is an intelligent, real-time risk assessment and fraud detection subsystem designed for a high-throughput, UPI-style payment gateway. Positioned in the pre-settlement authorization path, the service evaluates every payment transaction in real time to prevent financial fraud before funds are transferred.

```
┌─────────────────┐       ┌────────────────────────┐       ┌──────────────────────┐
│  Mobile App /   │       │  ApexPay Node.js Core  │       │  ApexPay ML Service  │
│  User Frontend  │       │     Backend Engine     │       │    (FastAPI / Py)    │
└────────┬────────┘       └───────────┬────────────┘       └──────────┬───────────┘
         │  Initiate Transfer         │                               │
         │───────────────────────────>│                               │
         │                            │  POST /predict-risk           │
         │                            │──────────────────────────────>│
         │                            │                               │  1. Extract Features
         │                            │                               │  2. Graph Ingestion
         │                            │                               │  3. RF Inference
         │                            │                               │  4. Rule Analysis
         │                            │                               │  5. Graph Intelligence
         │                            │  RiskResponse                 │  6. Multi-Signal Fusion
         │                            │<──────────────────────────────│
         │                            │                               │
         │  Decision Resolution:      │                               │
         │  - LOW: Auto-Approve       │                               │
         │  - MEDIUM: OTP Step-Up     │                               │
         │  - HIGH: Block / Reject    │                               │
         │<───────────────────────────│                               │
```

---

## 2. Three-Layer Hybrid Architecture

Fraud detection in financial networks requires balancing high recall against low false positives. Pure machine learning models often struggle with novel attacks or cold-start entities, while static rules fail to capture non-linear behavioral correlations. 

ApexPay employs a unified **Three-Layer Hybrid Architecture**:

```
                       Incoming Payment Request
                                  │
                                  ▼
           ┌──────────────────────────────────────────────┐
           │        Layer 1: Heuristic Rule Engine         │
           │  - Amount Z-Score & Dynamic Limits           │
           │  - Device & Location Anomaly Detection       │
           │  - Cold-Start First-Transaction Safeguards   │
           │  - Counterparty Stability Discounts          │
           └──────────────────────┬───────────────────────┘
                                  │
                                  ▼
           ┌──────────────────────────────────────────────┐
           │     Layer 2: Calibrated Machine Learning     │
           │  - 300-Estimator Random Forest Ensemble      │
           │  - Platt Sigmoid Probability Calibration     │
           │  - 17 Standardized Behavioral Features       │
           └──────────────────────┬───────────────────────┘
                                  │
                                  ▼
           ┌──────────────────────────────────────────────┐
           │      Layer 3: Graph Intelligence Engine      │
           │  - Directed Multigraph Topology              │
           │  - Discrete Multi-Window Velocity (1h, 24h)  │
           │  - Cycle DFS Laundering Detection            │
           │  - Mule Account Fan-In Ingestion             │
           │  - Half-Life Neighbor Risk Temporal Decay    │
           └──────────────────────┬───────────────────────┘
                                  │
                                  ▼
           ┌──────────────────────────────────────────────┐
           │       Multi-Signal Confirmation & Fusion     │
           │  - Adaptive Weighted Score Integration       │
           │  - Smart Force Critical Security Overrides   │
           │  - Normalized 3-Tier Decision Gating         │
           └──────────────────────┬───────────────────────┘
                                  │
                                  ▼
                 Authoritative Decision & Risk Payload
```

### Layer 1: Heuristic Rule Engine (`utils/risk_rules.py`)
- Evaluates deterministic, explainable financial rules.
- Computes contextual thresholds rather than static rupee cutoffs (e.g. ₹50,000 is legitimate for a high-net-worth user with low Z-score, but anomalous for a low-spending user).
- Grants **relationship stability discounts**: stable counterparties with extensive transaction history receive up to 60% reduction in heuristic suspicion.
- Grants **periodic pattern discounts**: recurring payments (e.g., rent, utility, salary) on regular calendar days are recognized and suppressed from false flagging.
- Returns a structured `HeuristicResult` containing `risk_score`, `decision`, `reasons`, and canonical `fraud_type` (`ACCOUNT_TAKEOVER`, `MULE_ACCOUNT`, `FIRST_TXN_HIGH_AMOUNT`, `PHISHING`, or `UNKNOWN`).

### Layer 2: Machine Learning Inference (`training/train.py`, `api/predict.py`)
- Employs a 300-tree **Random Forest Classifier** trained on high-entropy transaction vectors.
- Probability outputs are strictly calibrated using **Platt Sigmoid Calibration** (`CalibratedClassifierCV(method='sigmoid', cv=3)`). This ensures the output represents a mathematically reliable posterior probability $P(\text{Fraud} = 1 \mid \mathbf{x})$, eliminating tree-ensemble probability clumping near decision boundaries.
- Produces a pure `ml_probability` in $[0.0, 1.0]$.

### Layer 3: Graph Intelligence Engine (`utils/graph_engine.py`, `utils/graph_score.py`)
- Maintains a real-time directed multigraph of user accounts (nodes) and financial payments (edges).
- Calculates four topological components:
  1. **Connectivity Risk:** Degree centrality and active connection counts.
  2. **Neighbor Risk:** Contagion propagation from flagged counterparties, discounted by temporal half-life decay.
  3. **Temporal Velocity Risk:** Discrete sliding window activity (1-hour burst, 24-hour frequency, 7-day volume).
  4. **Structural Risk:** Deep graph motifs including circular fraud rings and mule account fan-in aggregation.
- Decouples sender and receiver evaluation to prevent attribute cross-contamination.

---

## 3. Data Flow and Execution Lifecycle

1. **Request Intake:**
   - FastAPI receives `POST /predict-risk` with transaction attributes and participant identifiers (`sender_id`, `receiver_id`).
2. **Graph Edge Ingestion:**
   - The engine validates participant identities. If valid, the payment is idempotently inserted into the graph topology and durable store.
3. **Feature Extraction:**
   - Contextual signals are extracted, including user historical baseline ($\mu_{30d}, \sigma_{30d}$), $Z$-score, device indicators, and relationship stability.
4. **Independent Layer Scoring:**
   - Heuristic rules compute `rule_score` and `rule_decision`.
   - Random Forest computes `ml_probability`.
   - Graph engine computes `graph_score` for both sender and receiver independently.
5. **Smart Force Overrides:**
   - Critical account takeovers ($Z > 8.0$ or new device + location anomaly + unstable recipient + high amount) trigger an immediate, non-negotiable `HIGH` override.
6. **Adaptive Fusion:**
   - When ML is confident ($> 0.75$), ML weight increases to $0.65$.
   - When ML is uncertain ($< 0.25$), Rules and Graph provide the foundation ($0.45\text{ ML} + 0.30\text{ Rules} + 0.25\text{ Graph}$).
   - Balanced baseline weights: $0.55\text{ ML} + 0.25\text{ Rules} + 0.20\text{ Graph}$.
7. **Decision Gating & Response:**
   - Authoritative mapping to `LOW` ($< 0.42$), `MEDIUM` ($[0.42, 0.75)$), or `HIGH` ($\ge 0.75$).
   - Returns full response payload with explainability reasons.

---

## 4. State Persistence and Multi-Worker Architecture

To support multi-instance deployment across distributed workers and survive restarts:
- **Durable SQLite Backing Store (`data/graph_store.db`):** Configured with Write-Ahead Logging (`PRAGMA journal_mode = WAL;`) and `synchronous = NORMAL` for high write concurrency.
- **In-Memory Graph Topology:** An in-memory adjacency index (`adj_list`) provides sub-millisecond ($< 0.5\text{ ms}$) graph queries during inference.
- **Startup Cache Warming:** Upon service boot, the engine replays the last 30 days of transactions from SQLite into the RAM topology index.
- **Thread Safety:** All modifications to graph structures are protected by re-entrant locks (`threading.RLock`).

---

## 5. Security and Failure Modes

1. **Identity Spoofing & Super-Node Prevention:**
   - Identifiers such as `"unknown_sender"`, `"unknown_receiver"`, `"dummy"`, and empty strings are rejected by `is_valid_identity()`. Artificial super-nodes cannot form.
2. **Graceful Fallback:**
   - If the trained model artifact is missing, the service operates in rule-plus-graph mode without throwing 500 errors.
   - If graph database persistence fails, the service falls back to in-memory mode seamlessly.
3. **Input Validation:**
   - Strict Pydantic and Zod schema validation across FastAPI and Node.js backend prevents type confusion and out-of-bound inputs.
