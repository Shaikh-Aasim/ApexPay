from __future__ import annotations
from typing import List

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

def calculate_zscore(amount: float, avg: float, std: float) -> float:
    """
    Safely calculates z-score with fallback logic.
    If std is 0, we check if the amount is exactly the average.
    If it's significantly different from the average even with 0 std, 
    we assign a moderate 'virtual' z-score of 1.5 to indicate slight risk.
    """
    if std <= 0:
        # Fallback: if amount is close to avg, zscore is 0. 
        # If it's different, we flag it as slightly unusual.
        diff = abs(amount - avg)
        if diff < 1.0: # Basically the same
            return 0.0
        return 1.5 # Moderate risk fallback
    return (amount - avg) / std

def get_feature_vector(data: dict) -> List[float]:
    """Converts input dictionary to a feature vector for the model."""
    vector = []
    for feature in FEATURES:
        val = data.get(feature, 0.0)
        # Convert boolean to float
        if isinstance(val, bool):
            val = 1.0 if val else 0.0
        vector.append(float(val))
    return vector
