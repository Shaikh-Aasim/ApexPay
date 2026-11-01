import numpy as np
import pandas as pd
from pathlib import Path
from typing import Tuple, Dict, List
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
        # Graph Scenarios (NEW)
        "graph_mule": [],
        "graph_ring": [],
        "graph_hub": [],
        # Edge Cases
        "edge_case_high_amount_legit": [],
        "edge_case_slight_anomaly": [],
        "edge_case_medium_risk": [],
        "edge_case_mixed_behavior": []
    }

    # Define User Profiles
    # (avg_amount, std_amount, total_txns, account_age)
    user_profiles = {
        "new_user": (500, 100, 1, 1),
        "regular_user": (2000, 400, 50, 2160), # 3 months
        "business_user": (15000, 3000, 500, 8760), # 1 year
        "risky_user": (3000, 1500, 20, 720) # 1 month, high variance
    }

    n_fraud = int(n_samples * fraud_ratio)
    n_normal = n_samples - n_fraud

    # Helper to add a row and track scenario
    def add_row(row_data: dict, label: int, scenario_key: str):
        idx = len(data)
        row_data["scenario_type"] = scenario_key
        data.append(row_data)
        labels.append(label)
        if scenario_key in scenario_indices:
            scenario_indices[scenario_key].append(idx)

    # Pre-define some fixed "bad actors" for graph scenarios to ensure clusters
    mule_receivers = [f"mule_target_{i}" for i in range(5)]
    hub_receivers = [f"hub_target_{i}" for i in range(5)]
    ring_sets = [[f"ring_{j}_user_{i}" for i in range(6)] for j in range(5)]

    # 1. GENERATE NORMAL CASES
    normal_scenarios = ["repayment", "salary", "regular", "high_legit", "trusted"]
    for _ in range(n_normal):
        case = rng.choice(normal_scenarios)
        profile_name = rng.choice(list(user_profiles.keys()))
        u_avg, u_std, u_txns, u_age = user_profiles[profile_name]
        
        # Add profile-based noise
        u_avg *= rng.uniform(0.8, 1.2)
        u_std *= rng.uniform(0.8, 1.2)

        sender = rng.choice(user_pool)
        receiver = rng.choice(user_pool)
        while receiver == sender:
            receiver = rng.choice(user_pool)

        if case == "repayment":
            amount = 2500.0 + rng.normal(0, 50)
            row = create_base_row(rng, amount, u_avg, u_std, sender=sender, receiver=receiver, periodic=True, stability=0.9, age=u_age, total_txn=u_txns)
            add_row(row, 0, "normal_repayment")
        elif case == "salary":
            amount = u_avg * 5 + rng.normal(0, 200)
            row = create_base_row(rng, amount, u_avg, u_std, sender=sender, receiver=receiver, periodic=True, stability=0.95, age=u_age, total_txn=u_txns)
            add_row(row, 0, "salary_incoming")
        elif case == "regular":
            amount = max(10, rng.normal(u_avg, u_std))
            row = create_base_row(rng, amount, u_avg, u_std, sender=sender, receiver=receiver, stability=rng.uniform(0.4, 0.7), age=u_age, total_txn=u_txns)
            add_row(row, 0, "regular_behavior")
        elif case == "high_legit":
            amount = rng.uniform(u_avg * 3, u_avg * 10)
            row = create_base_row(rng, amount, u_avg, u_std, sender=sender, receiver=receiver, stability=0.8, age=u_age, total_txn=u_txns)
            add_row(row, 0, "legit_high_value")
        elif case == "trusted":
            amount = rng.normal(u_avg, u_std)
            row = create_base_row(rng, amount, u_avg, u_std, sender=sender, receiver=receiver, stability=0.98, txns_24h=rng.integers(3, 8), age=u_age, total_txn=u_txns)
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
            # amount = rng.uniform(50000, 2000)
            amount = rng.uniform(50000, 1000000000) 
            row = create_base_row(rng, amount, 500, 100, sender=sender, receiver=receiver, first_txn=True, total_txn=1, age=0.5)
            add_row(row, 1, "fraud_first_txn")
        elif case == "ato":
            amount = rng.uniform(u_avg * 2, u_avg * 5)
            row = create_base_row(rng, amount, u_avg, u_std, sender=sender, receiver=receiver, device=1, location=1, age=u_age, total_txn=u_txns)
            add_row(row, 1, "fraud_ato")
        elif case == "velocity":
            amount = rng.uniform(100, 500)
            row = create_base_row(rng, amount, u_avg, u_std, sender=sender, receiver=receiver, txns_24h=rng.integers(13, 25), age=u_age, total_txn=u_txns)
            add_row(row, 1, "fraud_velocity")
        elif case == "zscore":
            amount = u_avg + (u_std * rng.uniform(2.5, 8))
            row = create_base_row(rng, amount, u_avg, u_std, sender=sender, receiver=receiver, age=u_age, total_txn=u_txns)
            add_row(row, 1, "fraud_high_zscore")
        elif case == "mule":
            amount = rng.uniform(1000, 5000)
            row = create_base_row(rng, amount, u_avg, u_std, sender=sender, receiver=receiver, flagged=1, suspicion=rng.uniform(0.7, 0.95), age=u_age, total_txn=u_txns)
            add_row(row, 1, "fraud_mule")
        elif case == "stealth":
            amount = rng.uniform(10, 50)
            row = create_base_row(rng, amount, u_avg, u_std, sender=sender, receiver=receiver, txns_24h=10, suspicion=0.4, age=u_age, total_txn=u_txns)
            add_row(row, 1, "stealth_fraud")
        elif case == "graph_mule":
            # Multiple senders to one receiver
            mule_receiver = rng.choice(mule_receivers)
            amount = rng.uniform(500, 2000)
            # Add some baseline suspicion
            row = create_base_row(rng, amount, u_avg, u_std, sender=sender, receiver=mule_receiver, stability=0.05, age=u_age, total_txn=u_txns, suspicion=0.4, device=0.5)
            add_row(row, 1, "graph_mule")
        elif case == "graph_ring":
            # Cycle pattern
            ring_users = rng.choice(ring_sets)
            u_idx = rng.integers(0, 6)
            sender = ring_users[u_idx]
            receiver = ring_users[(u_idx + 1) % 6]
            amount = rng.uniform(1000, 3000)
            # Add some baseline suspicion
            row = create_base_row(rng, amount, u_avg, u_std, sender=sender, receiver=receiver, stability=0.1, age=u_age, total_txn=u_txns, suspicion=0.3, location=0.5)
            add_row(row, 1, "graph_ring")
        elif case == "graph_hub":
            # High in-degree
            hub_receiver = rng.choice(hub_receivers)
            amount = rng.uniform(100, 500)
            # Add some baseline suspicion
            row = create_base_row(rng, amount, u_avg, u_std, sender=sender, receiver=hub_receiver, stability=0.02, age=u_age, total_txn=u_txns, suspicion=0.5)
            add_row(row, 1, "graph_hub")

    # 3. OVERWRITE SOME WITH EDGE CASES (to maintain total n_samples)
    edge_scenarios = ["high_legit_edge", "slight_anomaly", "medium_risk", "mixed"]
    n_edges = int(n_samples * 0.15) # 15% edge cases
    for _ in range(n_edges):
        case = rng.choice(edge_scenarios)
        profile_name = rng.choice(list(user_profiles.keys()))
        u_avg, u_std, u_txns, u_age = user_profiles[profile_name]
        
        # Randomly replace an existing sample to keep n_samples consistent
        replace_idx = rng.integers(0, len(data))
        
        if case == "high_legit_edge":
            amount = rng.uniform(50000, 150000)
            row = create_base_row(rng, amount, u_avg, u_std, periodic=True, stability=0.95, age=u_age, total_txn=u_txns)
            label = 0
            scenario = "edge_case_high_amount_legit"
        elif case == "slight_anomaly":
            amount = rng.normal(u_avg, u_std)
            row = create_base_row(rng, amount, u_avg, u_std, device=1, stability=0.8, age=u_age, total_txn=u_txns)
            label = 0
            scenario = "edge_case_slight_anomaly"
        elif case == "medium_risk":
            amount = u_avg * 3
            row = create_base_row(rng, amount, u_avg, u_std, device=1, suspicion=0.4, age=u_age, total_txn=u_txns)
            label = 0 # It's a "HOLD" case, technically normal but risky
            scenario = "edge_case_medium_risk"
        elif case == "mixed":
            amount = u_avg * 1.5
            row = create_base_row(rng, amount, u_avg, u_std, txns_24h=5, location=1, stability=0.4, age=u_age, total_txn=u_txns)
            label = rng.choice([0, 1]) # Could be either
            scenario = "edge_case_mixed_behavior"
        
        row["scenario_type"] = scenario
        data[replace_idx] = row
        labels[replace_idx] = label

    df = pd.DataFrame(data)
    y = np.array(labels)
    
    # Update scenario_indices after edge case replacements
    scenario_indices = {k: [] for k in scenario_indices}
    for i, row in df.iterrows():
        s_type = row["scenario_type"]
        if s_type in scenario_indices:
            scenario_indices[s_type].append(i)

    return df, y, scenario_indices

