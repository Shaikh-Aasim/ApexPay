from __future__ import annotations
from typing import List
import numpy as np

# List of all features used by the model
FEATURES: List[str] = [
    # Existing features
    "amount",
    "txn_count_24h",
    "device_change",
    "location_anomaly",
    "receiver_flagged",
    "receiver_suspicion_score",
    "user_avg_amount_30d",
    "user_std_amount_30d",
    "amount_zscore",
    
    # New User Context features
    "is_first_transaction",
    "user_total_txn",
    "account_age_hours",
    
    # New Pattern Features
    "is_periodic_pattern",
    "day_of_month",
    "relationship_stability_score",
    
    # New Global Risk Features
    "is_high_amount_global",
    "amount_percentile_global"
]

def calculate_zscore(amount: float, avg: float, std: float, stability: float = 0.0, periodic: float = 0.0) -> float:
    """
    Balanced z-score:
    - Handles std=0 safely
    - Reduces extreme deviations (prevents FP)
    - Preserves relative anomaly signal (keeps FN stable)
    """
    # Safe std
    if std <= 0:
        diff = abs(amount - avg)
        if diff < 1.0:
            return 0.0
        return 1.5

    # Log transform (reduces skew)
    amount = max(amount, 0)
    avg = max(avg, 0)

    amount_log = np.log1p(amount)
    avg_log = np.log1p(avg)

    # Scale std proportionally
    std_log = std / (avg + 1e-3)

    z = (amount_log - avg_log) / max(std_log, 1e-3)

    # Soft clipping
    z = np.tanh(z / 3) * 5

    # Reduce FP for stable/periodic behavior
    if stability > 0.8 or periodic:
        z *= 0.6
    return float(z)

def get_feature_vector(data: dict) -> List[float]:
    """Converts input dictionary to a feature vector for the model with null-safety."""
    vector = []
    for feature in FEATURES:
        val = data.get(feature, 0.0)
        if val is None:
            val = 0.0
        elif isinstance(val, bool):
            val = 1.0 if val else 0.0
        vector.append(float(val))
    return vector
