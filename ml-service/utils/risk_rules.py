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
    return max(0.0, min(1.0, x))

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
    account_age_hours: float = 0.0,
    is_periodic_pattern: bool = False,
    threshold_first_txn: float = 5000.0
) -> HeuristicResult:
    score = 0.0
    reasons: List[str] = []
    fraud_type = "UNKNOWN"

    # 1. Base amount risks
    if amount >= 25000:
        score += 0.25
        reasons.append("High transfer amount")
    elif amount >= 10000:
        score += 0.12
        reasons.append("Elevated transfer amount")

    # 2. Statistical anomaly (ENHANCED for stealth detection)
    if abs(amount_zscore) >= 2.5:
        score += 0.35
        reasons.append("Highly unusual amount vs recent history")
        fraud_type = "PHISHING"
    elif abs(amount_zscore) >= 1.5:
        score += 0.20
        reasons.append("Unusual transaction deviation")

    # 3. Velocity checks
    if txn_count_24h >= 12:
        score += 0.30
        reasons.append("High transaction frequency (24h)")
        fraud_type = "VELOCITY"
    elif txn_count_24h >= 6:
        score += 0.15
        reasons.append("Elevated transaction frequency")

    # 4. Security signals
    if device_change == 1:
        score += 0.15
        reasons.append("New device detected")
    if location_anomaly == 1:
        score += 0.15
        reasons.append("Unusual location pattern")
    
    if device_change == 1 and location_anomaly == 1:
        fraud_type = "ACCOUNT_TAKEOVER"

    # 5. Receiver risks
    if receiver_flagged == 1:
        score += 0.50 # Significant boost
        reasons.append("Receiver is flagged as suspicious")
        fraud_type = "MULE_ACCOUNT"
    else:
        score += 0.15 * clamp01(receiver_suspicion_score)
        if receiver_suspicion_score >= 0.7:
            reasons.append("Receiver has suspicious history")

    # 6. New User Context (Special Rules)
    if is_first_transaction:
        if amount > threshold_first_txn:
            # We'll handle the "MEDIUM risk (HOLD)" in the final decision logic
            # but we add a reason here.
            score += 0.20
            reasons.append("First transaction with high amount (requires hold)")
        else:
            score += 0.10
            reasons.append("First transaction for this user")

    if account_age_hours < 24:
        score += 0.10
        reasons.append("Very new account (< 24h)")

    # 7. Pattern Recognition (False Positive Reduction)
    if is_periodic_pattern:
        score -= 0.25
        reasons.append("Periodic transaction pattern detected (Reduced Risk)")

    score = clamp01(score)

    # Final Decision based on score
    if score < 0.35:
        decision = "LOW"
    elif score < 0.75:
        decision = "MEDIUM"
    else:
        decision = "HIGH"

    # Rule overrides
    if receiver_flagged == 1:
        decision = "HIGH"
        score = max(score, 0.9)
    
    if is_first_transaction and amount > threshold_first_txn:
        # Special rule: First txn + high amount -> MEDIUM (HOLD)
        if decision == "LOW":
            decision = "MEDIUM"
            score = max(score, 0.5)

    return HeuristicResult(
        risk_score=score,
        decision=decision,
        reasons=reasons or ["No strong risk signals"],
        fraud_type=fraud_type
    )
