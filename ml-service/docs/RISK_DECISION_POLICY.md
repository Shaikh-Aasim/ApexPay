# ApexPay Risk Decision Policy & Scoring Governance

## 1. Executive Summary & Policy Objectives

ApexPay operates an intelligent, three-tier risk governance policy designed to balance the security of real-time UPI payments against user payment friction. The objective is to maximize fraud capture (Recall $> 98\%$) while maintaining a minimal False Positive Rate ($< 1.0\%$) to protect legitimate user transaction flow.

The system outputs three authoritative decisions:
- **`LOW` (Auto-Approve):** Immediate settlement without user friction.
- **`MEDIUM` (Step-Up Authentication):** Transaction held; requires secondary out-of-band verification (SMS OTP / Biometric / MPIN confirmation).
- **`HIGH` (Block / Immediate Rejection):** Transaction blocked; counterparty investigation triggered.

---

## 2. Decision Score Bands & Categorization

The integrated risk score $S \in [0.0, 1.0]$ is categorized into distinct operational bands:

```
┌─────────────────────────────────┬─────────────────────────────────┬────────────────────────┐
│              LOW                │             MEDIUM              │          HIGH          │
│         [0.00 - 0.42)           │          [0.42 - 0.75)          │     [0.75 - 1.00]      │
├─────────────────────────────────┼─────────────────────────────────┼────────────────────────┤
│ Immediate Approval              │ Step-Up Challenge (OTP)         │ Hard Block / Reject    │
│ Zero User Friction              │ Hold for Verification           │ Prevent Settlement     │
│ Standard Audit Logging          │ 60-second Challenge Window      │ Risk Incident Created  │
└─────────────────────────────────┴─────────────────────────────────┴────────────────────────┘
```

### 2.1 LOW Risk Band ($0.00 \le S < 0.42$)
- **Action:** Pre-settlement approval is granted instantaneously ($< 20\text{ ms}$).
- **Target Profile:** Familiar counterparty, typical amount within $1.5\sigma$ of personal historical baseline, verified trusted device, normal time-of-day.
- **User Experience:** Seamless payment flow; no additional authentication steps beyond standard UPI MPIN.

### 2.2 MEDIUM Risk Band ($0.42 \le S < 0.75$)
- **Action:** Gateway places transaction in `HOLD_FOR_VERIFICATION` status.
- **Target Profile:** Single moderate anomaly (e.g., first-time transfer to an unflagged receiver, user traveling to an unfamiliar city, moderate velocity spike).
- **User Experience:** An interactive step-up challenge is issued to the mobile application. If verified within 60 seconds, the payment proceeds to settlement; otherwise, it is safely canceled.

### 2.3 HIGH Risk Band ($0.75 \le S \le 1.00$)
- **Action:** Transaction is immediately declined with an explicit fraud notification.
- **Target Profile:** Coordinated attack vectors, confirmed money mule funnels, circular laundering rings, or multi-signal account takeovers.
- **User Experience:** User is informed of the security hold with clear customer-support escalation instructions.

---

## 3. Multi-Signal Confirmation Matrix

Financial fraud rarely occurs in isolation. Isolated anomalies (such as purchasing a flight ticket from an airport) often represent legitimate lifestyle events. To eliminate false-positive rejections, ApexPay enforces a **Multi-Signal Confirmation Policy**:

### 3.1 Monitored Signal Register

| Signal Identifier | Trigger Threshold | Primary Indication |
|---|---|---|
| `high_zscore` | $|Z| \ge 1.5$ relative to 30-day baseline | Unusual transaction expenditure spike |
| `device_change` | Hardware fingerprint $\neq$ registered history | Potential credential theft or SIM swap |
| `location_anomaly` | Geo-IP or cellular cell delta $> 500\text{ km}$ | Unfamiliar geographic environment |
| `velocity_flag` | $\text{txn\_count\_24h} \ge 5$ | Rapid funds dissipation or automated script |
| `receiver_risk` | `receiver_flagged == 1` OR suspicion $\ge 0.70$ | Counterparty with prior chargeback history |
| `graph_risk` | Computed `graph_score` $\ge 0.35$ | Topological proximity to suspicious entities |
| `first_txn_elevated` | First transaction AND amount $\ge \u20b910,000$ | Cold-start ceiling vulnerability |

### 3.2 Confirmation Rules
1. **Isolated Signal Dampening:**
   If only **one** risk signal is present (Signal Count $= 1$) and the ML probability is below $0.80$, the transaction **cannot** be given a `HIGH` block. It is capped at `MEDIUM`, requiring step-up OTP rather than being outright rejected.
2. **Two-Signal Escalation:**
   If **two or more** distinct signals confirm each other (e.g., `device_change` AND `location_anomaly`), and the counterparty is unfamiliar (`relationship_stability < 0.40`), the decision automatically escalates to `HIGH`.

---

## 4. Hard Security Overrides

Certain critical fraud conditions bypass statistical averaging and trigger **non-negotiable hard blocks**:

```
                                  Incoming Transaction
                                           │
       ┌───────────────────────────────────┼───────────────────────────────────┐
       ▼                                   ▼                                   ▼
[Critical ATO Override]         [Mule Funnel Override]              [Blacklist Override]
Z-Score > 8.0                   Senders in 24h >= 10                receiver_flagged == 1
OR (New Device + Distant Loc    Structural Risk = 0.95              Direct Rule HIGH
+ Unstable Recipient + >10k)    Action: HIGH                        Action: HIGH
Action: HIGH
```

1. **Critical Account Takeover (ATO):**
   - Condition: $Z > 8.0$ OR (`device_change == 1` AND `location_anomaly == 1` AND `relationship_stability < 0.40` AND $\text{amount} \ge \u20b910,000$).
   - Decision: Immediate `HIGH` ($S = 0.95$), `fraud_type = ACCOUNT_TAKEOVER`.
2. **Critical Money Mule Aggregation:**
   - Condition: Receiver has $\ge 10$ unique senders in the preceding 24 hours.
   - Decision: Immediate `HIGH` ($S = 0.95$), `fraud_type = MULE_ACCOUNT`.
3. **Administrative Blacklist:**
   - Condition: Destination receiver UPI ID is flagged in the authoritative fraud registry.
   - Decision: Immediate `HIGH` ($S = 1.00$).

---

## 5. False Positive Protection & Customer Experience

To prevent frustrating legitimate account holders:
1. **Relationship Stability Discount:**
   - When a user sends money to a known, stable contact (`relationship_stability_score > 0.75`), graph-derived risk is suppressed by $75\%$ and heuristic risk is reduced by up to $60\%$.
2. **Periodic Pattern Recognition:**
   - Transactions identified as recurring (salary disbursements, rent, scheduled utility payments) on expected calendar days are automatically shielded from velocity and amount penalties.
3. **Social Bill-Splitting Triangle Exemption:**
   - Small, 3-node cyclic payment patterns ($A \to B \to C \to A$) are classified as social triangles with negligible risk ($0.05$), distinguishing them from laundering rings.

---

## 6. Dispute Resolution and Risk Decay

- **Temporal Risk Decay:** Flagged counterparty risk decays exponentially with a 14-day half-life. If an account has no suspicious activities for 30 days, its neighbor risk contagion drops below $0.05$.
- **Customer Remediation:** Upon customer identity re-verification, the operational status of the account is reset via administrative API, purging temporary graph risk flags.
