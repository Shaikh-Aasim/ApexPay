# ApexPay ML Service Quality Assurance & Test Report

**Execution Date:** November 2, 2026  
**Test Harness:** `tests/test_service_comprehensive.py`  
**Execution Environment:** Windows Server / Python 3.14 / SQLite 3 (WAL Mode)  
**Overall Status:** **100% PASSED (11/11 Automated Suites)**

---

## 1. Executive Summary

A comprehensive automated quality assurance evaluation was performed across all three layers of the ApexPay ML Service:
1. **Machine Learning Layer:** Calibrated 150-tree Random Forest (`risk_model.joblib`) evaluated across 50,000 synthetic transaction records.
2. **Heuristic Risk Engine:** Dynamic threshold scaling, relationship stability discounting, periodic pattern exceptions, and hard security overrides.
3. **Graph Intelligence Engine:** Multi-window velocity filters (1h, 24h, 7d), cyclic laundering detection (DFS), mule account fan-in aggregation, temporal half-life decay, SQLite WAL persistence, and super-node prevention.

All 11 automated test suites passed without errors or regressions.

---

## 2. Regression & Integrity Suite Results (`tests/test_service_comprehensive.py`)

| Test ID | Test Category | Specification & Injected Conditions | Expected Behavior | Observed Result | Status |
|:---:|---|---|---|---|:---:|
| **01** | Legitimate Payments | Normal grocery transaction (\u20b9350), $|Z| = 0.1$, stability $= 0.85$ | Approved immediately as `LOW` ($< 0.42$) | Score: `0.0008`, Decision: `LOW` | **PASS** |
| **02** | Security Overrides | Compromised account, sudden new device, distant location, $|Z| = 8.5$, \u20b945,000 | Immediate non-negotiable `HIGH` block, `ACCOUNT_TAKEOVER` | Score: `0.9500`, Fraud Type: `ACCOUNT_TAKEOVER` | **PASS** |
| **03** | Cold-Start Safeguard | Brand new account ($< 2$ hours old) transferring maximum ceiling (\u20b975,000) | Flagged for step-up authentication / block | Score: `1.0000`, Decision: `HIGH` | **PASS** |
| **04** | Graph Social Triangle | 3 friends splitting bills ($A \to B \to C \to A$) | Classified as social triangle; risk $\le 0.10$ | Unique Nodes: `3`, Risk: `0.02` | **PASS** |
| **05** | Graph Laundering Ring | 5-node directed cycle ($U_0 \to U_1 \to U_2 \to U_3 \to U_4 \to U_0$) | Classified as laundering ring; risk $\ge 0.90$ | Unique Nodes: `5`, Risk: `0.95`, Flag: `high_density_ring` | **PASS** |
| **06** | Graph Mule Funnel | Target account receiving funds from 11 distinct senders within 24 hours | Detected as critical mule funnel ($\ge 10$ senders) | Active Senders: `11`, Risk: `0.95` | **PASS** |
| **07** | Time-Window Isolation | 10 transactions 15 days ago, 1 transaction today | $24\text{h}$ burst $= 1$, Lifetime count $= 11$ | Burst 24h: `1`, Lifetime: `11` | **PASS** |
| **08** | Idempotency Protection | Re-sending identical `transaction_id` multiple times | Deduplicated; edge count remains 1 | Insertion 1: `True`, Insertion 2: `False`, Count: `1` | **PASS** |
| **09** | Identity Sanitization | Submitting `unknown_sender` and placeholder strings | Rejection; no artificial super-nodes created | `unknown_sender` rejected, `dummy` invalid | **PASS** |
| **10** | API Schema Contract | Inspecting keys returned by `predict()` | Full contract compliance for Node.js backend | All 9 required keys present and validated | **PASS** |
| **11** | Latency Benchmark | 25 consecutive single-sample inference evaluations | Median latency (p50) $< 300\text{ ms}$ in Python test runner | **p50: 81.06ms**, p95: 115.62ms, p99: 124.48ms | **PASS** |

---

## 3. Model Training & Cross-Validation Metrics (`training/train.py`)

The machine learning model was trained on 50,000 canonical transactions using Stratified 80/20 train/test splitting and 5-Fold Stratified Cross-Validation:

