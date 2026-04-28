import pandas as pd
import numpy as np
from pathlib import Path
import time

def generate_noisy_test_data(n_samples=7000, output_path="noisy_test_data.csv"):
    """
    Generates a noisy, realistic dataset for fraud detection validation.
    
    Refined Scenarios:
    1. NORMAL (90%):
       - Standard: Low risk, stable.
       - Business: High frequency, many senders, but trusted.
       - Noisy Normal: High amount or device change but high stability.
       - New Users: Low account age, first transaction.
       - Tricky Graph: Large cycles but high stability.
    2. FRAUD (10%):
       - Stealth Fraud: Low amounts, normal device, harder to detect.
       - Partial Fraud: Only 1-2 signals (e.g., just device change).
       - Obvious/Burst: High velocity, mule patterns.
    3. Label Noise: 3-5% flipped.
    """
    print(f"Generating noisy dataset: {n_samples} samples...")
    start_time = time.time()
    rng = np.random.default_rng(42)
    
    data = []
    
    # Actors for scenarios
    business_accounts = [f"biz_acc_{i}" for i in range(15)]
    trusted_users = [f"trusted_u_{i}" for i in range(50)]
    stealth_fraudsters = [f"stealth_fr_{i}" for i in range(30)]
    stable_rings = [[f"ring_{r}_u_{i}" for i in range(6)] for r in range(5)]

    def add_case(sender, receiver, amount, stability, suspicion, label, scenario, 
                 device=0, location=0, age=720, txn_24h=1, first_txn=False):
        # Calculate derived fields
        avg_30d = 500
        std_30d = 200
        zscore = (amount - avg_30d) / std_30d if std_30d > 0 else 0
        
        data.append({
            "sender_id": sender,
            "receiver_id": receiver,
            "amount": amount,
            "amount_zscore": zscore,
            "txn_count_24h": txn_24h,
            "device_change": device,
            "location_anomaly": location,
            "receiver_flagged": 1 if suspicion > 0.8 else 0,
            "receiver_suspicion_score": suspicion,
            "user_avg_amount_30d": avg_30d,
            "user_std_amount_30d": std_30d,
            "is_first_transaction": 1 if first_txn else 0,
            "user_total_txn": 0 if first_txn else rng.integers(5, 100),
            "account_age_hours": age,
            "is_periodic_pattern": 1 if "salary" in scenario or "repayment" in scenario else 0,
            "day_of_month": rng.integers(1, 28),
            "relationship_stability_score": stability,
            "is_high_amount_global": 1 if amount > 10000 else 0,
            "amount_percentile_global": min(1.0, amount / 20000),
            "label": label,
            "scenario": scenario
        })

    # --- 1. NORMAL CASES (90%) ---
    n_normal = int(n_samples * 0.9)
    
    # Standard (50% of normal)
    for _ in range(int(n_normal * 0.5)):
        s = rng.choice(trusted_users)
        r = f"user_{rng.integers(1000, 9000)}"
        add_case(s, r, rng.uniform(50, 800), 0.8, 0.0, 0, "normal_standard")

    # Business/Hub (20% of normal) - Tricky Many-to-One
    for _ in range(int(n_normal * 0.2)):
        biz = rng.choice(business_accounts)
        s = f"user_{rng.integers(10000, 20000)}"
        # Business accounts have many unique senders but high stability with the platform
        add_case(s, biz, rng.uniform(100, 3000), 0.5, 0.0, 0, "normal_business_hub", txn_24h=rng.integers(1, 5))

    # Noisy Normal (20% of normal) - High amount or device change
    for _ in range(int(n_normal * 0.2)):
        noise_type = rng.choice(["high_amount", "device_change", "stable_ring"])
        s = f"trusted_noise_{rng.integers(1, 500)}"
        r = f"user_{rng.integers(1, 500)}"
        if noise_type == "high_amount":
            add_case(s, r, rng.uniform(15000, 40000), 0.9, 0.0, 0, "noisy_normal_high_amount")
        elif noise_type == "device_change":
            add_case(s, r, rng.uniform(100, 500), 0.85, 0.0, 0, "noisy_normal_device", device=1)
        else: # Tricky Cycle
            ring = rng.choice(stable_rings)
            idx = rng.integers(0, len(ring))
            add_case(ring[idx], ring[(idx+1)%len(ring)], rng.uniform(200, 1000), 0.9, 0.0, 0, "noisy_normal_cycle")

    # New Users (10% of normal)
    for _ in range(n_normal - len(data)):
        add_case(f"new_u_{rng.integers(1, 1000)}", f"user_{rng.integers(1, 1000)}", rng.uniform(100, 1000), 0.0, 0.0, 0, "normal_new_user", age=rng.integers(1, 12), first_txn=True)

    # --- 2. FRAUD CASES (10%) ---
    n_fraud_target = n_samples - len(data)
    
    # Stealth Fraud (40% of fraud)
    for _ in range(int(n_fraud_target * 0.4)):
        f = rng.choice(stealth_fraudsters)
        v = f"victim_{rng.integers(1, 1000)}"
        # Low amount, normal device, low stability
        add_case(f, v, rng.uniform(20, 150), 0.0, 0.1, 1, "fraud_stealth")

    # Partial Fraud (30% of fraud) - Only 1 anomaly
    for _ in range(int(n_fraud_target * 0.3)):
        anomaly = rng.choice(["device", "location", "zscore"])
        f = f"fr_partial_{rng.integers(1, 500)}"
        v = f"v_{rng.integers(1, 500)}"
        if anomaly == "device":
            add_case(f, v, 200, 0.0, 0.2, 1, "fraud_partial_device", device=1)
        elif anomaly == "location":
            add_case(f, v, 200, 0.0, 0.2, 1, "fraud_partial_location", location=1)
        else:
            add_case(f, v, 9000, 0.0, 0.2, 1, "fraud_partial_amount")

    # Obvious/Burst (30% of fraud)
            for _ in range(n_samples - len(data)):
                case_type = rng.choice(["mule_burst", "ring_unstable"])
                if case_type == "mule_burst":
                    # TRIGGER MULE: in_degree >= 5 AND unique_senders >= 5 AND txn_count_24h > 3 AND stability < 0.4
                    # We use a specific receiver to simulate a mule hub
                    mule_hub = "mule_rcv_target"
                    # Add some history for this mule hub in the loop to ensure it triggers
                    add_case(f"mule_snd_{rng.integers(1, 100)}", mule_hub, rng.uniform(500, 2000), 0.05, 0.9, 1, "fraud_mule_burst", txn_24h=12, device=1)
                else:
                    # TRIGGER RING: node_count >= 5 AND stability < 0.4 AND transaction density is high
                    add_case(f"ring_u_{rng.integers(1, 5)}", f"ring_u_{rng.integers(6, 10)}", rng.uniform(1000, 4000), 0.1, 0.8, 1, "fraud_ring_burst", location=1)

    # --- 3. LABEL NOISE (3-5%) ---
    df = pd.DataFrame(data)
    noise_level = rng.uniform(0.03, 0.05)
    noise_mask = rng.random(len(df)) < noise_level
    df.loc[noise_mask, 'label'] = 1 - df.loc[noise_mask, 'label']
    df.loc[noise_mask, 'scenario'] = df.loc[noise_mask, 'scenario'] + "_label_noise"

    # Final shuffle
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    
    df.to_csv(output_path, index=False)
    print(f"Dataset generated and saved to {output_path}")
    print(f"Distribution: {df['label'].value_counts(normalize=True).to_dict()}")
    return output_path

if __name__ == "__main__":
    generate_noisy_test_data(8000)
