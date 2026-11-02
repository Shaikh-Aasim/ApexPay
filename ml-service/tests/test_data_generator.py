import numpy as np
import pandas as pd
from pathlib import Path
from typing import Tuple, Dict, List
import sys

# Ensure root is in path
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from utils.features import calculate_zscore

def generate_test_dataset(n_samples: int = 3000, fraud_ratio: float = 0.3, seed: int = 99) -> Tuple[pd.DataFrame, np.ndarray, Dict[str, List[int]]]:
    """
    Generates an advanced synthetic dataset with specific scenarios and edge cases.
    
    Args:
        n_samples: Total number of samples to generate.
        fraud_ratio: Proportion of fraud cases (0.0 to 1.0).
        seed: Random seed for reproducibility.
        
    Returns:
        df: The feature dataframe with scenario_type column.
        y: The ground truth labels.
        scenarios: A mapping of scenario names to row indices.
    """
    rng = np.random.default_rng(seed)
    data = []
    labels = []
    
    # Define Pool of Users
    user_pool = [f"user_{i}" for i in range(2000)]
    
    scenario_indices = {
        # Normal Scenarios
        "normal_repayment": [],
        "salary_incoming": [],
        "regular_behavior": [],
        "legit_high_value": [],
        "trusted_relationships": [],
        # Fraud Scenarios
        "fraud_first_txn": [],
        "fraud_ato": [],
        "fraud_velocity": [],
        "fraud_high_zscore": [],
        "fraud_mule": [],
        "stealth_fraud": [],
        # Graph Scenarios
        "graph_mule": [],
        "graph_ring": [],
        "graph_hub": [],
        # Edge Cases
        "edge_case_high_amount_legit": [],
        "edge_case_slight_anomaly": [],
        "edge_case_medium_risk": [],
        "edge_case_mixed_behavior": []
    }

    # Define User Profiles (avg_amount, std_amount, total_txns, account_age)
    user_profiles = {
        "new_user": (800, 200, 1, 1),
        "regular_user": (2500, 500, 50, 2160),      # 3 months
        "business_user": (25000, 6000, 500, 8760),  # 1 year
        "risky_user": (3500, 1800, 20, 720)         # 1 month, high variance
    }

    n_fraud = int(n_samples * fraud_ratio)
    n_normal = n_samples - n_fraud

    def add_row(row_data: dict, label: int, scenario_key: str):
        idx = len(data)
        row_data["scenario_type"] = scenario_key
        data.append(row_data)
        labels.append(label)
        if scenario_key in scenario_indices:
            scenario_indices[scenario_key].append(idx)

    # Pre-define fixed bad actors for graph clusters
    mule_receivers = [f"mule_target_{i}" for i in range(5)]
    hub_receivers = [f"hub_target_{i}" for i in range(5)]
    ring_sets = [[f"ring_{j}_user_{i}" for i in range(6)] for j in range(5)]

    # 1. GENERATE NORMAL CASES
    normal_scenarios = ["repayment", "salary", "regular", "high_legit", "trusted"]
    for _ in range(n_normal):
        case = rng.choice(normal_scenarios)
        profile_name = rng.choice(list(user_profiles.keys()))
        u_avg, u_std, u_txns, u_age = user_profiles[profile_name]
        
        u_avg *= rng.uniform(0.85, 1.15)
        u_std *= rng.uniform(0.85, 1.15)

        sender = rng.choice(user_pool)
        receiver = rng.choice(user_pool)
        while receiver == sender:
            receiver = rng.choice(user_pool)

        if case == "repayment":
            amount = 2500.0 + rng.normal(0, 50)
            row = create_base_row(rng, amount, u_avg, u_std, sender=sender, receiver=receiver, periodic=True, stability=0.9, age=u_age, total_txn=u_txns)
            add_row(row, 0, "normal_repayment")
        elif case == "salary":
            amount = u_avg * 3.5 + rng.normal(0, 200)
            row = create_base_row(rng, amount, u_avg, u_std, sender=sender, receiver=receiver, periodic=True, stability=0.95, age=u_age, total_txn=u_txns)
            add_row(row, 0, "salary_incoming")
        elif case == "regular":
            amount = max(10, rng.normal(u_avg, u_std))
            row = create_base_row(rng, amount, u_avg, u_std, sender=sender, receiver=receiver, stability=rng.uniform(0.4, 0.7), age=u_age, total_txn=u_txns)
            add_row(row, 0, "regular_behavior")
        elif case == "high_legit":
            amount = rng.uniform(u_avg * 2.5, u_avg * 6.0)
            row = create_base_row(rng, amount, u_avg, u_std, sender=sender, receiver=receiver, stability=0.82, age=u_age, total_txn=u_txns)
            add_row(row, 0, "legit_high_value")
        elif case == "trusted":
            amount = rng.normal(u_avg, u_std)
            row = create_base_row(rng, amount, u_avg, u_std, sender=sender, receiver=receiver, stability=0.98, txns_24h=rng.integers(2, 6), age=u_age, total_txn=u_txns)
            add_row(row, 0, "trusted_relationships")

    # 2. GENERATE FRAUD CASES
    fraud_scenarios = ["first_txn", "ato", "velocity", "zscore", "mule", "stealth", "graph_mule", "graph_ring", "graph_hub"]
    for _ in range(n_fraud):
        case = rng.choice(fraud_scenarios)
        profile_name = rng.choice(list(user_profiles.keys()))
        u_avg, u_std, u_txns, u_age = user_profiles[profile_name]

        sender = rng.choice(user_pool)
        receiver = rng.choice(user_pool)
        while receiver == sender:
            receiver = rng.choice(user_pool)

        if case == "first_txn":
            # Realistic cold-start drain transfer
            amount = rng.uniform(65000, 180000)
            row = create_base_row(rng, amount, 800, 200, sender=sender, receiver=receiver, first_txn=True, total_txn=1, age=0.5)
            add_row(row, 1, "fraud_first_txn")
        elif case == "ato":
            amount = rng.uniform(u_avg * 2.5, u_avg * 6)
            row = create_base_row(rng, amount, u_avg, u_std, sender=sender, receiver=receiver, device=1.0, location=1.0, age=u_age, total_txn=u_txns)
            add_row(row, 1, "fraud_ato")
        elif case == "velocity":
            amount = rng.uniform(200, 1000)
            row = create_base_row(rng, amount, u_avg, u_std, sender=sender, receiver=receiver, txns_24h=rng.integers(12, 25), age=u_age, total_txn=u_txns)
            add_row(row, 1, "fraud_velocity")
        elif case == "zscore":
            amount = u_avg + (u_std * rng.uniform(3.0, 7.0))
            row = create_base_row(rng, amount, u_avg, u_std, sender=sender, receiver=receiver, age=u_age, total_txn=u_txns)
            add_row(row, 1, "fraud_high_zscore")
        elif case == "mule":
            amount = rng.uniform(15000, 45000)
            row = create_base_row(rng, amount, u_avg, u_std, sender=sender, receiver=receiver, flagged=1.0, suspicion=rng.uniform(0.75, 0.98), age=u_age, total_txn=u_txns)
            add_row(row, 1, "fraud_mule")
        elif case == "stealth":
            amount = rng.uniform(50, 400)
            row = create_base_row(rng, amount, u_avg, u_std, sender=sender, receiver=receiver, txns_24h=8, suspicion=0.45, age=u_age, total_txn=u_txns)
            add_row(row, 1, "stealth_fraud")
        elif case == "graph_mule":
            mule_receiver = rng.choice(mule_receivers)
            amount = rng.uniform(800, 2500)
            device_flag = 1.0 if rng.random() < 0.5 else 0.0
            row = create_base_row(rng, amount, u_avg, u_std, sender=sender, receiver=mule_receiver, stability=0.05, age=u_age, total_txn=u_txns, suspicion=0.45, device=device_flag)
            add_row(row, 1, "graph_mule")
        elif case == "graph_ring":
            ring_users = rng.choice(ring_sets)
            u_idx = rng.integers(0, 6)
            sender = ring_users[u_idx]
            receiver = ring_users[(u_idx + 1) % 6]
            amount = rng.uniform(1500, 4500)
            loc_flag = 1.0 if rng.random() < 0.5 else 0.0
            row = create_base_row(rng, amount, u_avg, u_std, sender=sender, receiver=receiver, stability=0.08, age=u_age, total_txn=u_txns, suspicion=0.35, location=loc_flag)
            add_row(row, 1, "graph_ring")
        elif case == "graph_hub":
            hub_receiver = rng.choice(hub_receivers)
            amount = rng.uniform(200, 800)
            row = create_base_row(rng, amount, u_avg, u_std, sender=sender, receiver=hub_receiver, stability=0.02, age=u_age, total_txn=u_txns, suspicion=0.55)
            add_row(row, 1, "graph_hub")

    # 3. REALISTIC EDGE CASES
    edge_scenarios = ["high_legit_edge", "slight_anomaly", "medium_risk", "mixed"]
    n_edges = int(n_samples * 0.12)
    for _ in range(n_edges):
        case = rng.choice(edge_scenarios)
        profile_name = rng.choice(list(user_profiles.keys()))
        u_avg, u_std, u_txns, u_age = user_profiles[profile_name]
        
        replace_idx = rng.integers(0, len(data))
        
        if case == "high_legit_edge":
            amount = rng.uniform(40000, 100000)
            row = create_base_row(rng, amount, u_avg, u_std, periodic=True, stability=0.92, age=u_age, total_txn=u_txns)
            label = 0
            scenario = "edge_case_high_amount_legit"
        elif case == "slight_anomaly":
            amount = rng.normal(u_avg, u_std)
            row = create_base_row(rng, amount, u_avg, u_std, device=1.0, stability=0.85, age=u_age, total_txn=u_txns)
            label = 0
            scenario = "edge_case_slight_anomaly"
        elif case == "medium_risk":
            amount = u_avg * 2.8
            row = create_base_row(rng, amount, u_avg, u_std, device=1.0, suspicion=0.4, age=u_age, total_txn=u_txns)
            label = 0  # Hold / OTP candidate, ground-truth not malicious
            scenario = "edge_case_medium_risk"
        elif case == "mixed":
            amount = u_avg * 1.8
            loc_flag = 1.0 if rng.random() < 0.5 else 0.0
            row = create_base_row(rng, amount, u_avg, u_std, txns_24h=4, location=loc_flag, stability=0.45, age=u_age, total_txn=u_txns)
            label = rng.choice([0, 1])
            scenario = "edge_case_mixed_behavior"
        
        row["scenario_type"] = scenario
        data[replace_idx] = row
        labels[replace_idx] = label

    df = pd.DataFrame(data)
    y = np.array(labels)
    
    groups = df.groupby("scenario_type").groups
    scenario_indices = {k: groups.get(k, pd.Index([])).tolist() for k in scenario_indices}

    return df, y, scenario_indices

