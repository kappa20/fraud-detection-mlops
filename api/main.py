"""Service FastAPI de scoring de fraude (Livrable 7).

Endpoints :
    GET  /health   - sonde de disponibilité (Livrable 9 - Monitoring)
    POST /predict  - score de fraude pour une transaction
    GET  /metrics  - métriques Prometheus (disponibilité, temps de réponse)

Usage local :
    uvicorn api.main:app --reload
"""

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator

from api.model_loader import FraudModel, ModelNotLoadedError, get_model_version
from api.schemas import PredictionOutput, TransactionInput

model = FraudModel()

PREDICTIONS_LOG = Path(__file__).resolve().parent.parent / "monitoring" / "predictions_log.jsonl"


def _log_prediction(transaction: TransactionInput, proba: float, is_fraud: bool) -> None:
    """Journalise chaque prédiction (Livrable 9 — métriques ML en
    production), réutilisé par monitoring/drift_check.py pour comparer la
    distribution récente à celle d'entraînement."""
    PREDICTIONS_LOG.parent.mkdir(exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "amount": transaction.amount,
        "fraud_probability": proba,
        "is_fraud": is_fraud,
        "model_version": get_model_version(),
    }
    with PREDICTIONS_LOG.open("a") as f:
        f.write(json.dumps(record) + "\n")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        model.load()
    except ModelNotLoadedError:
        # /health reportera model_loaded=False plutôt que de faire planter
        # le démarrage du service (utile en développement, avant Phase D).
        pass
    yield


app = FastAPI(
    title="Fraud Detection API",
    description="Service de scoring de transactions bancaires — projet MLOps & DataOps.",
    version="1.0.0",
    lifespan=lifespan,
)

Instrumentator().instrument(app).expose(app)  # expose GET /metrics


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": model.is_loaded,
        "model_version": get_model_version() if model.is_loaded else None,
    }


@app.post("/predict", response_model=PredictionOutput)
def predict(transaction: TransactionInput):
    if not model.is_loaded:
        raise HTTPException(status_code=503, detail="Modèle non chargé. Voir GET /health.")

    proba = model.predict_proba(transaction.model_dump())
    is_fraud = proba >= model.threshold
    _log_prediction(transaction, proba, is_fraud)
    return PredictionOutput(
        fraud_probability=round(proba, 6),
        is_fraud=is_fraud,
        threshold=model.threshold,
        model_version=get_model_version(),
    )
