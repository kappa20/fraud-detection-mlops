"""Tests de l'API FastAPI (Livrable 7/8).

Utilise un modèle scikit-learn factice entraîné à la volée pour ne pas
dépendre du pipeline ML complet (dlt/dbt/MLflow) en CI : ces tests
vérifient le contrat de l'API (schéma, codes HTTP), pas la qualité du
modèle — déjà couverte par docs/ml/experiments_summary.md.
"""

import joblib
import numpy as np
from fastapi.testclient import TestClient
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from api.main import app
from api.main import model as api_model


def _make_dummy_model():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(50, 31))  # v1-v28 + amount + log_amount + hour_of_day
    y = rng.integers(0, 2, size=50)
    pipeline = Pipeline([("scaler", StandardScaler()), ("clf", LogisticRegression())])
    pipeline.fit(X, y)
    return pipeline


def _valid_payload() -> dict:
    return {"time": 406, **{f"v{i}": 0.0 for i in range(1, 29)}, "amount": 149.62}


def test_health_and_predict_happy_path(tmp_path):
    dummy_path = tmp_path / "model.pkl"
    joblib.dump(_make_dummy_model(), dummy_path)
    api_model._model_path = dummy_path

    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["model_loaded"] is True

        resp = client.post("/predict", json=_valid_payload())
        assert resp.status_code == 200
        body = resp.json()
        assert 0.0 <= body["fraud_probability"] <= 1.0
        assert isinstance(body["is_fraud"], bool)
        assert body["threshold"] == api_model.threshold


def test_predict_rejects_incomplete_payload(tmp_path):
    dummy_path = tmp_path / "model.pkl"
    joblib.dump(_make_dummy_model(), dummy_path)
    api_model._model_path = dummy_path

    payload = _valid_payload()
    del payload["v28"]

    with TestClient(app) as client:
        resp = client.post("/predict", json=payload)
        assert resp.status_code == 422


def test_predict_rejects_negative_amount(tmp_path):
    dummy_path = tmp_path / "model.pkl"
    joblib.dump(_make_dummy_model(), dummy_path)
    api_model._model_path = dummy_path

    payload = _valid_payload()
    payload["amount"] = -10.0

    with TestClient(app) as client:
        resp = client.post("/predict", json=payload)
        assert resp.status_code == 422


def test_metrics_endpoint_exposed():
    with TestClient(app) as client:
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "python_gc_objects_collected_total" in resp.text