- **Algorithm:** Random Forest Classifier (150 estimators, max depth 10, min samples leaf 4, class weight balanced) wrapped in `CalibratedClassifierCV(method='sigmoid', cv=3)`.
- **5-Fold Cross-Validation Mean F1:** **0.9735** ($\pm 0.0030$).

### Hold-Out Test Set Performance ($N = 10,000$):
- **Accuracy:** **98.53%**
- **Precision:** **96.11%**
- **Recall:** **98.75%**
- **F1-Score:** **0.9741**

### Confusion Matrix:
$$\begin{pmatrix} 7085 & 112 \\ 35 & 2768 \end{pmatrix}$$
- **True Negatives (Legitimate Approved):** 7,085 (98.44%)
- **False Positives (Legitimate Flagged):** 112 (1.56%)
- **False Negatives (Fraud Missed):** 35 (1.25%)
- **True Positives (Fraud Blocked):** 2,768 (98.75%)

### Threshold Sensitivity Analysis:
| Decision Threshold | Precision | Recall | F1-Score | Operational Role |
|:---:|:---:|:---:|:---:|---|
| **0.30** | 95.72% | 99.04% | 0.9735 | Maximum Security Mode |
| **0.40** | 95.95% | 98.93% | 0.9742 | High Sensitivity Gateway |
| **0.45** | **96.11%** | **98.75%** | **0.9741** | **Default ApexPay Production Threshold** |
| **0.50** | 96.50% | 98.50% | 0.9749 | Standard Balanced Mode |
| **0.60** | 97.03% | 97.93% | 0.9748 | Low-Friction Merchant Flow |
| **0.70** | 98.02% | 97.00% | 0.9751 | High-Volume Enterprise SLA |

---

## 4. Benchmark Dataset Mapping Tests (`scripts/benchmark_dataset_mapping.py`)

- **PaySim Schema Transformation:**
  - Evaluated on 2,500 records.
  - Successfully derived `user_avg_amount_30d`, `user_std_amount_30d`, `amount_zscore`, `txn_count_24h`, and `relationship_stability_score`.
  - Output file: `tests/mock_mapped_paysim.csv` verified.
- **IEEE-CIS Schema Transformation:**
  - Evaluated on 2,500 records.
  - Successfully mapped `TransactionAmt`, `D1` (account age proxy), and `C1` (velocity proxy).
  - Output file: `tests/mock_mapped_ieee.csv` verified.

---

## 5. Storage & Concurrency Audit

1. **SQLite WAL Mode:**
   - Active database: `data/graph_store.db` (126 KB).
   - Write-Ahead Logging verified (`PRAGMA journal_mode = WAL`).
   - Dual-layer RAM cache provides sub-millisecond in-memory lookups without disk read bottlenecks during live inference.
2. **Idempotent Edge Insertion:**
   - Verified that resubmissions of identical `txn_id` tokens return `False` and are safely discarded without duplicate edge count inflation.
3. **Decoupled Counterparty Context:**
   - Verified that sender attributes (`is_first_transaction`, `account_age_hours`) are never incorrectly applied when computing the receiver's graph risk.


## 6. Regression Addendum — Optional Receiver Context Fix (November 2, 2026)

A reproducible API failure was traced to `receiver_account_age_hours`: the Pydantic request model declares this field optional, so `model_dump()` includes it with value `None` when omitted. The graph integration previously used `data.get("receiver_account_age_hours", 720.0)`, which returns the existing `None` rather than the fallback, and then called `float(None)`.

**Fix:** Treat an explicit `None` as missing and use the existing neutral 720-hour fallback. The API exception handler now logs the full traceback server-side. A regression test covers the optional receiver fields, and an API-level test exercises the same six-field request used in Swagger UI.

**Validation performed in the available test runtime:** 13/13 automated suites passed, including the optional-context regression and a FastAPI `TestClient` POST that returned HTTP 200 with the complete response contract. The serialized model reports scikit-learn 1.9.1 while the available validation runtime had 1.8.0, producing scikit-learn version warnings. `requirements.txt` is therefore aligned to the model's recorded 1.9.1 version; a clean installation with that exact version should be used for final local verification.
