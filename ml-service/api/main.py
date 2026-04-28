from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from api.predict import RiskPredictor

ROOT = Path(__file__).resolve().parents[1]
METRICS_PATH = ROOT / "model" / "metrics.json"

class RiskRequest(BaseModel):
    # Existing features
    amount: float = Field(gt=0)
    txn_count_24h: int = Field(ge=0)
    device_change: int = Field(ge=0, le=1)
    location_anomaly: int = Field(ge=0, le=1)
    receiver_suspicion_score: float = Field(ge=0, le=1)
    receiver_flagged: int = Field(ge=0, le=1)
    user_avg_amount_30d: float = Field(ge=0)
    user_std_amount_30d: float = Field(ge=0)
    amount_zscore: float
    
    # New User Context features
    is_first_transaction: bool = False
    user_total_txn: int = Field(ge=0, default=0)
    account_age_hours: float = Field(ge=0, default=0.0)
    
    # New Pattern Features
    is_periodic_pattern: bool = False
    day_of_month: int = Field(ge=1, le=31, default=1)
    relationship_stability_score: float = Field(ge=0, le=1, default=0.0)
    
    # New Global Risk Features
    is_high_amount_global: bool = False
    amount_percentile_global: float = Field(ge=0, le=1, default=0.0)

class RiskResponse(BaseModel):
    risk_score: float
    decision: str
    reasons: List[str]
    fraud_type: str
    model_version: str

app = FastAPI(title="ApexPay Advanced Risk Service", version="2.0.0")
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
        return RiskResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
