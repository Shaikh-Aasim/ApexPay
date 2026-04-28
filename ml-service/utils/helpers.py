from __future__ import annotations
import numpy as np
from typing import List

def safe_divide(a: float, b: float) -> float:
    """Safely divides a by b, returning 0 if b is 0."""
    return a / b if b != 0 else 0.0

def normalize_features(X: np.ndarray) -> np.ndarray:
    """Simple min-max normalization for a feature matrix."""
    min_vals = X.min(axis=0)
    max_vals = X.max(axis=0)
    range_vals = max_vals - min_vals
    # Avoid division by zero
    range_vals[range_vals == 0] = 1.0
    return (X - min_vals) / range_vals

def calculate_relationship_stability(interactions: int, total_txn: int) -> float:
    """Calculates stability score based on interactions between sender and receiver."""
    if total_txn <= 0:
        return 0.0
    return min(1.0, interactions / total_txn)
