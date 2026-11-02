# ApexPay ML Service API Reference & Integration Guide

## 1. Service Overview & Base Configuration

The ApexPay ML Service is a high-performance RESTful API implemented using FastAPI and Pydantic v2. It provides synchronous, low-latency pre-settlement fraud evaluation for the Node.js core banking backend.

- **Default Port:** `8000`
- **Base URL:** `http://127.0.0.1:8000`
- **Interactive OpenAPI Documentation:** `http://127.0.0.1:8000/docs`
- **ReDoc Documentation:** `http://127.0.0.1:8000/redoc`

---

## 2. API Endpoints

### 2.1 Service Health Check

#### `GET /health`
Verifies that the API service is active and reports the loaded machine learning model version.

- **Request:** None
- **Response Headers:** `Content-Type: application/json`
- **Response Status:** `200 OK`

```json
{
  "status": "ok",
  "model_version": "2.2.0"
}
```

---

### 2.2 Model Metrics & Evaluation Metadata

#### `GET /metrics`
Returns serialized cross-validation scores, hold-out test set accuracy, threshold calibration tables, and operational performance metrics.

- **Request:** None
- **Response Status:** `200 OK` (or `404 Not Found` if model has not been trained)

```json
{
  "model_version": "2.2.0",
  "trained_at": "2026-11-02T13:25:00Z",
  "cv_5fold_f1_mean": 0.9735,
  "test_metrics": {
    "accuracy": 0.9854,
    "precision": 0.9614,
    "recall": 0.9875,
    "f1_score": 0.9743,
    "decision_threshold": 0.45
  },
  "training_sample_count": 50000,
  "features": [
    "amount", "txn_count_24h", "device_change", "location_anomaly",
    "receiver_suspicion_score", "receiver_flagged", "user_avg_amount_30d",
    "user_std_amount_30d", "amount_zscore", "is_first_transaction",
    "user_total_txn", "account_age_hours", "is_periodic_pattern",
    "day_of_month", "relationship_stability_score", "is_high_amount_global",
    "amount_percentile_global"
  ]
}
```

---

### 2.3 Real-Time Fraud & Risk Scoring

#### `POST /predict-risk`
Executes synchronous 3-layer risk evaluation (ML + Heuristic Rules + Graph Intelligence).

- **Request Headers:** `Content-Type: application/json`
- **Response Status:** `200 OK`

#### Request Payload Schema (`RiskRequest`):

| Field | Type | Required | Description |
|---|:---:|:---:|---|
| `sender_id` | String | Optional | Unique account identifier of payer (e.g., `user_c1001`). |
| `receiver_id` | String | Optional | Unique account identifier of payee (e.g., `user_m5002`). |
| `transaction_id` | String | Optional | Unique UUID for idempotency and graph deduplication. |
| `amount` | Float | **Yes** | Transaction value in INR ($> 0$). |
| `txn_count_24h` | Integer | Optional (def: 1) | Payer velocity over the previous 24 hours. |
| `device_change` | Integer | Optional (def: 0) | Binary flag: $1$ if device hardware changed, else $0$. |
| `location_anomaly` | Integer | Optional (def: 0) | Binary flag: $1$ if location is anomalous, else $0$. |
| `receiver_suspicion_score`| Float | Optional (def: 0.0)| Destination historical fraud rate $[0.0, 1.0]$. |
| `receiver_flagged` | Integer | Optional (def: 0) | $1$ if receiver is on blacklist, else $0$. |
| `user_avg_amount_30d` | Float | Optional (def: 0.0)| Payer 30-day mean transaction value. |
| `user_std_amount_30d` | Float | Optional (def: 0.0)| Payer 30-day standard deviation. |
| `amount_zscore` | Float | Optional (def: 0.0)| Statistical deviation: $\frac{\text{amount} - \mu}{\sigma}$. |
| `is_first_transaction` | Boolean | Optional (def: false)| $true$ if this is payer's first lifetime transfer. |
| `user_total_txn` | Integer | Optional (def: 0) | Total lifetime transactions by payer. |
| `account_age_hours` | Float | Optional (def: 720)| Payer account age in elapsed hours. |
| `receiver_is_first_transaction`| Boolean | Optional (def: false)| $true$ if this is payee's first transaction. |
| `receiver_account_age_hours` | Float | Optional (def: 720)| Payee account age in elapsed hours. |
| `relationship_stability_score`| Float | Optional (def: 0.5)| Ratio of past transfers between this pair $[0.0, 1.0]$. |
| `is_periodic_pattern` | Boolean | Optional (def: false)| $true$ if regular recurring payment. |
| `day_of_month` | Integer | Optional (def: 1) | Day of month $[1, 31]$. |
| `is_high_amount_global` | Boolean | Optional (def: false)| $true$ if $\ge$ platform 95th percentile. |
| `amount_percentile_global`| Float | Optional (def: 0.0)| Cumulative rank in platform distribution. |

