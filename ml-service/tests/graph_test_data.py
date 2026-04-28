import pandas as pd
import numpy as np
from pathlib import Path
import time

def generate_graph_test_data(mode="MINI", output_path=None):
    """
    Generates structured scenario-based data for Graph Intelligence validation.
    
    Modes:
    - MINI: 800-1500 samples (default 1000)
    - FULL: 10k-15k samples (default 12000)
    
    Scenarios:
    A. NORMAL: salary, monthly repayment, family transfers (small cycles), trusted.
    B. GRAPH FRAUD: mule (10+ senders), fraud ring (6-8 nodes), suspicious hub.
    C. EDGE CASES: high amount but trusted, slight anomaly, mixed.
    """
    n_samples = 1000 if mode == "MINI" else 12000
    if output_path is None:
        output_path = f"graph_test_data_{mode.lower()}.csv"
        
    print(f"Generating {mode} dataset: {n_samples} samples...")
    start_time = time.time()
    rng = np.random.default_rng(42)
    
    data = []
    
    # PRE-DEFINE ACTORS for Graph Scenarios
    mule_receivers = [f"mule_rcv_{i}" for i in range(5 if mode == "MINI" else 20)]
    hub_users = [f"hub_user_{i}" for i in range(3 if mode == "MINI" else 15)]
    large_rings = [[f"ring_{r}_user_{i}" for i in range(rng.integers(6, 9))] for r in range(2 if mode == "MINI" else 10)]
    small_families = [[f"fam_{f}_user_{i}" for i in range(3)] for f in range(5 if mode == "MINI" else 50)]
    
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
            "is_periodic_pattern": 1 if "repayment" in scenario or "salary" in scenario else 0,
            "relationship_stability": stability,
            "label": label,
            "scenario": scenario
        })

    # --- 1. NORMAL CASES (60%) ---
    n_normal = int(n_samples * 0.6)
    
    # Salary
    for _ in range(int(n_normal * 0.3)):
        add_case("corp_hr", f"user_{rng.integers(1000, 5000)}", rng.uniform(3000, 7000), 0.95, 0.0, 0, "salary")
        
    # Monthly Repayments
    for _ in range(int(n_normal * 0.3)):
        add_case(f"user_{rng.integers(1000, 5000)}", "utility_co", rng.uniform(50, 300), 0.9, 0.0, 0, "monthly_repayment")
        
    # Family Transfers (Small Cycles / High Stability)
    for _ in range(int(n_normal * 0.2)):
        fam_idx = rng.integers(0, len(small_families))
        fam = small_families[fam_idx]
        s, r = rng.choice(fam, 2, replace=False)
        add_case(s, r, rng.uniform(100, 1000), 0.85, 0.0, 0, "family_transfer")
        
    # Trusted Relationships
    for _ in range(int(n_normal * 0.2)):
        add_case(f"user_{rng.integers(1000, 5000)}", f"user_{rng.integers(5000, 9000)}", rng.uniform(200, 2000), 0.8, 0.0, 0, "trusted_transfer")

    # --- 2. GRAPH FRAUD CASES (30%) ---
    n_fraud = int(n_samples * 0.3)
    
    # Mule: 10+ users -> 1 receiver
    for _ in range(int(n_fraud * 0.4)):
        receiver = rng.choice(mule_receivers)
        sender = f"mule_snd_{rng.integers(0, 500)}"
        # Mules often have low stability and high burst
        add_case(sender, receiver, rng.uniform(500, 2000), 0.05, 0.3, 1, "graph_mule", device=int(rng.integers(0, 2)))
        
    # Fraud Ring: 6-8 nodes
    for _ in range(int(n_fraud * 0.4)):
        ring_idx = rng.integers(0, len(large_rings))
        ring = large_rings[ring_idx]
        idx = rng.integers(0, len(ring))
        sender = ring[idx]
        receiver = ring[(idx + 1) % len(ring)]
        add_case(sender, receiver, rng.uniform(1000, 5000), 0.1, 0.2, 1, "graph_ring", location=int(rng.integers(0, 2)))
        
    # Suspicious Hub
    for _ in range(int(n_fraud * 0.2)):
        receiver = rng.choice(hub_users)
        sender = f"user_{rng.integers(10000, 20000)}"
        add_case(sender, receiver, rng.uniform(100, 500), 0.02, 0.5, 1, "graph_hub")

    # --- 3. EDGE CASES (10%) ---
    n_edge = n_samples - len(data)
    for _ in range(n_edge):
        case_type = ["high_trusted", "slight_anomaly", "mixed"][rng.integers(0, 3)]
        if case_type == "high_trusted":
            add_case(f"user_{rng.integers(1000, 2000)}", f"user_{rng.integers(2000, 3000)}", 15000, 0.95, 0.0, 0, "edge_high_trusted")
        elif case_type == "slight_anomaly":
            add_case(f"user_{rng.integers(3000, 4000)}", f"user_{rng.integers(4000, 5000)}", 2000, 0.4, 0.2, 0, "edge_slight_anomaly", location=1)
        else:
            add_case(f"user_{rng.integers(5000, 6000)}", f"user_{rng.integers(6000, 7000)}", 500, 0.3, 0.4, 1, "edge_mixed", device=1)

    # Final shuffle
    df = pd.DataFrame(data)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    
    df.to_csv(output_path, index=False)
    print(f"Dataset saved to {output_path} in {time.time() - start_time:.2f}s")
    return output_path

if __name__ == "__main__":
    import sys
    mode = "MINI"
    if len(sys.argv) > 1:
        mode = sys.argv[1].upper()
    generate_graph_test_data(mode)
