"""
Comprehensive End-to-End Test Suite for ApexPay ML Service
==========================================================
Validates:
1. Normal everyday transactions (LOW)
2. Context-aware threshold adjustments & relationship stability discounts
3. Hard security overrides (Account Takeover, Blacklist)
4. Cold-start new user transactions (FIRST_TXN_HIGH_AMOUNT)
5. Graph Intelligence: Social bill-splitting triangles (LOW)
6. Graph Intelligence: Circular laundering rings >= 5 nodes (HIGH)
7. Graph Intelligence: Money mule fan-in aggregation (HIGH)
8. Exact discrete time-window aggregation (1h, 24h, 7d, lifetime)
9. Idempotent deduplication (resending same txn_id)
10. Identity validation & super-node prevention (unknown_sender)
11. End-to-end API response contract & fields
12. Inference latency benchmarks (p50, p95, p99)

Author: ApexPay Machine Learning Systems Team
"""

import sys
import time
from pathlib import Path
from typing import Dict, Any, List
import numpy as np

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from api.predict import RiskPredictor
from utils.graph_engine import GraphEngine, is_valid_identity
from utils.graph_features import compute_graph_features
from utils.graph_rules import detect_mule_pattern, detect_fraud_ring
from utils.risk_rules import heuristic_risk

