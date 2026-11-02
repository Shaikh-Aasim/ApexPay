from __future__ import annotations
import joblib
import numpy as np
from pathlib import Path
from typing import Dict, Any, List

from utils.features import FEATURES, get_feature_vector
from utils.risk_rules import heuristic_risk, HeuristicResult
from utils.graph_engine import GraphEngine
from api.integration import integrate_graph_intelligence

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "model" / "risk_model.joblib"

class RiskPredictor:
    def __init__(self):
        self.model_obj = self._load_model()
        self.model = self.model_obj["model"] if self.model_obj else None
        self.features = self.model_obj["features"] if self.model_obj else FEATURES
        self.version = self.model_obj.get("version", "unknown") if self.model_obj else "heuristic-only"
        
        # Optimize tree evaluation for low-latency single-sample inference (eliminate multiprocessing overhead)
        if self.model and hasattr(self.model, "calibrated_classifiers_"):
            for c in self.model.calibrated_classifiers_:
                if hasattr(c, "estimator"):
                    c.estimator.n_jobs = 1
        elif self.model and hasattr(self.model, "n_jobs"):
            self.model.n_jobs = 1

        # Initialize Graph Intelligence Layer
        self.graph_engine = GraphEngine()

    def _load_model(self) -> Dict[str, Any] | None:
        if not MODEL_PATH.exists():
            return None
        return joblib.load(MODEL_PATH)

    def predict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Full 3-layer hybrid prediction pipeline:
        1. Graph State Ingestion
        2. Heuristic Rule Evaluation (Layer 1)
        3. Calibrated ML Probability (Layer 2)
        4. Hard Overrides (Non-negotiable security blocks)
        5. Graph Intelligence Fusion (Layer 3)
        6. Normalized Decision Gating (LOW, MEDIUM, HIGH)
        """
        sender_id = str(data.get("sender_id", ""))
        receiver_id = str(data.get("receiver_id", ""))
        amount = float(data.get("amount", 0))
        txn_id = data.get("transaction_id")

        # 1. Update Graph with current transaction (idempotent, validates IDs)
        self.graph_engine.add_transaction(sender_id, receiver_id, amount, txn_id=txn_id)

        # 2. Extract Contextual Signals
        z = float(data.get("amount_zscore", 0))
        device = int(data.get("device_change", 0))
        location = int(data.get("location_anomaly", 0))
        stability = float(data.get("relationship_stability_score", data.get("relationship_stability", 0.0)))
        txn_count = int(data.get("txn_count_24h", 1))
        is_first = bool(data.get("is_first_transaction", data.get("sender_is_first_transaction", False)))
        account_age = float(data.get("account_age_hours", data.get("sender_account_age_hours", 720.0)))
        is_periodic = bool(data.get("is_periodic_pattern", False))

        # 3. Layer 1: Heuristic Risk Evaluation
        h_res: HeuristicResult = heuristic_risk(
            amount=amount,
            amount_zscore=z,
            device_change=device,
            location_anomaly=location,
            txn_count_24h=txn_count,
            receiver_suspicion_score=float(data.get("receiver_suspicion_score", 0)),
            receiver_flagged=int(data.get("receiver_flagged", 0)),
            is_first_transaction=is_first,
            account_age_hours=account_age,
            is_periodic_pattern=is_periodic,
            relationship_stability=stability
        )

        # 4. Layer 2: Machine Learning Inference
        ml_score = 0.0
        if self.model:
            X = np.array([get_feature_vector(data)])
            ml_score = float(self.model.predict_proba(X)[0][1])

        # 5. Smart Force Override: Critical Account Takeover or Extreme Deviation
        if z > 8.0 or (device == 1 and location == 1 and stability < 0.4 and amount >= 10000):
            return {
                "risk_score": 0.95,
                "combined_risk_score": 0.95,
                "ml_probability": round(ml_score, 4),
                "rule_score": round(h_res.risk_score, 4),
                "graph_score": 1.0,
                "decision": "HIGH",
                "reasons": list(set(h_res.reasons + ["Critical Account Takeover / Extreme Deviation Detected"])),
                "fraud_type": h_res.fraud_type if h_res.fraud_type != "UNKNOWN" else "ACCOUNT_TAKEOVER",
                "graph_features": {},
                "graph_debug": {},
                "debug_support": {
                    "override": "smart_force_high",
                    "reason": "Extreme anomaly threshold exceeded"
                },
                "model_version": self.version
            }

        # 6. Layer 3: Graph Intelligence Fusion
        integration_res = integrate_graph_intelligence(
            data=data,
            ml_score=ml_score,
            rule_res=h_res,
            engine=self.graph_engine
        )

        final_score = integration_res["risk_score"]
        graph_score = integration_res["graph_score"]
        decision = integration_res["decision"]

        # Ensure final score is strictly clamped in [0.0, 1.0] for backend Zod validation safety
        final_score = max(0.0, min(1.0, float(final_score)))

        return {
            "risk_score": round(final_score, 4),
            "combined_risk_score": round(final_score, 4),
            "ml_probability": round(ml_score, 4),
            "rule_score": round(h_res.risk_score, 4),
            "graph_score": round(graph_score, 4),
            "decision": decision,
            "reasons": integration_res["reasons"],
            "fraud_type": h_res.fraud_type,
            "graph_features": integration_res.get("graph_features", {}),
            "graph_debug": integration_res.get("graph_debug", {}),
            "debug_support": integration_res.get("debug_support", {}),
            "model_version": self.version
        }

    def update_graph(self, sender_id: str, receiver_id: str, amount: float, 
                     risk_score: float = 0.0, is_flagged: bool = False):
        """
        Updates the graph with new transaction and risk information.
        In production, this is called for every processed transaction.
        """
        self.graph_engine.add_transaction(sender_id, receiver_id, amount)
        self.graph_engine.update_user_risk(sender_id, risk_score, is_flagged)
