"""Service FastAPI de la plateforme d'ingestion continue pour la banque.

Distinct de api/main.py (scoring temps réel) : ce service reçoit les
nouvelles transactions de la banque (ou des transactions synthétiques
générées pour la démo), fait grandir data/raw/creditcard.csv, et
déclenche le versioning DVC + git une fois le seuil de mises à jour en
attente atteint (voir platform_api/state.py et versioning.py).

Le déclenchement du pipeline de ré-entraînement complet
(orchestration_dagster/fraud_dagster/job.py étendu, promotion MLflow)
n'est pas encore câblé ici — voir le TODO dans _ingest_and_maybe_trigger.

Usage local :
    uvicorn platform_api.main:app --reload --port 8000
"""

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException

from platform_api import dataset, simulate, state, versioning
from platform_api.schemas import (
    IngestRequest,
    IngestResponse,
    RunRecord,
    SimulateRequest,
    StatusResponse,
    ThresholdResponse,
    ThresholdUpdate,
)

app = FastAPI(
    title="Fraud Detection — Continuous Training Platform",
    description="Ingestion des données bancaires, seuil de déclenchement, simulation de dérive.",
    version="0.1.0",
)


def _ingest_and_maybe_trigger(rows: list[dict], trigger: str) -> IngestResponse:
    dataset.append_rows(rows)

    current_state = state.load_state()
    current_state["pending_count"] += len(rows)
    triggered = False

    if current_state["pending_count"] >= current_state["threshold"]:
        rows_added = current_state["pending_count"]
        commit_message = f"data: +{rows_added} transactions ({trigger}) — seuil de {current_state['threshold']} atteint"
        try:
            result = versioning.version_dataset(commit_message)
            run_record = RunRecord(
                timestamp=result["timestamp"],
                trigger=trigger,
                rows_added=rows_added,
                dvc_md5=result["md5"],
                commit_sha=result["commit_sha"],
                status="versioned",
                # TODO (Day 2) : déclencher ici le job Dagster étendu
                # (train -> drift_check -> register -> promotion MLflow)
                # au lieu de se contenter de versionner le dataset.
                note="Versioning DVC/git effectué ; déclenchement du ré-entraînement pas encore câblé.",
            )
            triggered = True
        except versioning.VersioningError as exc:
            run_record = RunRecord(
                timestamp=datetime.now(timezone.utc).isoformat(),
                trigger=trigger,
                rows_added=rows_added,
                status="failed",
                note=str(exc),
            )
        state.append_run(run_record.model_dump())
        current_state["pending_count"] = 0

    state.save_state(current_state)
    return IngestResponse(
        rows_ingested=len(rows),
        pending_count=current_state["pending_count"],
        threshold=current_state["threshold"],
        triggered=triggered,
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/status", response_model=StatusResponse)
def status():
    current_state = state.load_state()
    last_run = state.load_last_run()
    return StatusResponse(
        pending_count=current_state["pending_count"],
        threshold=current_state["threshold"],
        dataset_rows=dataset.row_count(),
        last_run=RunRecord(**last_run) if last_run else None,
    )


@app.get("/config/threshold", response_model=ThresholdResponse)
def get_threshold():
    current_state = state.load_state()
    return ThresholdResponse(threshold=current_state["threshold"], pending_count=current_state["pending_count"])


@app.put("/config/threshold", response_model=ThresholdResponse)
def set_threshold(update: ThresholdUpdate):
    current_state = state.load_state()
    current_state["threshold"] = update.threshold
    state.save_state(current_state)
    return ThresholdResponse(threshold=current_state["threshold"], pending_count=current_state["pending_count"])


@app.post("/data/ingest", response_model=IngestResponse)
def ingest(request: IngestRequest):
    rows = [t.model_dump() for t in request.transactions]
    return _ingest_and_maybe_trigger(rows, trigger="ingest")


@app.post("/data/simulate", response_model=IngestResponse)
def simulate_data(request: SimulateRequest):
    try:
        rows = simulate.generate_synthetic_rows(request.n, request.drift_intensity)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _ingest_and_maybe_trigger(rows, trigger="simulate")


@app.get("/runs", response_model=list[RunRecord])
def runs(limit: int = 50):
    return [RunRecord(**r) for r in state.load_runs(limit)]