def create_base_row(rng, amount, u_avg, u_std, **kwargs):
    """Helper to create a standard feature row with overrides and Gaussian noise."""
    row = {
        "sender_id": kwargs.get("sender", "user_unknown"),
        "receiver_id": kwargs.get("receiver", "user_unknown"),
        "amount": max(1.0, amount),
        "txn_count_24h": float(kwargs.get("txns_24h", rng.integers(1, 4))),
        "device_change": float(kwargs.get("device", 0)),
        "location_anomaly": float(kwargs.get("location", 0)),
        "receiver_flagged": float(kwargs.get("flagged", 0)),
        "receiver_suspicion_score": float(kwargs.get("suspicion", rng.beta(2, 10))),
        "user_avg_amount_30d": u_avg,
        "user_std_amount_30d": u_std,
        # "amount_zscore": calculate_zscore(amount, u_avg, u_std),
        "amount_zscore": calculate_zscore(
    amount,
    u_avg,
    u_std,
    stability=kwargs.get("stability", 0),
    periodic=kwargs.get("periodic", False)
),
        "is_first_transaction": float(kwargs.get("first_txn", False)),
        "user_total_txn": float(kwargs.get("total_txn", rng.integers(10, 500))),
        "account_age_hours": float(kwargs.get("age", rng.uniform(24, 8760))),
        "is_periodic_pattern": float(kwargs.get("periodic", False)),
        "day_of_month": float(rng.integers(1, 31)),
        "relationship_stability_score": float(kwargs.get("stability", rng.uniform(0.1, 0.6))),
        "is_high_amount_global": 1.0 if amount > 65000 else 0.0,
        "amount_percentile_global": rng.uniform(0.1, 0.9)
    }
    
    # Add Gaussian noise to all numerical fields for realism
    # and to create overlap between classes
    noise_factor = 0.06 # 2% noise
    for key in row:
        if isinstance(row[key], float) and key not in ["device_change", "location_anomaly", "receiver_flagged", "is_first_transaction", "is_periodic_pattern", "is_high_amount_global", "amount_zscore",
        "user_avg_amount_30d",          # 🔥 ADD THIS
        "user_std_amount_30d"   ]:
            row[key] += rng.normal(0, abs(row[key]) * noise_factor)
            
    return row

def generate_large_scale_test_suite():
    """Generates and saves the large scale test datasets."""
    output_path = "test_data_large.csv"
    # if Path(output_path).exists():
    #     print(f"\n[INFO] Using existing large scale test data at {output_path}")
    #     return output_path
        
    print("\nGenerating Large Scale Test Suite (10k-15k samples)...")
    
    # 1. Balanced Dataset (50% Fraud, 50% Normal)
    df_balanced, y_balanced, _ = generate_test_dataset(n_samples=50000, fraud_ratio=0.5, seed=101)
    df_balanced['label'] = y_balanced
    
    # 2. Realistic Dataset (10% Fraud, 90% Normal)
    df_realistic, y_realistic, _ = generate_test_dataset(n_samples=50000, fraud_ratio=0.1, seed=202)
    df_realistic['label'] = y_realistic
    
    # Combine or save separately
    df_full = pd.concat([df_balanced, df_realistic]).reset_index(drop=True)
    
    # Save to CSV
    output_path = "test_data_large.csv"
    df_full.to_csv(output_path, index=False)
    print(f"Successfully saved {len(df_full)} samples to {output_path}")
    
    return output_path

if __name__ == "__main__":
    generate_large_scale_test_suite()
