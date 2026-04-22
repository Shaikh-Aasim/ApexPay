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
    if x < 0:
        return 0.0
    if x > 1:
        return 1.0
    return x


def heuristic_risk(
    *,
    amount: float,
    amount_zscore: float,
    device_change: int,
    location_anomaly: int,
    txn_count_24h: int,
    receiver_suspicion_score: float,
    receiver_flagged: int,
) -> HeuristicResult:
    score = 0.0
    reasons: List[str] = []

    if amount >= 25000:
        score += 0.25
        reasons.append("High transfer amount")
    elif amount >= 10000:
        score += 0.12
        reasons.append("Elevated transfer amount")

    if abs(amount_zscore) >= 2.5:
        score += 0.25
        reasons.append("Unusual amount vs your recent history")
    elif abs(amount_zscore) >= 1.5:
        score += 0.12
        reasons.append("Slightly unusual amount vs your recent history")

    if txn_count_24h >= 12:
        score += 0.20
        reasons.append("High transaction frequency in last 24h")
    elif txn_count_24h >= 6:
        score += 0.10
        reasons.append("Elevated transaction frequency in last 24h")

    if device_change == 1:
        score += 0.15
        reasons.append("New device detected")

    if location_anomaly == 1:
        score += 0.15
        reasons.append("Unusual location pattern")

    if receiver_flagged == 1:
        score += 0.30
        reasons.append("Receiver is flagged as suspicious")
    else:
        score += 0.10 * clamp01(receiver_suspicion_score)
        if receiver_suspicion_score >= 0.7:
            reasons.append("Receiver has suspicious history")

    score = clamp01(score)

    if score < 0.30:
        decision = "LOW"
    elif score < 0.70:
        decision = "MEDIUM"
    else:
        decision = "HIGH"

    if receiver_flagged == 1:
        fraud_type = "MULE_ACCOUNT"
    elif device_change == 1 and location_anomaly == 1:
        fraud_type = "ACCOUNT_TAKEOVER"
    elif abs(amount_zscore) >= 2.5:
        fraud_type = "PHISHING"
    else:
        fraud_type = "UNKNOWN"

    return HeuristicResult(risk_score=score, decision=decision, reasons=reasons or ["No strong risk signals"], fraud_type=fraud_type)