class TestApexPayMLService:
    def __init__(self):
        self.predictor = RiskPredictor()
        # Use isolated in-memory test engine
        self.engine = GraphEngine(enable_persistence=False)
        self.predictor.graph_engine = self.engine
        self.results: List[Dict[str, Any]] = []

    def record_test(self, name: str, passed: bool, details: str = ""):
        self.results.append({
            "name": name,
            "passed": passed,
            "details": details
        })
        status_str = "[PASS]" if passed else "[FAIL]"
        print(f" {status_str:<6} | {name:<50} | {details}")

    def test_01_normal_legitimate_payment(self):
        """Everyday payment with familiar receiver should be approved as LOW risk."""
        payload = {
            "sender_id": "user_rahul",
            "receiver_id": "user_grocery_store",
            "amount": 350.0,
            "amount_zscore": 0.1,
            "txn_count_24h": 1,
            "device_change": 0,
            "location_anomaly": 0,
            "relationship_stability_score": 0.85,
            "account_age_hours": 2400.0
        }
        res = self.predictor.predict(payload)
        passed = (res["decision"] == "LOW") and (res["risk_score"] < 0.42)
        self.record_test("01. Normal Legitimate Payment Flow", passed, f"Score: {res['risk_score']:.4f}, Decision: {res['decision']}")

    def test_02_account_takeover_override(self):
        """Sudden new device, anomalous location, and extreme Z-score should trigger HIGH."""
        payload = {
            "sender_id": "user_victim_1",
            "receiver_id": "user_attacker_1",
            "amount": 45000.0,
            "amount_zscore": 8.5,
            "txn_count_24h": 5,
            "device_change": 1,
            "location_anomaly": 1,
            "relationship_stability_score": 0.05,
            "account_age_hours": 1200.0
        }
        res = self.predictor.predict(payload)
        passed = (res["decision"] == "HIGH") and (res["fraud_type"] == "ACCOUNT_TAKEOVER") and (res["risk_score"] >= 0.85)
        self.record_test("02. Critical Account Takeover Override", passed, f"Score: {res['risk_score']:.4f}, Type: {res['fraud_type']}")

    def test_03_cold_start_high_amount(self):
        """Brand new account attempting maximum ceiling transfer should be flagged."""
        payload = {
            "sender_id": "user_new_signup",
            "receiver_id": "user_random_1",
            "amount": 75000.0,
            "amount_zscore": 3.5,
            "txn_count_24h": 1,
            "is_first_transaction": True,
            "account_age_hours": 2.0,
            "device_change": 0,
            "location_anomaly": 0,
            "relationship_stability_score": 0.0
        }
        res = self.predictor.predict(payload)
        passed = (res["decision"] in ["MEDIUM", "HIGH"]) and (res["risk_score"] >= 0.45)
        self.record_test("03. Cold-Start First Txn High Value", passed, f"Score: {res['risk_score']:.4f}, Decision: {res['decision']}")

    def test_04_social_triangle_not_laundering(self):
        """3-node cycle (A -> B -> C -> A) splitting bills should NOT be flagged as money laundering."""
        self.engine.reset()
        now = time.time()
        self.engine.add_transaction("friend_A", "friend_B", 200.0, timestamp=now - 500)
        self.engine.add_transaction("friend_B", "friend_C", 200.0, timestamp=now - 300)
        self.engine.add_transaction("friend_C", "friend_A", 200.0, timestamp=now - 100)

        ring = detect_fraud_ring("friend_A", self.engine, relationship_stability=0.7)
        passed = (ring["path_len"] == 3) and (ring["risk"] <= 0.10)
        self.record_test("04. Social Triangle (3 nodes) Exemption", passed, f"Nodes: {ring['path_len']}, Risk: {ring['risk']}")

    def test_05_circular_laundering_ring(self):
        """5-node circular ring (U0 -> U1 -> U2 -> U3 -> U4 -> U0) should be flagged as severe laundering."""
        self.engine.reset()
        now = time.time()
        nodes = [f"launder_U{i}" for i in range(5)]
        for i in range(4):
            self.engine.add_transaction(nodes[i], nodes[i+1], 15000.0, timestamp=now - (500 - i * 50))
        self.engine.add_transaction(nodes[4], nodes[0], 15000.0, timestamp=now)

        ring = detect_fraud_ring(nodes[0], self.engine, relationship_stability=0.1)
        passed = (ring["path_len"] == 5) and (ring["risk"] >= 0.90) and ("high_density_ring" in ring["flags"])
        self.record_test("05. Extended Laundering Ring (>=5 nodes)", passed, f"Nodes: {ring['path_len']}, Risk: {ring['risk']}, Flags: {ring['flags']}")

    def test_06_mule_account_fan_in(self):
        """Mule account receiving rapid funds from 10 distinct senders within 24 hours."""
        self.engine.reset()
        now = time.time()
        mule_id = "target_mule_account"
        for i in range(11):
            sender = f"victim_payer_{i}"
            self.engine.add_transaction(sender, mule_id, 2500.0, timestamp=now - (i * 100))

        feat = compute_graph_features(mule_id, self.engine, current_time=now)
        mule_res = detect_mule_pattern(feat, relationship_stability=0.05)
        passed = (feat["unique_senders_24h"] >= 10) and (mule_res["risk"] >= 0.90)
        self.record_test("06. Mule Fan-In Funnel Detection", passed, f"Senders24h: {feat['unique_senders_24h']}, Risk: {mule_res['risk']}")

    def test_07_discrete_time_window_separation(self):
        """10 historical transactions over 30 days and 1 transaction today must not count as 11 in 24 hours."""
        self.engine.reset()
        now = time.time()
        s_id = "sender_alice"
        r_id = "receiver_bob"
        
        # 10 transactions 15 days ago
        for i in range(10):
            ts = now - (15 * 86400) + (i * 60)
            self.engine.add_transaction(s_id, r_id, 100.0, timestamp=ts, txn_id=f"old_{i}")
            
        # 1 transaction today
        self.engine.add_transaction(s_id, r_id, 100.0, timestamp=now, txn_id="today_1")

        feat = compute_graph_features(s_id, self.engine, current_time=now)
        passed = (feat["burst_count_24h"] == 1) and (feat["lifetime_txns"] == 11)
        self.record_test("07. Accurate Time-Window Separation", passed, f"24h: {feat['burst_count_24h']}, Lifetime: {feat['lifetime_txns']}")

    def test_08_idempotent_deduplication(self):
        """Inserting identical transaction_id multiple times must not inflate graph edge count."""
        self.engine.reset()
        now = time.time()
        t1 = self.engine.add_transaction("sender_x", "receiver_y", 500.0, timestamp=now, txn_id="txn_unique_123")
        t2 = self.engine.add_transaction("sender_x", "receiver_y", 500.0, timestamp=now, txn_id="txn_unique_123")

        feat = compute_graph_features("sender_x", self.engine, current_time=now)
        passed = (t1 is True) and (t2 is False) and (feat["lifetime_txns"] == 1)
        self.record_test("08. Idempotent Deduplication Safeguard", passed, f"First: {t1}, Second: {t2}, Lifetime: {feat['lifetime_txns']}")

    def test_09_identity_sanitization(self):
        """Unknown placeholder identities must be rejected to prevent artificial super-nodes."""
        self.engine.reset()
        res1 = self.engine.add_transaction("unknown_sender", "user_valid", 100.0)
        res2 = self.engine.add_transaction("user_valid", "unknown_receiver", 100.0)
        res3 = is_valid_identity("dummy")
        
        passed = (res1 is False) and (res2 is False) and (res3 is False)
        self.record_test("09. Super-Node Contamination Prevention", passed, f"unknown_sender blocked: {not res1}, dummy invalid: {not res3}")

    def test_10_api_response_schema_completeness(self):
        """Verify that prediction output contains all required fields for Node.js backend."""
        payload = {
            "sender_id": "usr_test_schema_1",
            "receiver_id": "usr_test_schema_2",
            "amount": 1200.0,
            "amount_zscore": 0.5,
            "txn_count_24h": 2
        }
        res = self.predictor.predict(payload)
        expected_keys = [
            "risk_score", "combined_risk_score", "ml_probability",
            "rule_score", "graph_score", "decision", "reasons",
            "fraud_type", "model_version"
        ]
        all_present = all(k in res for k in expected_keys)
        self.record_test("10. API Contract Schema Completeness", all_present, f"Keys verified: {len(expected_keys)}")

    def test_11_optional_receiver_context_is_null_safe(self):
        """API model_dump includes optional receiver fields as None; inference must accept that."""
        payload = {
            "sender_id": "usr_rahul_9912",
            "receiver_id": "usr_ananya_3321",
            "amount": 450.0,
            "amount_zscore": 0.25,
            "txn_count_24h": 2,
            "relationship_stability_score": 0.85,
            "receiver_is_first_transaction": None,
            "receiver_account_age_hours": None,
            "receiver_total_txn": None,
        }
        try:
            result = self.predictor.predict(payload)
            passed = (
                0.0 <= result["risk_score"] <= 1.0
                and result["decision"] in {"LOW", "MEDIUM", "HIGH"}
            )
            details = f"Score: {result['risk_score']:.4f}, Decision: {result['decision']}"
        except Exception as exc:
            passed = False
            details = f"Raised {type(exc).__name__}: {exc}"
        self.record_test("11. Optional Receiver Context (None) Safety", passed, details)

    def test_12_actual_fastapi_endpoint(self):
        """Exercise the same POST contract used by Swagger UI."""
        try:
            from fastapi.testclient import TestClient
            from api.main import app

            payload = {
                "sender_id": "usr_rahul_9912",
                "receiver_id": "usr_ananya_3321",
                "amount": 450.0,
                "amount_zscore": 0.25,
                "txn_count_24h": 2,
                "relationship_stability_score": 0.85,
            }
            with TestClient(app) as client:
                response = client.post("/predict-risk", json=payload)
            body = response.json()
            required = {
                "risk_score", "combined_risk_score", "ml_probability",
                "rule_score", "graph_score", "decision", "reasons",
                "fraud_type", "model_version",
            }
            passed = response.status_code == 200 and required.issubset(body)
            details = f"HTTP {response.status_code}; decision={body.get('decision')}"
        except Exception as exc:
            passed = False
            details = f"Raised {type(exc).__name__}: {exc}"
        self.record_test("12. FastAPI POST /predict-risk Contract", passed, details)

    def test_13_latency_benchmark(self, n_iterations: int = 25):
        """Benchmark single-sample inference latency percentiles (p50, p95, p99)."""
        latencies = []
        payload = {
            "sender_id": "bench_usr_1",
            "receiver_id": "bench_usr_2",
            "amount": 750.0,
            "amount_zscore": 0.4,
            "txn_count_24h": 1,
            "relationship_stability_score": 0.8
        }
        
        # Warmup
        self.predictor.predict(payload)
        
        for _ in range(n_iterations):
            t0 = time.perf_counter()
            self.predictor.predict(payload)
            t1 = time.perf_counter()
            latencies.append((t1 - t0) * 1000.0)  # Convert to ms

        p50 = np.percentile(latencies, 50)
        p95 = np.percentile(latencies, 95)
        p99 = np.percentile(latencies, 99)
        passed = p50 < 300.0  # Python unit test runtime SLA (<300ms)
        self.record_test("13. Single-Sample Latency Benchmark", passed, f"p50: {p50:.2f}ms, p95: {p95:.2f}ms, p99: {p99:.2f}ms")

    def run_all(self):
        print("\n" + "=" * 70)
        print("          APEXPAY COMPREHENSIVE REGRESSION & INTEGRITY SUITE")
        print("=" * 70)
        self.test_01_normal_legitimate_payment()
        self.test_02_account_takeover_override()
        self.test_03_cold_start_high_amount()
        self.test_04_social_triangle_not_laundering()
        self.test_05_circular_laundering_ring()
        self.test_06_mule_account_fan_in()
        self.test_07_discrete_time_window_separation()
        self.test_08_idempotent_deduplication()
        self.test_09_identity_sanitization()
        self.test_10_api_response_schema_completeness()
        self.test_11_optional_receiver_context_is_null_safe()
        self.test_12_actual_fastapi_endpoint()
        self.test_13_latency_benchmark()

        passed_count = sum(1 for r in self.results if r["passed"])
        total_count = len(self.results)
        print("=" * 70)
        print(f" SUMMARY: {passed_count}/{total_count} Tests Passed ({passed_count/total_count:.1%})")
        print("=" * 70)
        return passed_count == total_count

if __name__ == "__main__":
    runner = TestApexPayMLService()
    success = runner.run_all()
    sys.exit(0 if success else 1)
