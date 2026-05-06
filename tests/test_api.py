"""End-to-end smoke test using the in-memory test client.

Requires: a trained model at the path in settings, plus reachable Redis + Postgres
(use docker-compose for local). Skips if any dependency is missing.
"""
import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    if not os.path.exists("models/surrogate-v1.joblib"):
        pytest.skip("model artifact not present; run train_surrogate first")
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_predict_basic(client):
    r = client.post("/v1/predict", json={"heat_flux": 600, "porosity": 0.7, "ambient_c": 25, "wind_mps": 2})
    assert r.status_code == 200
    body = r.json()
    t = body["temps"]
    assert t["t1_c"] > t["t2_c"] > t["t3_c"] > t["t4_c"]
    assert body["model_version"] == "v1"


def test_predict_validation_rejects_out_of_range(client):
    r = client.post("/v1/predict", json={"heat_flux": 1500, "porosity": 0.7})
    assert r.status_code == 422


def test_simulate_returns_drying_time(client):
    r = client.post(
        "/v1/simulate",
        json={"heat_flux": 700, "porosity": 0.7, "ambient_c": 25, "wind_mps": 1, "crop": "tomato"},
    )
    assert r.status_code == 200
    trays = r.json()["trays"]
    assert len(trays) == 4
    for t in trays:
        assert t["drying_time_hours"] > 0
