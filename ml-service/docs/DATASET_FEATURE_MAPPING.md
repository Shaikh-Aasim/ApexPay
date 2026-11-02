# Dataset Feature Mapping Specification: Public Benchmarks to ApexPay

## 1. Overview and Rationale

The ApexPay Fraud Detection Engine operates on real-time transaction streaming data with an intelligent three-layer architecture:
1. **Machine Learning Layer:** Calibrated ensemble model predicting transaction-level fraud probability.
2. **Heuristic Risk Engine:** Deterministic rule engine evaluating behavioral velocity, device anomalies, and baseline deviations.
3. **Graph Intelligence Engine:** Dynamic directed multigraph tracking counterparty familiarity, mule account funnels, and circular laundering rings.

Public fraud datasets—such as **PaySim** (Mobile Money synthetic simulation) and **IEEE-CIS Fraud Detection** (Vesta e-commerce benchmark)—are industry standards for academic evaluation. However, these benchmarks utilize disparate schemas and lack explicit UPI-specific fields (e.g., relationship stability score, receiver suspicion history, device binding deltas).

This document details the mathematical transformations, proxies, and behavioral derivations implemented in `scripts/benchmark_dataset_mapping.py` to map these public benchmarks onto ApexPay's canonical 17-feature production schema.

---

## 2. ApexPay Canonical 17-Feature Schema

Every transaction evaluated by the ML inference pipeline is vectorized into the following 17 features:

| Index | Feature Identifier | Type | Domain / Range | Semantic Meaning in UPI Gateway |
|:---:|:---|:---:|:---:|:---|
| 1 | `amount` | Float | $[1.0, \infty)$ | Transaction monetary value in INR ($\u20b9$). |
| 2 | `txn_count_24h` | Integer | $[0, \infty)$ | Velocity of transactions initiated by sender in the preceding 24 hours. |
| 3 | `device_change` | Binary | $\{0, 1\}$ | Boolean indicator: whether the payment was initiated from a new hardware fingerprint. |
| 4 | `location_anomaly` | Binary | $\{0, 1\}$ | Boolean indicator: whether the geo-IP / cellular cell tower deviates drastically from user history. |
| 5 | `receiver_suspicion_score` | Float | $[0.0, 1.0]$ | Prior cumulative fraud/chargeback probability associated with the receiver UPI ID. |
| 6 | `receiver_flagged` | Binary | $\{0, 1\}$ | Authoritative administrative blacklist flag on the receiver entity. |
| 7 | `user_avg_amount_30d` | Float | $[0.0, \infty)$ | Sender's 30-day historical mean expenditure per transaction. |
| 8 | `user_std_amount_30d` | Float | $[1.0, \infty)$ | Sender's 30-day transaction standard deviation (floored at 1.0 to prevent division by zero). |
| 9 | `amount_zscore` | Float | $(-\infty, \infty)$ | Statistical deviation: $\frac{\text{amount} - \mu_{30d}}{\sigma_{30d}}$. |
| 10 | `is_first_transaction` | Binary | $\{0, 1\}$ | Cold-start indicator: sender account's very first lifetime transaction. |
| 11 | `user_total_txn` | Integer | $[0, \infty)$ | Cumulative lifetime transactions completed by the sender account. |
| 12 | `account_age_hours` | Float | $[0.0, \infty)$ | Elapsed hours since the user registered their UPI profile. |
| 13 | `is_periodic_pattern` | Binary | $\{0, 1\}$ | Regularity indicator: recurring payments (salaries, subscriptions, rent). |
| 14 | `day_of_month` | Integer | $[1, 31]$ | Calendar day of transaction execution. |
| 15 | `relationship_stability_score` | Float | $[0.0, 1.0]$ | Ratio of past successful transactions between this exact sender-receiver pair. |
| 16 | `is_high_amount_global` | Binary | $\{0, 1\}$ | Platform-wide 95th percentile outlier threshold flag. |
| 17 | `amount_percentile_global` | Float | $[0.0, 1.0]$ | Cumulative distribution rank of transaction amount across the platform. |

Target Label: `is_fraud` (0 = Legitimate, 1 = Fraudulent).

---

## 3. PaySim Benchmark Mapping

### 3.1 Raw Dataset Characteristics
- **Source:** Kaggle / NTNU PaySim Mobile Money Simulator.
- **Volume:** ~6.36 million financial logs across 744 time steps (30 days of simulation).
- **Primary Columns:** `step`, `type` (`CASH_IN`, `CASH_OUT`, `DEBIT`, `PAYMENT`, `TRANSFER`), `amount`, `nameOrig`, `oldbalanceOrg`, `newbalanceOrig`, `nameDest`, `oldbalanceDest`, `newbalanceDest`, `isFraud`, `isFlaggedFraud`.

### 3.2 Transformation Pipeline

