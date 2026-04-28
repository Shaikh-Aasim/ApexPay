import pandas as pd
import numpy as np
from pathlib import Path

def generate_mini_dataset(output_path="test_data_mini.csv", n_samples=1000):
    """
    Generates a fast, targeted dataset for Graph Intelligence validation.
    Distribution: 60% Normal, 40% Fraud.
    """
    print(f"Generating mini dataset: {n_samples} samples...")
    rng = np.random.default_rng(42)
    
    data = []
    
    # 1. PRE-DEFINE ACTORS
    mule_receivers = [f"mule_rcv_{i}" for i in range(3)]
    hub_users = [f"hub_user_{i}" for i in range(2)]
    large_ring = [f"ring_user_{i}" for i in range(7)]
    small_family = [f"fam_{i}" for i in range(3)]
    
    def add_case(sender, receiver, amount, stability, suspicion, label, scenario, 
                 device=0, location=0, age=720, txn_24h=1):
        data.append({
            "sender_id": sender,
            "receiver_id": receiver,
            "amount": amount,
            "amount_zscore": (amount - 500) / 200 if amount > 500 else 0,
            "device_change": device,
            "location_anomaly": location,
            "txn_count_24h": txn_24h,
            "receiver_suspicion_score": suspicion,
            "receiver_flagged": 1 if suspicion > 0.7 else 0,
            "is_first_transaction": 0,
            "account_age_hours": age,
            "is_periodic_pattern": 1 if "repayment" in scenario else 0,
            "relationship_stability": stability,
            "label": label,
            "scenario": scenario
        })

    # --- NORMAL CASES (60% = 600 samples) ---
    for _ in range(200):
        # Monthly Repayment
        add_case(f"user_{rng.integers(1000, 2000)}", "utility_co", rng.uniform(50, 200), 0.9, 0.0, 0, "normal_repayment")
    for _ in range(200):
        # Salary
        add_case("corp_hr", f"user_{rng.integers(1000, 2000)}", rng.uniform(3000, 5000), 0.95, 0.0, 0, "salary")
    for _ in range(100):
        # Family Transfers (Small cycles, high stability)
        s, r = rng.choice(small_family, 2, replace=False)
        add_case(s, r, rng.uniform(100, 500), 0.85, 0.0, 0, "family_transfer")
    for _ in range(100):
        # Edge Case: High amount but trusted
        add_case(f"user_{rng.integers(2000, 3000)}", f"user_{rng.integers(3000, 4000)}", 8000, 0.9, 0.1, 0, "edge_trusted_high")

    # --- FRAUD CASES (40% = 400 samples) ---
    for _ in range(150):
        # Mule: Many users -> One receiver
        sender = f"mule_snd_{rng.integers(0, 100)}"
        receiver = rng.choice(mule_receivers)
        add_case(sender, receiver, rng.uniform(800, 1500), 0.05, 0.4, 1, "graph_mule", device=1)
    for _ in range(150):
        # Fraud Ring: Cycle 7 nodes
        idx = rng.integers(0, 7)
        sender = large_ring[idx]
        receiver = large_ring[(idx + 1) % 7]
        add_case(sender, receiver, rng.uniform(1000, 3000), 0.1, 0.3, 1, "graph_ring", location=1)
    for _ in range(100):
        # Suspicious Hub
        sender = f"user_{rng.integers(5000, 6000)}"
        receiver = rng.choice(hub_users)
        add_case(sender, receiver, rng.uniform(100, 300), 0.02, 0.6, 1, "graph_hub")

    df = pd.DataFrame(data)
    df.to_csv(output_path, index=False)
    print(f"Mini dataset saved to {output_path}")
    return output_path

if __name__ == "__main__":
    generate_mini_dataset()
