import pandas as pd
import numpy as np
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from utils.features import calculate_zscore

def generate_mini_dataset(output_path="test_data_mini.csv", n_samples=1000):
    """
    Generates a fast, targeted dataset for Graph Intelligence validation.
    Distribution: 60% Normal, 40% Fraud.
    Includes all canonical 17 features with consistent naming.
    """
    print(f"Generating mini dataset: {n_samples} samples...")
    rng = np.random.default_rng(42)
    
    data = []
    
    # Pre-define actors
    mule_receivers = [f"mule_rcv_{i}" for i in range(3)]
    hub_users = [f"hub_user_{i}" for i in range(2)]
    large_ring = [f"ring_user_{i}" for i in range(7)]
    small_family = [f"fam_{i}" for i in range(3)]
    
    def add_case(sender, receiver, amount, stability, suspicion, label, scenario, 
                 device=0.0, location=0.0, age=720.0, txn_24h=1.0, u_avg=2000.0, u_std=500.0, first_txn=0.0):
        
        is_periodic = 1.0 if ("repayment" in scenario or "salary" in scenario) else 0.0
        zscore = calculate_zscore(amount, u_avg, u_std, stability=stability, periodic=(is_periodic == 1.0))
        
        data.append({
            "sender_id": sender,
            "receiver_id": receiver,
            "amount": float(amount),
            "txn_count_24h": float(txn_24h),
            "device_change": float(device),
            "location_anomaly": float(location),
            "receiver_flagged": 1.0 if suspicion > 0.7 else 0.0,
            "receiver_suspicion_score": float(suspicion),
            "user_avg_amount_30d": float(u_avg),
            "user_std_amount_30d": float(u_std),
            "amount_zscore": float(zscore),
            "is_first_transaction": float(first_txn),
            "user_total_txn": 1.0 if first_txn else float(rng.integers(10, 200)),
            "account_age_hours": float(age),
            "is_periodic_pattern": is_periodic,
            "day_of_month": float(rng.integers(1, 28)),
            "relationship_stability_score": float(stability),
            "is_high_amount_global": 1.0 if amount > 50000 else 0.0,
            "amount_percentile_global": float(min(1.0, amount / 80000.0)),
            "scenario": scenario,
            "scenario_type": scenario,
            "label": int(label)
        })

    # --- NORMAL CASES (60% = 600 samples) ---
    for _ in range(200):
        # Monthly Repayment
        add_case(f"user_{rng.integers(1000, 2000)}", "utility_co", rng.uniform(500, 2500), 0.90, 0.0, 0, "normal_repayment", u_avg=2000)
    for _ in range(200):
        # Salary
        add_case("corp_hr", f"user_{rng.integers(1000, 2000)}", rng.uniform(15000, 45000), 0.95, 0.0, 0, "salary", u_avg=25000)
    for _ in range(100):
        # Family Transfers (Small cycles, high stability)
        s, r = rng.choice(small_family, 2, replace=False)
        add_case(s, r, rng.uniform(200, 1500), 0.85, 0.0, 0, "family_transfer", u_avg=1000)
    for _ in range(100):
        # Edge Case: High amount but trusted
        add_case(f"user_{rng.integers(2000, 3000)}", f"user_{rng.integers(3000, 4000)}", 18000, 0.90, 0.05, 0, "edge_trusted_high", u_avg=15000)

    # --- FRAUD CASES (40% = 400 samples) ---
    for _ in range(150):
        # Mule: Many users -> One receiver
        sender = f"mule_snd_{rng.integers(0, 100)}"
        receiver = rng.choice(mule_receivers)
        add_case(sender, receiver, rng.uniform(800, 3500), 0.05, 0.45, 1, "graph_mule", device=1.0)
    for _ in range(150):
        # Fraud Ring: Cycle 7 nodes
        idx = rng.integers(0, 7)
        sender = large_ring[idx]
        receiver = large_ring[(idx + 1) % 7]
        add_case(sender, receiver, rng.uniform(2000, 5000), 0.10, 0.35, 1, "graph_ring", location=1.0)
    for _ in range(100):
        # Suspicious Hub
        sender = f"user_{rng.integers(5000, 6000)}"
        receiver = rng.choice(hub_users)
        add_case(sender, receiver, rng.uniform(300, 1200), 0.02, 0.65, 1, "graph_hub")

    df = pd.DataFrame(data)
    save_path = ROOT / output_path if not Path(output_path).is_absolute() else Path(output_path)
    df.to_csv(save_path, index=False)
    print(f"Mini dataset saved to {save_path} with {len(df.columns)} columns")
    return str(save_path)

if __name__ == "__main__":
    generate_mini_dataset()
