import pandas as pd
import numpy as np
from pathlib import Path
import time
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from utils.features import calculate_zscore

def generate_graph_test_data(mode="MINI", output_path=None):
    """
    Generates structured scenario-based data for Graph Intelligence validation.
    
    Modes:
    - MINI: 1000 samples
    - FULL: 12000 samples
    
    Includes all 17 canonical features for seamless model evaluation.
    """
    n_samples = 1000 if mode == "MINI" else 12000
    if output_path is None:
        output_path = ROOT / f"graph_test_data_{mode.lower()}.csv"
    else:
        output_path = Path(output_path)
        
    print(f"Generating {mode} dataset: {n_samples} samples...")
    start_time = time.time()
    rng = np.random.default_rng(42)
    
    data = []
    
    # Pre-define actors for graph scenarios
    mule_receivers = [f"mule_rcv_{i}" for i in range(5 if mode == "MINI" else 20)]
    hub_users = [f"hub_user_{i}" for i in range(3 if mode == "MINI" else 15)]
    large_rings = [[f"ring_{r}_user_{i}" for i in range(rng.integers(6, 9))] for r in range(2 if mode == "MINI" else 10)]
    small_families = [[f"fam_{f}_user_{i}" for i in range(3)] for f in range(5 if mode == "MINI" else 50)]
    
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

    # --- 1. NORMAL CASES (60%) ---
    n_normal = int(n_samples * 0.6)
    
    # Salary
    for _ in range(int(n_normal * 0.3)):
        add_case("corp_hr", f"user_{rng.integers(1000, 5000)}", rng.uniform(20000, 55000), 0.95, 0.0, 0, "salary", u_avg=30000)
        
    # Monthly Repayments
    for _ in range(int(n_normal * 0.3)):
        add_case(f"user_{rng.integers(1000, 5000)}", "utility_co", rng.uniform(500, 3000), 0.90, 0.0, 0, "monthly_repayment", u_avg=2000)
        
    # Family Transfers (Small Cycles / High Stability)
    for _ in range(int(n_normal * 0.2)):
        fam_idx = rng.integers(0, len(small_families))
        fam = small_families[fam_idx]
        s, r = rng.choice(fam, 2, replace=False)
        add_case(s, r, rng.uniform(200, 1500), 0.85, 0.0, 0, "family_transfer", u_avg=1000)
        
    # Trusted Relationships
    for _ in range(int(n_normal * 0.2)):
        add_case(f"user_{rng.integers(1000, 5000)}", f"user_{rng.integers(5000, 9000)}", rng.uniform(500, 3500), 0.80, 0.0, 0, "trusted_transfer", u_avg=2000)

    # --- 2. GRAPH FRAUD CASES (30%) ---
    n_fraud = int(n_samples * 0.3)
    
    # Mule: 10+ users -> 1 receiver
    for _ in range(int(n_fraud * 0.4)):
        receiver = rng.choice(mule_receivers)
        sender = f"mule_snd_{rng.integers(0, 500)}"
        add_case(sender, receiver, rng.uniform(1000, 4000), 0.05, 0.45, 1, "graph_mule", device=float(rng.choice([0, 1])))
        
    # Fraud Ring: 6-8 nodes
    for _ in range(int(n_fraud * 0.4)):
        ring_idx = rng.integers(0, len(large_rings))
        ring = large_rings[ring_idx]
        idx = rng.integers(0, len(ring))
        sender = ring[idx]
        receiver = ring[(idx + 1) % len(ring)]
        add_case(sender, receiver, rng.uniform(2000, 6000), 0.10, 0.35, 1, "graph_ring", location=float(rng.choice([0, 1])))
        
    # Suspicious Hub
    for _ in range(int(n_fraud * 0.2)):
        receiver = rng.choice(hub_users)
        sender = f"user_{rng.integers(10000, 20000)}"
        add_case(sender, receiver, rng.uniform(300, 1500), 0.02, 0.65, 1, "graph_hub")

    # --- 3. EDGE CASES (10%) ---
    n_edge = n_samples - len(data)
    for _ in range(n_edge):
        case_type = ["high_trusted", "slight_anomaly", "mixed"][rng.integers(0, 3)]
        if case_type == "high_trusted":
            add_case(f"user_{rng.integers(1000, 2000)}", f"user_{rng.integers(2000, 3000)}", 25000, 0.95, 0.0, 0, "edge_high_trusted", u_avg=20000)
        elif case_type == "slight_anomaly":
            add_case(f"user_{rng.integers(3000, 4000)}", f"user_{rng.integers(4000, 5000)}", 3000, 0.45, 0.2, 0, "edge_slight_anomaly", location=1.0)
        else:
            add_case(f"user_{rng.integers(5000, 6000)}", f"user_{rng.integers(6000, 7000)}", 800, 0.30, 0.4, 1, "edge_mixed", device=1.0)

    df = pd.DataFrame(data)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    
    df.to_csv(output_path, index=False)
    print(f"Dataset saved to {output_path} in {time.time() - start_time:.2f}s with {len(df.columns)} columns")
    return str(output_path)

if __name__ == "__main__":
    mode = "MINI"
    if len(sys.argv) > 1:
        mode = sys.argv[1].upper()
    generate_graph_test_data(mode)
