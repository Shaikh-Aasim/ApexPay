import joblib
import numpy as np
import pandas as pd
from pathlib import Path
import sys

# Ensure we can import from utils and tests
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from tests.test_data_generator import generate_test_dataset, generate_large_scale_test_suite
from tests.metrics import print_overall_metrics, run_threshold_testing, analyze_false_positives
from tests.scenario_tests import run_scenario_evaluation, run_ux_tests
from api.predict import RiskPredictor

MODEL_PATH = ROOT / "model" / "risk_model.joblib"

def load_system():
    """Loads the risk predictor with integrated graph intelligence."""
    predictor = RiskPredictor()
    return predictor

def evaluate_dataset(predictor: RiskPredictor, df, y_true, name="Dataset"):
    """Runs a full evaluation on a specific dataset using the integrated RiskPredictor."""
    print(f"\n" + "="*40)
    print(f" EVALUATING: {name}")
    print("="*40)
    
    # Reset graph state for clean evaluation of the dataset
    predictor.graph_engine.reset()
    
    # Run Predictions
    y_pred = []
    prob_scores = []
    
    print(f"Processing {len(df)} transactions through Graph + ML + Rules...")
    for i, (_, row) in enumerate(df.iterrows()):
        data = row.to_dict()
        
        # 1. Update Graph (Simulating real-time arrival)
        # In a real system, we'd update with the final risk after prediction, 
        # but here we update basic transaction info first.
        predictor.update_graph(
            sender_id=data.get("sender_id", "user_unknown"),
            receiver_id=data.get("receiver_id", "user_unknown"),
            amount=float(data.get("amount", 0))
        )
        
        # 2. Predict
        res = predictor.predict(data)
        
        # 3. Post-prediction graph update (optional, but helpful for neighbor risk)
        predictor.graph_engine.update_user_risk(
            user_id=data.get("sender_id", "user_unknown"),
            risk_score=res["risk_score"],
            is_flagged=(res["decision"] == "HIGH")
        )
        
        y_pred.append(1 if res["decision"] == "HIGH" else 0)
        prob_scores.append(res["risk_score"])
        
        if (i + 1) % 1000 == 0:
            print(f"  ... processed {i + 1} samples")

    y_pred = np.array(y_pred)
    prob_scores = np.array(prob_scores)
    
    # 1. Overall Metrics
    print_overall_metrics(y_true, y_pred)
    
    # 2. Threshold Testing
    run_threshold_testing(y_true, prob_scores)
    
    # 3. Scenario Evaluation
    scenario_indices = {}
    if 'scenario_type' in df.columns:
        for s_type in df['scenario_type'].unique():
            scenario_indices[s_type] = df[df['scenario_type'] == s_type].index.tolist()
    
    if scenario_indices:
        run_scenario_evaluation(y_true, y_pred, scenario_indices)
        run_ux_tests(df, y_true, y_pred, scenario_indices)
    
    # FP Analysis
    analyze_false_positives(df, y_true, y_pred)

def main():
    print("="*60)
    print("      APEXPAY FRAUD DETECTION - GRAPH INTELLIGENCE EVALUATION")
    print("="*60)

    # 1. Load Predictor
    print("\n[1/4] Loading RiskPredictor (ML + Rules + Graph)...")
    predictor = load_system()
    print(f"Successfully loaded RiskPredictor (Model Version: {predictor.version})")

    # 2. Generate/Load Large Scale Test Data
    print("\n[2/4] Generating/Loading Large Scale Test Data...")
    csv_path = generate_large_scale_test_suite()
    df_full = pd.read_csv(csv_path)
    print(f"Loaded {len(df_full)} samples from {csv_path}")

    # 3. Split into Balanced and Realistic for Evaluation
    print("\n[3/4] Splitting into Balanced and Realistic Scenarios...")
    # Balanced: 50/50 split
    df_balanced = df_full[df_full['label'].isin([0, 1])].groupby('label').head(250).reset_index(drop=True) 
    y_balanced = df_balanced['label'].values
    
    # Realistic: 98/2 split (more realistic for fraud)
    n_total_realistic = 500
    n_fraud_realistic = int(n_total_realistic * 0.1) # 5% fraud
    n_normal_realistic = n_total_realistic - n_fraud_realistic
    
    df_normal = df_full[df_full['label'] == 0].head(n_normal_realistic)
    df_fraud = df_full[df_full['label'] == 1].head(n_fraud_realistic)
    df_realistic = pd.concat([df_normal, df_fraud]).sample(frac=1).reset_index(drop=True)
    y_realistic = df_realistic['label'].values

    # 4. Run Evaluations
    print("\n[4/4] Running Detailed Evaluations...")
    
    evaluate_dataset(predictor, df_balanced, y_balanced, name="BALANCED DATASET (50% Fraud)")
    evaluate_dataset(predictor, df_realistic, y_realistic, name="REALISTIC DATASET (5% Fraud)")

    # Final Summary
    print("\n" + "="*60)
    print("      FINAL GRAPH-INTEGRATED TEST SUMMARY")
    print("="*60)
    
    # Use predictor for final summary calculation
    predictor.graph_engine.reset()
    y_pred_realistic = []
    for _, row in df_realistic.iterrows():
        data = row.to_dict()
        predictor.update_graph(data.get("sender_id"), data.get("receiver_id"), float(data.get("amount")))
        res = predictor.predict(data)
        y_pred_realistic.append(1 if res["decision"] == "HIGH" else 0)
    
    y_pred_realistic = np.array(y_pred_realistic)
    
    fp_rate = np.sum((y_pred_realistic == 1) & (y_realistic == 0)) / np.sum(y_realistic == 0)
    recall = np.sum((y_pred_realistic == 1) & (y_realistic == 1)) / np.sum(y_realistic == 1)
    
    print(f"System Safety (Realistic): {'SAFE' if fp_rate < 0.05 else 'CAUTION (High FPs)'}")
    print(f"False Positive Rate: {fp_rate:.2%}")
    print(f"Fraud Detection Strength (Recall): {recall:.2%}")
    print("\nConclusion:")
    if fp_rate < 0.02 and recall > 0.55: # Updated target to 55%+
        print("-> The Graph Layer EXCEEDED performance targets.")
    elif recall > 0.45:
        print("-> The Graph Layer shows SIGNIFICANT improvement.")
    else:
        print("-> The system performance is stable but recall improvement is modest.")
    print("="*60)

if __name__ == "__main__":
    main()
