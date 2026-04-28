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
        # Initialize Graph Intelligence Layer
        self.graph_engine = GraphEngine()

    def _load_model(self) -> Dict[str, Any] | None:
        if not MODEL_PATH.exists():
            return None
        return joblib.load(MODEL_PATH)

    def predict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        # 1. PRE-PREDICT: Update Graph with current transaction
        # This ensures the graph is persistent and accumulates edges over time
        sender_id = data.get("sender_id", "unknown_sender")
        receiver_id = data.get("receiver_id", "unknown_receiver")
        amount = float(data.get("amount", 0))
        
        # Add edge and update node stats before analysis
        self.graph_engine.add_transaction(sender_id, receiver_id, amount)

        # 2. Get Heuristic Score
        h_res: HeuristicResult = heuristic_risk(
            amount=float(data.get("amount", 0)),
            amount_zscore=float(data.get("amount_zscore", 0)),
            device_change=int(data.get("device_change", 0)),
            location_anomaly=int(data.get("location_anomaly", 0)),
            txn_count_24h=int(data.get("txn_count_24h", 0)),
            receiver_suspicion_score=float(data.get("receiver_suspicion_score", 0)),
            receiver_flagged=int(data.get("receiver_flagged", 0)),
            is_first_transaction=bool(data.get("is_first_transaction", False)),
            account_age_hours=float(data.get("account_age_hours", 0)),
            is_periodic_pattern=bool(data.get("is_periodic_pattern", False))
        )

        ml_score = 0.0
        if self.model:
            # 2. Get ML Score
            X = np.array([get_feature_vector(data)])
            ml_score = float(self.model.predict_proba(X)[0][1])

        # 3. Integrate Graph Intelligence
        # This replaces the old weighted scoring and decision logic
        integration_res = integrate_graph_intelligence(
            data=data,
            ml_score=ml_score,
            rule_res=h_res,
            engine=self.graph_engine
        )

        return {
            "risk_score": integration_res["risk_score"],
            "decision": integration_res["decision"],
            "reasons": integration_res["reasons"],
            "fraud_type": h_res.fraud_type,
            "ml_score": ml_score,
            "rule_score": h_res.risk_score,
            "graph_score": integration_res["graph_score"],
            "graph_features": integration_res.get("graph_features", {}),
            "graph_debug": integration_res.get("graph_debug", {}),
            "debug_support": integration_res.get("debug_support", {}),
            "model_version": self.version
        }

    def update_graph(self, sender_id: str, receiver_id: str, amount: float, 
                     risk_score: float = 0.0, is_flagged: bool = False):
        """
        Updates the graph with new transaction and risk information.
        In production, this would be called for every processed transaction.
        """
        self.graph_engine.add_transaction(sender_id, receiver_id, amount)
        self.graph_engine.update_user_risk(sender_id, risk_score, is_flagged)
