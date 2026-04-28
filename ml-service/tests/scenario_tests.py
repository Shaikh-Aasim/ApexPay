import numpy as np
from typing import Dict, List
from sklearn.metrics import accuracy_score

def run_scenario_evaluation(y_true: np.ndarray, y_pred: np.ndarray, scenario_indices: Dict[str, List[int]]):
    """Evaluates accuracy for each specific behavior scenario."""
    print("\n" + "="*40)
    print("      SCENARIO-BASED PERFORMANCE")
    print("="*40)
    print(f"{'Scenario Name':<30} | {'Count':<6} | {'Accuracy':<10}")
    print("-" * 52)

    # Group scenarios into higher-level categories for clarity
    groups = {
        "NORMAL SCENARIOS": [
            "normal_repayment", 
            "salary_incoming", 
            "regular_behavior", 
            "legit_high_value", 
            "trusted_relationships"
        ],
        "FRAUD SCENARIOS": [
            "fraud_first_txn", 
            "fraud_ato", 
            "fraud_velocity", 
            "fraud_high_zscore", 
            "fraud_mule", 
            "stealth_fraud",
            "graph_mule",
            "graph_ring",
            "graph_hub"
        ],
        "EDGE CASES": [
            "edge_case_high_amount_legit", 
            "edge_case_slight_anomaly", 
            "edge_case_medium_risk", 
            "edge_case_mixed_behavior"
        ]
    }

    for group_name, scenarios in groups.items():
        print(f"\n--- {group_name} ---")
        for scenario in scenarios:
            indices = scenario_indices.get(scenario, [])
            if not indices: continue
            
            s_true = y_true[indices]
            s_pred = y_pred[indices]
            
            # Use unique indices to avoid issues if samples were replaced during generation
            # although indices should already be unique per scenario
            acc = accuracy_score(s_true, s_pred)
            print(f"{scenario:<30} | {len(indices):<6} | {acc:<10.2%}")

def run_ux_tests(df, y_true, y_pred, scenario_indices):
    """Specific tests for User Experience requirements."""
    print("\n" + "="*40)
    print("      USER EXPERIENCE (UX) VALIDATION")
    print("="*40)

    # 1. Monthly Repayment Test
    repayment_indices = scenario_indices.get("normal_repayment", [])
    if repayment_indices:
        fails = np.sum(y_pred[repayment_indices] == 1)
        total = len(repayment_indices)
        status = "PASSED" if (fails/total) < 0.01 else f"FAILED ({(fails/total):.2%} flagged)"
        print(f"Monthly Repayment Test: {status}")
        print(f"  - Expected: <1% flagged. Actual: {(fails/total):.2%} flagged.")

    # 2. New User + High Amount (Cold Start)
    first_txn_indices = scenario_indices.get("fraud_first_txn", [])
    if first_txn_indices:
        detects = np.sum(y_pred[first_txn_indices] == 1)
        total = len(first_txn_indices)
        print(f"New User + High Amount Test: {(detects/total):.2%} DETECTED")
        print(f"  - Context: First transaction of high amount should be scrutinized (MEDIUM/HOLD).")

    # 3. Legit High-Value Transaction
    high_legit_indices = scenario_indices.get("edge_case_high_amount_legit", [])
    if high_legit_indices:
        fails = np.sum(y_pred[high_legit_indices] == 1)
        total = len(high_legit_indices)
        status = "PASSED" if (fails/total) < 0.05 else f"FAILED (Too many FPs: {(fails/total):.2%})"
        print(f"Legit High-Value Test: {status}")
        print(f"  - Context: Business/Loan payments should NOT be blocked as high risk.")

    # 4. Trusted Relationship Test
    trusted_indices = scenario_indices.get("trusted_relationships", [])
    if trusted_indices:
        fails = np.sum(y_pred[trusted_indices] == 1)
        total = len(trusted_indices)
        status = "PASSED" if (fails/total) < 0.02 else f"FAILED ({(fails/total):.2%} flagged)"
        print(f"Trusted Relationship Test: {status}")
        print(f"  - Context: High stability transfers should have minimal friction.")

    # 5. Graph Scenario Tests
    graph_scenarios = ["graph_mule", "graph_ring", "graph_hub"]
    print("\nGraph Scenario Detection:")
    for scenario in graph_scenarios:
        indices = scenario_indices.get(scenario, [])
        if indices:
            detects = np.sum(y_pred[indices] == 1)
            total = len(indices)
            print(f"  - {scenario:<15}: {(detects/total):.2%} DETECTED")
