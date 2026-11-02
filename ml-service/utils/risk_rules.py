from __future__ import annotations
from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class HeuristicResult:
    risk_score: float
    decision: str
    reasons: List[str]
    fraud_type: str

def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))

def heuristic_risk(
    *,
    amount: float,
    amount_zscore: float,
    device_change: int,
    location_anomaly: int,
    txn_count_24h: int,
    receiver_suspicion_score: float,
    receiver_flagged: int,
    is_first_transaction: bool = False,
    account_age_hours: float = 720.0,
    is_periodic_pattern: bool = False,
    relationship_stability: float = 0.5,
    threshold_first_txn: float = 5000.0
) -> HeuristicResult:
    """
    Robust Real-World Heuristic Fraud Engine:
    Evaluates multi-dimensional risk signals (amount, deviation, velocity, credentials,
    receiver reputation, account lifecycle, and counterparty stability).
    
    Produces:
    - risk_score: strictly clamped in [0.0, 1.0]
    - decision: 'LOW' (approve), 'MEDIUM' (challenge / OTP), or 'HIGH' (block)
    - reasons: human-auditable risk explanations
    - fraud_type: strictly aligned with payment platform taxonomy
    """
    score = 0.0
    reasons: List[str] = []
    fraud_type = "UNKNOWN"

    # =========================================================================
    # 1. AMOUNT BASELINE (Tiered financial exposure)
    # =========================================================================
    if amount >= 100000:
        score += 0.28
        reasons.append("Very high transfer amount (>= 100k)")
    elif amount >= 50000:
        score += 0.20
        reasons.append("High transfer amount (>= 50k)")
    elif amount >= 20000:
        score += 0.12
        reasons.append("Elevated transfer amount (>= 20k)")
    elif amount >= 10000:
        score += 0.06
        reasons.append("Moderate transfer amount (>= 10k)")

    # =========================================================================
    # 2. STATISTICAL DEVIATION (Dynamic baseline comparison via Z-Score)
    # =========================================================================
    abs_z = abs(amount_zscore)
    if abs_z >= 4.0:
        score += 0.35
        reasons.append("Extreme deviation from 30-day baseline (|z| >= 4.0)")
        fraud_type = "PHISHING"
    elif abs_z >= 2.5:
        score += 0.25
        reasons.append("Significant deviation from 30-day baseline (|z| >= 2.5)")
        if fraud_type == "UNKNOWN":
            fraud_type = "PHISHING"
    elif abs_z >= 1.5:
        score += 0.15
        reasons.append("Noticeable deviation from recent spending pattern (|z| >= 1.5)")

    # =========================================================================
    # 3. VELOCITY CHECKS (Rapid transaction bursts)
    # =========================================================================
    if txn_count_24h >= 15:
        score += 0.35
        reasons.append(f"Extreme transaction velocity ({txn_count_24h} in 24h)")
        if fraud_type == "UNKNOWN":
            fraud_type = "ACCOUNT_TAKEOVER"
    elif txn_count_24h >= 8:
        score += 0.22
        reasons.append(f"High transaction frequency ({txn_count_24h} in 24h)")
    elif txn_count_24h >= 4:
        score += 0.10
        reasons.append(f"Elevated transaction frequency ({txn_count_24h} in 24h)")

    # =========================================================================
    # 4. CREDENTIAL & ENVIRONMENT ANOMALIES (Device & Geolocation)
    # =========================================================================
    if device_change == 1 and location_anomaly == 1:
        score += 0.35
        reasons.append("Dual environment anomaly: Unrecognized device AND location jump")
        fraud_type = "ACCOUNT_TAKEOVER"
    elif device_change == 1:
        score += 0.14
        reasons.append("New unrecognized device detected")
    elif location_anomaly == 1:
        score += 0.14
        reasons.append("Unusual geolocation pattern detected")

    # =========================================================================
    # 5. RECEIVER REPUTATION & MULE RISKS
    # =========================================================================
    if receiver_flagged == 1:
        score += 0.55
        reasons.append("Receiver account is flagged on security blacklist")
        fraud_type = "MULE_ACCOUNT"
    else:
        norm_suspicion = clamp01(receiver_suspicion_score)
        if norm_suspicion >= 0.70:
            score += 0.28
            reasons.append(f"Receiver has high historical suspicion score ({norm_suspicion:.2f})")
            if fraud_type == "UNKNOWN":
                fraud_type = "MULE_ACCOUNT"
        elif norm_suspicion >= 0.40:
            score += 0.14
            reasons.append(f"Receiver has moderate suspicion score ({norm_suspicion:.2f})")

    # =========================================================================
    # 6. ACCOUNT LIFECYCLE & COLD-START (New Account & First Transaction)
    # =========================================================================
    if is_first_transaction:
        if amount >= 60000:
            score += 0.40
            reasons.append("First transaction with critical high value (>= 60k)")
            fraud_type = "FIRST_TXN_HIGH_AMOUNT"
        elif amount > threshold_first_txn:
            score += 0.20
            reasons.append(f"First transaction with elevated amount (requires step-up hold)")
            if fraud_type == "UNKNOWN":
                fraud_type = "FIRST_TXN_HIGH_AMOUNT"
        else:
            score += 0.08
            reasons.append("First transaction for user account")

    if account_age_hours < 24:
        if amount >= 40000:
            score += 0.30
            reasons.append("New account (< 24 hours old) with high-value transfer")
        else:
            score += 0.12
            reasons.append("New account (< 24 hours old)")

    # =========================================================================
    # 7. COMPOUND ATTACK SIGNATURES (Corroborated Multi-Vector Threats)
    # =========================================================================
    # Account Takeover Drain signature
    if (device_change == 1 or location_anomaly == 1) and amount >= 30000 and abs_z >= 2.0:
        score += 0.25
        reasons.append("Compound threat: Environment change combined with large baseline anomaly")
        fraud_type = "ACCOUNT_TAKEOVER"

    # Rapid high-volume burst
    if txn_count_24h >= 8 and amount >= 20000:
        score += 0.20
        reasons.append("Compound threat: High velocity coupled with substantial amount")

    # Velocity to suspicious receiver (smurfing / funneling)
    if txn_count_24h >= 6 and (receiver_flagged == 1 or receiver_suspicion_score >= 0.6):
        score += 0.25
        reasons.append("Rapid funneling to suspicious counterparty")
        fraud_type = "MULE_ACCOUNT"

    # =========================================================================
    # 8. FALSE-POSITIVE MITIGATION (Discounts for Legitimate Patterns)
    # =========================================================================
    # Periodic / Recurring transactions (Rent, Utilities, EMI, Salaries)
    if is_periodic_pattern and score < 0.70:
        score -= 0.18
        reasons.append("Periodic recurring pattern confirmed (Legitimacy Discount)")

    # Counterparty relationship stability
    if relationship_stability > 0.75 and receiver_flagged == 0:
        score -= 0.20
        reasons.append("High relationship stability with trusted counterparty (Legitimacy Discount)")
    elif relationship_stability > 0.50 and receiver_flagged == 0:
        score -= 0.08
        reasons.append("Familiar counterparty history")

    # Clamping raw accumulated score to [0.0, 1.0]
    score = clamp01(score)

    # =========================================================================
    # 9. REAL-WORLD DECISION MATRIX & CRITICAL OVERRIDES
    # =========================================================================
    # Default decision based on calibrated bands:
    # LOW:    [0.00, 0.40) -> Approve immediately
    # MEDIUM: [0.40, 0.75) -> Step-up authentication (OTP Challenge)
    # HIGH:   [0.75, 1.00] -> Block / Reject
    if score < 0.40:
        decision = "LOW"
    elif score < 0.75:
        decision = "MEDIUM"
    else:
        decision = "HIGH"

    # --- CRITICAL HIGH OVERRIDES (Non-negotiable blocks) ---
    if receiver_flagged == 1 and amount >= 15000:
        decision = "HIGH"
        score = max(score, 0.95)
        reasons.append("CRITICAL: Significant transfer directed to flagged mule account")
        fraud_type = "MULE_ACCOUNT"

    elif device_change == 1 and location_anomaly == 1 and (amount >= 20000 or abs_z >= 2.5):
        decision = "HIGH"
        score = max(score, 0.92)
        reasons.append("CRITICAL: Verified Account Takeover pattern (credential breach)")
        fraud_type = "ACCOUNT_TAKEOVER"

    elif is_first_transaction and amount >= 60000:
        decision = "HIGH"
        score = max(score, 0.90)
        reasons.append("CRITICAL: New user first transaction exceeds safety ceiling (>= 60k)")
        fraud_type = "FIRST_TXN_HIGH_AMOUNT"

    elif txn_count_24h >= 8 and amount >= 20000 and (device_change == 1 or location_anomaly == 1):
        decision = "HIGH"
        score = max(score, 0.95)
        reasons.append("CRITICAL: Coordinated high-velocity attack with environmental shift")
        fraud_type = "ACCOUNT_TAKEOVER"

    elif abs_z >= 7.0 and relationship_stability < 0.35:
        decision = "HIGH"
        score = max(score, 0.95)
        reasons.append("CRITICAL: Extreme statistical drain to unfamiliar counterparty")
        fraud_type = "PHISHING"

    # --- SAFETY MEDIUM OVERRIDES (Hold for OTP step-up instead of blind pass) ---
    elif decision == "LOW":
        # Cold-start new user first transaction: Never outright block, but challenge with OTP
        if is_first_transaction and amount > threshold_first_txn:
            decision = "MEDIUM"
            score = max(score, 0.48)
            reasons.append("New user cold-start: Step-up verification required")
            fraud_type = "FIRST_TXN_HIGH_AMOUNT"

        # Velocity burst safeguard: 10+ transactions within 24 hours
        elif txn_count_24h >= 10 and not is_periodic_pattern:
            decision = "MEDIUM"
            score = max(score, 0.48)
            reasons.append(f"Velocity burst safeguard ({txn_count_24h} in 24h): Step-up verification required")
            if fraud_type == "UNKNOWN":
                fraud_type = "ACCOUNT_TAKEOVER"

        # Environmental anomaly on notable transfer
        elif (device_change == 1 or location_anomaly == 1) and (amount >= 15000 or abs_z >= 2.0):
            decision = "MEDIUM"
            score = max(score, 0.50)
            reasons.append("Security challenge: Unfamiliar environment on significant transfer")

        # Untrusted / suspicious receiver
        elif receiver_suspicion_score >= 0.70 and amount >= 5000:
            decision = "MEDIUM"
            score = max(score, 0.55)
            reasons.append("Security challenge: Receiver has elevated suspicion history")
            if fraud_type == "UNKNOWN":
                fraud_type = "MULE_ACCOUNT"

    return HeuristicResult(
        risk_score=round(score, 4),
        decision=decision,
        reasons=reasons or ["Normal transaction behavior"],
        fraud_type=fraud_type
    )