```
PaySim Raw Stream [step, type, amount, nameOrig, nameDest, isFraud]
       │
       ▼
Chronological Sorting (step ASC)
       │
       ├─► Rolling State Engine (nameOrig)
       │     ├─► User transaction count: user_total_txn = count(nameOrig)
       │     ├─► Cold-start flag: is_first_transaction = (count == 0)
       │     ├─► Sliding window (24 steps): txn_count_24h
       │     ├─► Expenditure history: user_avg_amount_30d, user_std_amount_30d
       │     └─► Z-Score calculation: z = (amount - avg) / max(1.0, std)
       │
       ├─► Counterparty Graph Matrix (nameOrig, nameDest)
       │     ├─► Pair interaction frequency: pair_count(nameOrig, nameDest)
       │     └─► relationship_stability_score = pair_count / (user_total_txn + 1)
       │
       ├─► Destination Reputation Matrix (nameDest)
       │     ├─► Prior fraud count / total receipts: receiver_suspicion_score
       │     └─► receiver_flagged = 1 if receiver_suspicion_score >= 0.50 else 0
       │
       └─► Hardware & Behavioral Proxies
             ├─► device_change: Transfer/Cash-out fraud proxy (Bernoulli p=0.75 if fraud else 0.05)
             ├─► location_anomaly: Cross-border proxy (Bernoulli p=0.65 if fraud else 0.04)
             └─► account_age_hours = (step - first_step_orig) + 24.0
```

---

## 4. IEEE-CIS Fraud Detection Mapping

### 4.1 Raw Dataset Characteristics
- **Source:** Vesta Corporation / IEEE Computational Intelligence Society.
- **Volume:** 590,540 transactions across 394 features.
- **Primary Columns:** `TransactionID`, `isFraud`, `TransactionDT`, `TransactionAmt`, `card1` (card identifier proxy), `addr1`, `addr2` (billing region), `dist1` (distance proxy), `C1..C14` (count aggregations), `D1..D15` (timedelta features).

### 4.2 Transformation Pipeline
1. **`amount`**: Directly mapped from `TransactionAmt`.
2. **`account_age_hours`**: Derived from feature `D1` (days between transaction and user registration):
   $$\text{account\_age\_hours} = \max(1.0, D1 \times 24.0)$$
3. **`txn_count_24h`**: Extracted from count feature `C1` (count of phone numbers/cards associated with payment) clamped to $[1, 20]$.
4. **`location_anomaly`**: Synthesized from `dist1 > 100` or mismatch between billing region (`addr1`) and operating cellular region.
5. **`device_change`**: Extracted from `DeviceInfo` or `id_30..38` operating system shifts; proxied with conditional distribution under fraud.
6. **`relationship_stability_score`**: Inferred from card-to-merchant repeat purchase frequency; set to $0.80$ for regular merchant transactions and $0.15$ for fraudulent attack events.

---

## 5. Limitations, Information Loss, and Operational Assumptions

1. **UPI-PIN Protocol vs. Card CVV/3DS:**
   - Public datasets originate from e-commerce (IEEE-CIS) or agent banking (PaySim). UPI transactions mandate 2-factor authentication at device-level (MPIN entered inside secure hardware enclave).
   - In real-world UPI, fraud manifests predominantly via **social engineering (phishing / remote screen sharing)** and **mule laundering networks**, whereas e-commerce fraud is dominated by **stolen credit card credentials**.
2. **Device Hardware Fingerprinting:**
   - IEEE-CIS and PaySim do not provide raw IMEI or Android KeyStore attestation hashes. ApexPay uses binary proxy indicators `device_change` and `location_anomaly` when running on public benchmarks.
3. **Receiver Identity Granularity:**
   - In PaySim, `nameDest` prefixes indicate whether the destination is a customer (`C`) or merchant (`M`). This allows robust receiver suspicion tracking, but lacks the structured Virtual Payment Address (VPA) hierarchy of UPI (e.g., `user@okaxis`, `merchant@icici`).

---

## 6. How to Run the Benchmark Mapper

The mapping utility `scripts/benchmark_dataset_mapping.py` can be executed directly from the command line:

```bash
# 1. Transform PaySim dataset
python scripts/benchmark_dataset_mapping.py \
    --dataset paysim \
    --input-file /path/to/PS_20174392719_1491204439457_log.csv \
    --output-file data/mapped_paysim_apexpay.csv

# 2. Transform IEEE-CIS dataset
python scripts/benchmark_dataset_mapping.py \
    --dataset ieee_cis \
    --input-file /path/to/train_transaction.csv \
    --output-file data/mapped_ieee_apexpay.csv

# 3. Run self-test pipeline with mock benchmark generator
python scripts/benchmark_dataset_mapping.py --dataset paysim --mock-test
python scripts/benchmark_dataset_mapping.py --dataset ieee_cis --mock-test
```
