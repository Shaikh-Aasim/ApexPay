# ApexPay ML Service: Intelligent Pre-Settlement Fraud Detection Gateway

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Framework-FastAPI-green.svg)](https://fastapi.tiangolo.com/)
[![Scikit-Learn](https://img.shields.io/badge/Model-RandomForest%20%2B%20CalibratedCV-orange.svg)](https://scikit-learn.org/)
[![Tests](https://img.shields.io/badge/Regression%20Tests-11%2F11%20Passed%20(100%25)-brightgreen.svg)]()
[![Model F1](https://img.shields.io/badge/F1--Score-0.9741-success.svg)]()

The **ApexPay ML Service** is a real-time, pre-settlement fraud detection and risk scoring microservice engineered for high-throughput, UPI-style instant payment gateways. Operating synchronously in the pre-authorization path, the service evaluates payment transactions across three integrated layers to identify financial threats before settlement occurs.

---

## 1. Three-Layer Hybrid Architecture

Fraud detection in financial networks requires balancing maximum threat recall against minimal customer friction. ApexPay utilizes an integrated **Three-Layer Architecture**:

```
                       Incoming Payment Request
                                  │
                                  ▼
           ┌──────────────────────────────────────────────┐
           │        Layer 1: Heuristic Rule Engine         │
           │  - Amount Z-Score & Contextual Limits        │
           │  - Device & Location Anomaly Verification    │
           │  - Cold-Start First-Transaction Safeguards   │
           │  - Relationship Stability Risk Discounts     │
           │  - Periodic Pattern Exemptions (Salary/Rent) │
           └──────────────────────┬───────────────────────┘
                                  │
                                  ▼
           ┌──────────────────────────────────────────────┐
           │     Layer 2: Calibrated Machine Learning     │
           │  - 150-Tree Random Forest Ensemble           │
           │  - Platt Sigmoid Probability Calibration     │
           │  - 17 Standardized Behavioral Features       │
           │  - 98.53% Accuracy | 98.75% Recall           │
           └──────────────────────┬───────────────────────┘
                                  │
                                  ▼
           ┌──────────────────────────────────────────────┐
           │      Layer 3: Graph Intelligence Engine      │
           │  - Directed Multigraph with In-Memory Cache  │
           │  - Discrete Time-Windows (1h, 24h, 7d)       │
           │  - Bounded Cycle DFS Laundering Detection    │
           │  - Money Mule Fan-In Funnel Aggregation      │
           │  - 14-Day Half-Life Neighbor Risk Decay      │
           │  - Durable SQLite WAL Backing Store          │
           └──────────────────────┬───────────────────────┘
                                  │
                                  ▼
           ┌──────────────────────────────────────────────┐
           │       Multi-Signal Confirmation & Fusion     │
           │  - Adaptive Weighted Score Blending          │
           │  - Non-Negotiable Hard Security Overrides    │
           │  - Precision-Guarded False Positive Filter   │
           └──────────────────────┬───────────────────────┘
                                  │
                                  ▼
               Authoritative Decision: LOW / MEDIUM / HIGH
```

### Three-Tier Decision Outcomes:
- **`LOW` (Auto-Approve):** Score in $[0.00, 0.42)$. Immediate settlement with zero user friction.
- **`MEDIUM` (Step-Up Authentication):** Score in $[0.42, 0.75)$. Held for 60-second secondary challenge (OTP / Biometric / MPIN verification).
- **`HIGH` (Block / Immediate Rejection):** Score in $[0.75, 1.00]$. Non-negotiable transaction decline and account investigation.

---

## 2. Key Technical Advancements

1. **Discrete Time-Window Velocity Aggregation:**
   - Completely resolved the legacy 24-hour conflation bug. The engine now stores discrete timestamp arrays per edge, strictly filtering transactions across 1-hour bursts, 24-hour velocities, 7-day totals, and lifetime counts.
2. **Social Triangle Exemption vs. Circular Laundering:**
   - Small 3-node cyclic flows ($A \to B \to C \to A$) are recognized as natural social bill-splitting with negligible risk ($0.05$).
   - Complex cycles ($\ge 5$ nodes) are detected via bounded DFS as circular laundering rings with high structural risk ($0.95$).
3. **Mule Fan-In Funnel Detection:**
   - High in-degree aggregation ($\ge 10$ unique senders in 24 hours with low stability) is flagged as a critical money mule funnel.
4. **Durable Persistence & Idempotency:**
   - Sub-millisecond in-memory RAM cache backed by durable SQLite in Write-Ahead Logging (`WAL`) mode. Replays 30-day history upon boot and rejects duplicate `txn_id` submissions.
5. **Decoupled Sender & Receiver Context:**
   - Sender-specific attributes (`is_first_transaction`, `account_age_hours`) are strictly isolated and never erroneously applied to receiver evaluation.
6. **Platt Sigmoid Calibration:**
   - Random Forest probabilities are calibrated via Platt scaling, mapping ensemble votes directly to true empirical posterior probabilities $P(\text{Fraud} = 1 \mid \mathbf{x})$.

---

## 3. Directory Layout

```
ml-service/
├── api/
│   ├── integration.py         # Adaptive multi-signal score fusion & decision gating
│   ├── main.py                # FastAPI endpoints (/health, /metrics, /predict-risk)
│   └── predict.py             # RiskPredictor orchestration pipeline
├── data/
│   └── graph_store.db         # Persistent SQLite WAL store for transaction graph
├── docs/                      # Comprehensive technical documentation suite
│   ├── API_REFERENCE.md       # Full API specifications, schemas & curl examples
│   ├── DATASET_FEATURE_MAPPING.md # Public benchmark (PaySim, IEEE-CIS) mapping specs
│   ├── DATASET_GENERATION.md  # Synthetic data generation math & distributions
│   ├── GRAPH_ENGINE.md        # Graph topology, cycle DFS & mule detection algorithms
│   ├── ML_ARCHITECTURE.md     # Full architectural design & component lifecycle
│   ├── ML_SERVICE_AUDIT.md    # Initial engineering audit & remediation matrix
│   ├── MODEL_TRAINING.md      # Training pipeline, calibration & cross-validation
│   ├── RISK_DECISION_POLICY.md# 3-tier policy, thresholds & override governance
│   └── TEST_REPORT.md         # Full test suite execution report & verification
├── model/
│   ├── metrics.json           # Serialized model metrics & evaluation report
│   └── risk_model.joblib      # CalibratedClassifierCV Random Forest bundle
├── scripts/
│   └── benchmark_dataset_mapping.py # Public dataset converter (PaySim & IEEE-CIS)
├── tests/
│   ├── mini_test_data_generator.py  # Rapid test dataset generator
│   ├── quick_test_runner.py         # Fast validation runner
│   ├── test_data_generator.py       # Canonical 50,000-sample generator
│   └── test_service_comprehensive.py# 11-point automated regression test suite
├── training/
│   └── train.py               # Model training, cross-validation & calibration script
├── utils/
│   ├── features.py            # 17 canonical features definition & vectorizer
│   ├── graph_engine.py        # Directed multigraph engine & SQLite WAL persistence
│   ├── graph_features.py      # Multi-window velocity & graph metric calculators
│   ├── graph_rules.py         # Cycle DFS, mule fan-in & structural rules
│   ├── graph_score.py         # 4-component graph score calculator
│   └── risk_rules.py          # Heuristic rule engine & dynamic thresholds
├── requirements.txt           # Python package dependencies
└── README.md                  # Project overview & operational documentation
```

---

## 4. Installation & Quickstart

### Prerequisites
- Python 3.10+ (tested on Python 3.10, 3.11, 3.12, 3.14)
- Virtual environment recommended

### Setup
```bash
# 1. Clone repository & navigate to ml-service
cd ml-service

# 2. Create and activate a Python virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## 5. Model Training & Evaluation

```bash
# 1. Generate canonical 50,000-sample high-entropy dataset
python tests/test_data_generator.py

# 2. Execute 5-fold cross validation, training, and Platt sigmoid calibration
python training/train.py
```

### Verified Model Performance:
- **Accuracy:** 98.53%
- **Precision:** 96.11%
- **Recall:** 98.75%
- **F1-Score:** 0.9741
- **Cross-Validation (5-Fold F1):** 0.9735 ($\pm 0.0030$)

---

## 6. Running the API Service

```bash
# Start FastAPI server on port 8000
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Quick Verification:
```bash
# Health check
curl http://127.0.0.1:8000/health

# Evaluate transaction risk
curl -X POST "http://127.0.0.1:8000/predict-risk" \
  -H "Content-Type: application/json" \
  -d '{
    "sender_id": "usr_rahul_9912",
    "receiver_id": "usr_ananya_3321",
    "amount": 450.0,
    "amount_zscore": 0.25,
    "txn_count_24h": 2,
    "relationship_stability_score": 0.85
  }'
```

---

## 7. Running the Automated Test Suite

```bash
# Execute comprehensive 11-point regression and integrity suite
python tests/test_service_comprehensive.py
```

All 11 critical test categories validate normal payments, account takeover overrides, cold-start limits, social triangles, circular laundering, mule fan-ins, time-window aggregations, idempotency, identity sanitization, API schema completeness, and latency SLAs.

---

## 8. Public Benchmark Mapping

Convert industry-standard datasets into the ApexPay 17-feature schema:

```bash
# Map PaySim Mobile Money dataset
python scripts/benchmark_dataset_mapping.py --dataset paysim --mock-test

# Map IEEE-CIS Fraud Detection dataset
python scripts/benchmark_dataset_mapping.py --dataset ieee_cis --mock-test
```

---

## 9. Comprehensive Documentation Index

For detailed deep-dives into specific subsystems, consult the documents in `docs/`:
- [`docs/ML_SERVICE_AUDIT.md`](file:///d:/SPIT/Major%20Project/Final%20Clone/ApexPay/ml-service/docs/ML_SERVICE_AUDIT.md): Engineering audit, defect catalog & remediation matrix.
- [`docs/ML_ARCHITECTURE.md`](file:///d:/SPIT/Major%20Project/Final%20Clone/ApexPay/ml-service/docs/ML_ARCHITECTURE.md): Multi-layer system design, data flow & failure modes.
- [`docs/DATASET_GENERATION.md`](file:///d:/SPIT/Major%20Project/Final%20Clone/ApexPay/ml-service/docs/DATASET_GENERATION.md): Statistical distributions & synthetic fraud scenarios.
- [`docs/DATASET_FEATURE_MAPPING.md`](file:///d:/SPIT/Major%20Project/Final%20Clone/ApexPay/ml-service/docs/DATASET_FEATURE_MAPPING.md): PaySim & IEEE-CIS feature derivation & proxies.
- [`docs/MODEL_TRAINING.md`](file:///d:/SPIT/Major%20Project/Final%20Clone/ApexPay/ml-service/docs/MODEL_TRAINING.md): Random Forest training, calibration & feature rankings.
- [`docs/RISK_DECISION_POLICY.md`](file:///d:/SPIT/Major%20Project/Final%20Clone/ApexPay/ml-service/docs/RISK_DECISION_POLICY.md): 3-tier policy bands, overrides & multi-signal matrix.
- [`docs/GRAPH_ENGINE.md`](file:///d:/SPIT/Major%20Project/Final%20Clone/ApexPay/ml-service/docs/GRAPH_ENGINE.md): Directed multigraph topology, time windows & decay math.
- [`docs/API_REFERENCE.md`](file:///d:/SPIT/Major%20Project/Final%20Clone/ApexPay/ml-service/docs/API_REFERENCE.md): REST endpoints, schemas, error codes & Node.js integration.
- [`docs/TEST_REPORT.md`](file:///d:/SPIT/Major%20Project/Final%20Clone/ApexPay/ml-service/docs/TEST_REPORT.md): Quality assurance report & verification evidence.