#### Response Payload Schema (`RiskResponse`):

```json
{
  "risk_score": 0.1250,
  "combined_risk_score": 0.1250,
  "ml_probability": 0.0421,
  "rule_score": 0.0800,
  "graph_score": 0.0500,
  "decision": "LOW",
  "reasons": [
    "Normal expenditure within user historical baseline",
    "Known counterparty with high stability score"
  ],
  "fraud_type": "UNKNOWN",
  "model_version": "2.2.0"
}
```

---

## 3. Real-World Decision Examples

### Example A: Legitimate Everyday Payment (Decision: `LOW`)
```bash
curl -X POST "http://127.0.0.1:8000/predict-risk" \
  -H "Content-Type: application/json" \
  -d '{
    "sender_id": "usr_rahul_9912",
    "receiver_id": "usr_ananya_3321",
    "amount": 450.0,
    "amount_zscore": 0.25,
    "txn_count_24h": 2,
    "device_change": 0,
    "location_anomaly": 0,
    "relationship_stability_score": 0.85
  }'
```
**Response:**
```json
{
  "risk_score": 0.0450,
  "combined_risk_score": 0.0450,
  "ml_probability": 0.0125,
  "rule_score": 0.0000,
  "graph_score": 0.0200,
  "decision": "LOW",
  "reasons": ["Normal transaction profile", "Established counterparty relationship"],
  "fraud_type": "UNKNOWN",
  "model_version": "2.2.0"
}
```

---

### Example B: Unfamiliar Transfer Requiring Step-Up (Decision: `MEDIUM`)
```bash
curl -X POST "http://127.0.0.1:8000/predict-risk" \
  -H "Content-Type: application/json" \
  -d '{
    "sender_id": "usr_vikram_4421",
    "receiver_id": "usr_newmerchant_8891",
    "amount": 12500.0,
    "amount_zscore": 2.85,
    "txn_count_24h": 4,
    "device_change": 0,
    "location_anomaly": 1,
    "relationship_stability_score": 0.00
  }'
```
**Response:**
```json
{
  "risk_score": 0.5820,
  "combined_risk_score": 0.5820,
  "ml_probability": 0.4850,
  "rule_score": 0.5500,
  "graph_score": 0.3500,
  "decision": "MEDIUM",
  "reasons": [
    "Elevated amount Z-score (>2.5) relative to 30-day baseline",
    "First interaction with unfamiliar counterparty",
    "Location anomaly detected"
  ],
  "fraud_type": "UNKNOWN",
  "model_version": "2.2.0"
}
```

---

### Example C: Coordinated Account Takeover (Decision: `HIGH`)
```bash
curl -X POST "http://127.0.0.1:8000/predict-risk" \
  -H "Content-Type: application/json" \
  -d '{
    "sender_id": "usr_compromised_1102",
    "receiver_id": "usr_mule_7761",
    "amount": 48000.0,
    "amount_zscore": 8.42,
    "txn_count_24h": 7,
    "device_change": 1,
    "location_anomaly": 1,
    "relationship_stability_score": 0.00,
    "receiver_suspicion_score": 0.85
  }'
```
**Response:**
```json
{
  "risk_score": 0.9500,
  "combined_risk_score": 0.9500,
  "ml_probability": 0.9840,
  "rule_score": 0.9500,
  "graph_score": 1.0000,
  "decision": "HIGH",
  "reasons": [
    "Critical Account Takeover / Extreme Deviation Detected",
    "Severe amount Z-score anomaly (>8.0)",
    "Simultaneous hardware and location displacement on unverified counterparty"
  ],
  "fraud_type": "ACCOUNT_TAKEOVER",
  "model_version": "2.2.0"
}
```

---

## 4. Node.js Backend Integration

The ApexPay Node.js backend communicates with the ML Service via `backend/services/mlService.ts`:

```typescript
import { predictRisk } from "./mlService";

// In payment settlement flow:
const riskAssessment = await predictRisk({
  sender_id: sender.userId,
  receiver_id: receiver.userId,
  amount: payment.amount,
  txn_count_24h: senderStats.velocity24h,
  device_change: isNewDevice ? 1 : 0,
  location_anomaly: isLocationAnomaly ? 1 : 0,
  receiver_suspicion_score: receiver.riskScore,
  receiver_flagged: receiver.isBlacklisted ? 1 : 0,
  user_avg_amount_30d: senderStats.mean30d,
  user_std_amount_30d: senderStats.std30d,
  amount_zscore: calculatedZScore,
  relationship_stability_score: pairStabilityScore
});

if (riskAssessment.decision === "HIGH") {
  throw new PaymentBlockedError(riskAssessment.reasons.join("; "));
} else if (riskAssessment.decision === "MEDIUM") {
  return initiateStepUpChallenge(payment.id);
} else {
  return executeImmediateSettlement(payment.id);
}
```
