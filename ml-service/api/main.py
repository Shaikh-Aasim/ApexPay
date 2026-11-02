from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, ConfigDict

from api.predict import RiskPredictor

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
METRICS_PATH = ROOT / "model" / "metrics.json"

class RiskRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    # Identifiers for Dynamic Graph Tracking & Deduplication
    sender_id: Optional[str] = None
    receiver_id: Optional[str] = None
    transaction_id: Optional[str] = None

    # Core Transaction Features
    amount: float = Field(gt=0)
    txn_count_24h: int = Field(ge=0, default=1)
    device_change: int = Field(ge=0, le=1, default=0)
    location_anomaly: int = Field(ge=0, le=1, default=0)
    receiver_suspicion_score: float = Field(ge=0, le=1, default=0.0)
    receiver_flagged: int = Field(ge=0, le=1, default=0)
    user_avg_amount_30d: float = Field(ge=0, default=0.0)
    user_std_amount_30d: float = Field(ge=0, default=0.0)
    amount_zscore: float = 0.0
    
    # Sender Context Features
    is_first_transaction: bool = False
    user_total_txn: int = Field(ge=0, default=0)
    account_age_hours: float = Field(ge=0, default=720.0)
    
    # Receiver Context Features (Decoupled Evaluation)
    receiver_is_first_transaction: Optional[bool] = None
    receiver_account_age_hours: Optional[float] = None
    receiver_total_txn: Optional[int] = None

    # Pattern & Relationship Features
    is_periodic_pattern: bool = False
    day_of_month: int = Field(ge=1, le=31, default=1)
    relationship_stability_score: float = Field(ge=0, le=1, default=0.5)
    
    # Global Risk Features
    is_high_amount_global: bool = False
    amount_percentile_global: float = Field(ge=0, le=1, default=0.0)

class RiskResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    # Primary Decision Metrics
    risk_score: float
    combined_risk_score: Optional[float] = None
    ml_probability: Optional[float] = None
    rule_score: Optional[float] = None
    graph_score: Optional[float] = None
    decision: str
    reasons: List[str]
    fraud_type: str
    model_version: str

app = FastAPI(title="ApexPay Advanced Risk Service", version="2.2.0")
predictor = RiskPredictor()

@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "model_version": predictor.version}

@app.get("/metrics")
def metrics() -> Dict[str, Any]:
    if METRICS_PATH.exists():
        return json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail="metrics not found; run training/train.py")

@app.post("/predict-risk", response_model=RiskResponse)
def predict(req: RiskRequest) -> RiskResponse:
    try:
        data = req.model_dump()
        result = predictor.predict(data)
        return RiskResponse(
            risk_score=result["risk_score"],
            combined_risk_score=result.get("combined_risk_score", result["risk_score"]),
            ml_probability=result.get("ml_probability", result.get("ml_score", 0.0)),
            rule_score=result.get("rule_score", 0.0),
            graph_score=result.get("graph_score", 0.0),
            decision=result["decision"],
            reasons=result["reasons"],
            fraud_type=result["fraud_type"],
            model_version=result["model_version"]
        )
    except Exception as e:
        # Keep the full traceback in server logs for diagnosis while returning
        # a stable error response to API clients.
        logger.exception("Fraud-risk prediction failed")
        raise HTTPException(status_code=500, detail=str(e))