def create_base_row(rng, amount, u_avg, u_std, **kwargs):
    """Helper to create a standard feature row with overrides and mathematical consistency."""
    base_amount = max(1.0, float(amount))
    
    # Apply small realistic noise to amount
    noisy_amount = max(1.0, base_amount * (1 + rng.normal(0, 0.03)))
    
    stability = float(kwargs.get("stability", rng.uniform(0.1, 0.6)))
    periodic = bool(kwargs.get("periodic", False))
    
    # Canonical calculation of zscore using the final amount
    zscore = calculate_zscore(noisy_amount, u_avg, u_std, stability=stability, periodic=periodic)
    
    # Strictly enforce binary flags: 0.0 or 1.0 (No fractional floats like 0.5)
    device_val = 1.0 if float(kwargs.get("device", 0)) >= 0.5 else 0.0
    loc_val = 1.0 if float(kwargs.get("location", 0)) >= 0.5 else 0.0
    flagged_val = 1.0 if float(kwargs.get("flagged", 0)) >= 0.5 else 0.0
    first_val = 1.0 if bool(kwargs.get("first_txn", False)) else 0.0
    periodic_val = 1.0 if periodic else 0.0
    is_high_val = 1.0 if noisy_amount > 50000 else 0.0

    row = {
        "sender_id": kwargs.get("sender", "user_unknown"),
        "receiver_id": kwargs.get("receiver", "user_unknown"),
        "amount": round(noisy_amount, 2),
        "txn_count_24h": float(max(1, int(kwargs.get("txns_24h", rng.integers(1, 4))))),
        "device_change": device_val,
        "location_anomaly": loc_val,
        "receiver_flagged": flagged_val,
        "receiver_suspicion_score": float(max(0.0, min(1.0, kwargs.get("suspicion", rng.beta(2, 10))))),
        "user_avg_amount_30d": float(u_avg),
        "user_std_amount_30d": float(u_std),
        "amount_zscore": float(zscore),
        "is_first_transaction": first_val,
        "user_total_txn": float(kwargs.get("total_txn", rng.integers(10, 500))),
        "account_age_hours": float(kwargs.get("age", rng.uniform(24, 8760))),
        "is_periodic_pattern": periodic_val,
        "day_of_month": float(rng.integers(1, 31)),
        "relationship_stability_score": float(max(0.0, min(1.0, stability))),
        "is_high_amount_global": is_high_val,
        "amount_percentile_global": float(max(0.0, min(1.0, noisy_amount / 80000.0)))
    }
    return row

def generate_large_scale_test_suite():
    """Generates and saves the canonical large scale test datasets."""
    output_path = ROOT / "test_data_large.csv"
    print(f"\nGenerating Canonical Large Scale Dataset (50,000 samples)...")
    
    # Balanced Dataset (50% Fraud, 50% Normal)
    df_balanced, y_balanced, _ = generate_test_dataset(n_samples=25000, fraud_ratio=0.5, seed=101)
    df_balanced['label'] = y_balanced
    
    # Realistic Dataset (10% Fraud, 90% Normal)
    df_realistic, y_realistic, _ = generate_test_dataset(n_samples=25000, fraud_ratio=0.1, seed=202)
    df_realistic['label'] = y_realistic
    
    df_full = pd.concat([df_balanced, df_realistic]).sample(frac=1, random_state=42).reset_index(drop=True)
    df_full.to_csv(output_path, index=False)
    print(f"Successfully saved {len(df_full)} samples to {output_path}")
    return str(output_path)

if __name__ == "__main__":
    generate_large_scale_test_suite()
