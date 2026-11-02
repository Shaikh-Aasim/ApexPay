# ApexPay Fraud Dataset Generation & Simulation Methodology

## 1. Rationale and Principles

Training machine learning models for payment fraud presents unique challenges:
1. **Confidentiality & Privacy:** Banking regulations (e.g., RBI guidelines, GDPR) strictly prohibit the public exposure of genuine consumer banking records, mobile numbers, and bank account numbers.
2. **Extreme Class Imbalance:** Real-world payment fraud represents $< 0.1\%$ of total network traffic. Pure random sampling would result in insufficient positive examples for model training.
3. **Behavioral Diversity:** Fraudsters continuously evolve their tactics (credential stuffing, SIM swap, remote screen sharing, mule fan-ins, circular laundering).

To address these requirements, ApexPay implements a high-fidelity, statistically grounded **Synthetic Transaction Simulator** (`tests/test_data_generator.py`). The simulator models legitimate consumer spending habits and sophisticated adversarial attack vectors with exact mathematical distributions.

---

## 2. Statistical Distributions & Sampling Mechanics

Financial transaction features do not adhere to Gaussian distributions. ApexPay models payment parameters using empirical financial distributions:

### 2.1 Transaction Monetary Values (`amount`)
Legitimate payment amounts are modeled using piecewise **Lognormal Distributions**:
$$X \sim \text{Lognormal}(\mu, \sigma^2), \quad f(x) = \frac{1}{x \sigma \sqrt{2\pi}} \exp\left(-\frac{(\ln x - \mu)^2}{2\sigma^2}\right)$$

- **Micro-Payments (Tea stalls, groceries, metro):** $\mu = 4.2, \sigma = 0.6 \implies \text{Median} \approx \u20b966, \text{Range} \in [\u20b910, \u20b9500]$.
- **Standard Retail / Utilities:** $\mu = 7.1, \sigma = 0.8 \implies \text{Median} \approx \u20b91,200, \text{Range} \in [\u20b9300, \u20b98,000]$.
- **High-Value P2P Transfers:** $\mu = 9.5, \sigma = 0.9 \implies \text{Median} \approx \u20b913,300, \text{Range} \in [\u20b95,000, \u20b91,00,000]$.

### 2.2 Transaction Velocities (`txn_count_24h`)
Discrete event counts are generated using **Poisson** and **Negative Binomial** processes:
- **Normal Users:** $k \sim \text{Poisson}(\lambda = 1.8)$, modeling 1 to 4 daily transactions.
- **Velocity Attack / Smurfing:** $k \sim \text{Poisson}(\lambda = 12.0) + 5$, modeling burst frequencies between 8 and 25 transactions per day.

### 2.3 Account Age (`account_age_hours`)
User lifespans follow an **Exponential Distribution**:
$$T \sim \text{Exp}(\lambda = 0.001), \quad \text{clamped to } [1.0, 8760.0 \text{ hours (1 year)}]$$

---

## 3. Fraud Scenario Specifications

The generator synthesizes distinct financial scenarios with structured parameter boundaries:

| Scenario Code | Scenario Name | Target Label | Amount Distribution | Velocity ($24\text{h}$) | Device Shift | Location Anomaly | Relationship Stability | Primary Modality |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|---|
| `LEGIT_NORMAL` | Standard Everyday UPI | 0 | $\text{Lognormal}(5.5, 0.7)$ | 1–4 | 0 (97%) | 0 (98%) | $[0.40, 0.95]$ | Normal baseline |
| `LEGIT_TRAVEL` | User Traveling (Vacation) | 0 | $\text{Lognormal}(6.8, 0.8)$ | 2–6 | 0 | **1 (100%)** | $[0.20, 0.60]$ | False positive buffer |
| `LEGIT_NEW_DEVICE` | User Upgraded Phone | 0 | $\text{Lognormal}(5.8, 0.6)$ | 1–3 | **1 (100%)** | 0 | $[0.70, 0.98]$ | False positive buffer |
| `LEGIT_SALARY_RENT` | Periodic High Value | 0 | $\u20b915,000 - \u20b980,000$ | 1–2 | 0 | 0 | $[0.85, 1.00]$ | Periodic pattern exception |
| `FRAUD_ATO` | Account Takeover | 1 | $\u20b925,000 - \u20b91,00,000$ | 4–12 | **1 (100%)** | **1 (100%)** | $[0.00, 0.15]$ | Extreme deviation ($Z > 4.0$) |
| `FRAUD_MULE_FANIN` | Money Mule Funnel | 1 | $\u20b91,000 - \u20b910,000$ | 8–25 | 0 or 1 | 0 or 1 | $[0.00, 0.10]$ | High-in degree aggregation |
| `FRAUD_PHISHING` | Social Engineering | 1 | $\u20b910,000 - \u20b950,000$ | 1–3 | 0 (user device) | 0 | $[0.00, 0.05]$ | Suspicious receiver reputation |
| `FRAUD_RING` | Circular Laundering | 1 | $\u20b95,000 - \u20b940,000$ | 5–15 | 0 or 1 | 0 or 1 | $[0.05, 0.30]$ | Multi-hop directed cycles |
| `FRAUD_FIRST_TXN` | Cold-Start High Amount | 1 | $\u20b950,000 - \u20b91,00,000$ | 1 | 1 (60%) | 1 (50%) | $0.00$ | First transaction max amount |

---

## 4. Leakage Elimination and Integrity Controls

To guarantee that the synthetic dataset produces models that generalize reliably to real-world data:

1. **Recalculated Statistical Moments:**
   In early iterations of the codebase, noisy amounts were sampled after computing user mean ($\mu$) and standard deviation ($\sigma$), resulting in statistical leakage. The pipeline now explicitly computes:
   $$\text{amount\_zscore} = \frac{\text{amount}_{\text{final}} - \mu_{30d}}{\max(1.0, \sigma_{30d})}$$
   ensuring strict algebraic consistency across every row.

2. **Clean Discrete Binary Types:**
   Binary features (`device_change`, `location_anomaly`, `receiver_flagged`, `is_first_transaction`, `is_periodic_pattern`, `is_high_amount_global`) are strictly constrained to $\{0, 1\}$ integer or boolean types, eliminating fractional artifact noise.

3. **Global Threshold Consistency:**
   `is_high_amount_global` is determined dynamically by calculating the empirical 95th percentile ($P_{95}$) across all sampled transactions, ensuring that global anomaly features are statistically synchronized.

---

## 5. Dataset Generation Command

To reproduce the canonical 50,000-sample training dataset:

```bash
# Generate 50,000-sample balanced dataset
python tests/test_data_generator.py

# Output: test_data_large.csv (50,000 rows, 17 features + target label)
```
