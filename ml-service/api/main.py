from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from utils.risk_rules import heuristic_risk


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "model" / "risk_model.joblib"
METRICS_PATH = ROOT / "model" / "metrics.json"


class RiskRequest(BaseModel):
    amount: float = Field(gt=0)
    txn_count_24h: int = Field(ge=0)
    device_change: int = Field(ge=0, le=1)
    location_anomaly: int = Field(ge=0, le=1)
    receiver_suspicion_score: float = Field(ge=0, le=1)
    receiver_flagged: int = Field(ge=0, le=1)
    user_avg_amount_30d: float = Field(ge=0)
    user_std_amount_30d: float = Field(gt=0)
    amount_zscore: float


class RiskResponse(BaseModel):
    risk_score: float
    decision: str
    reasons: List[str]
    fraud_type: str
    model_version: str


def load_model() -> Optional[Dict[str, Any]]:
    if not MODEL_PATH.exists():
        return None
    obj = joblib.load(MODEL_PATH)
    if not isinstance(obj, dict) or "model" not in obj:
        return None
    return obj


MODEL_OBJ = load_model()

app = FastAPI(title="ApexPay ML Risk Service", version="1.0.0")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> Dict[str, Any]:
    if METRICS_PATH.exists():
        return json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail="metrics not found; run training/train.py")


@app.post("/predict-risk", response_model=RiskResponse)
def predict(req: RiskRequest) -> RiskResponse:
    amount = float(req.amount)
    amount_zscore = float(req.amount_zscore)

    if MODEL_OBJ is None:
        res = heuristic_risk(
            amount=amount,
            amount_zscore=amount_zscore,
            device_change=int(req.device_change),
            location_anomaly=int(req.location_anomaly),
            txn_count_24h=int(req.txn_count_24h),
            receiver_suspicion_score=float(req.receiver_suspicion_score),
            receiver_flagged=int(req.receiver_flagged),
        )
        return RiskResponse(
            risk_score=res.risk_score,
            decision=res.decision,
            reasons=res.reasons,
            fraud_type=res.fraud_type,
            model_version="heuristic-1",
        )

    features: List[str] = MODEL_OBJ["features"]
    model = MODEL_OBJ["model"]
    version = str(MODEL_OBJ.get("version", "rf-unknown"))

    payload: Dict[str, Any] = req.model_dump()
    X = np.array([[float(payload[f]) for f in features]], dtype=float)
    prob = float(model.predict_proba(X)[0][1])

    res = heuristic_risk(
        amount=amount,
        amount_zscore=amount_zscore,
        device_change=int(req.device_change),
        location_anomaly=int(req.location_anomaly),
        txn_count_24h=int(req.txn_count_24h),
        receiver_suspicion_score=float(req.receiver_suspicion_score),
        receiver_flagged=int(req.receiver_flagged),
    )

    return RiskResponse(
        risk_score=max(prob, res.risk_score),
        decision=res.decision,
        reasons=res.reasons,
        fraud_type=res.fraud_type,
        model_version=version,
    )
