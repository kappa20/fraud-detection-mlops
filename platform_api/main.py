"""Service FastAPI de la plateforme d'ingestion continue pour la banque.

Distinct de api/main.py (scoring temps réel) : ce service reçoit les
nouvelles transactions de la banque (ou des transactions synthétiques
générées pour la démo), fait grandir data/raw/creditcard.csv, et
déclenche le versioning DVC + git une fois le seuil de mises à jour en
attente atteint (voir platform_api/state.py et versioning.py), puis le
pipeline complet de ré-entraînement en arrière-plan (voir pipeline.py).

Usage local :
    uvicorn platform_api.main:app --reload --port 8000
"""

from datetime import datetime, timezone

from fastapi import BackgroundTasks, FastAPI, HTTPException

from platform_api import dataset, pipeline, simulate, state, versioning
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


def _ingest_and_maybe_trigger(rows: list[dict], trigger: str, background_tasks: BackgroundTasks) -> IngestResponse:
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
                status="pipeline_running",
                note="Dataset versionné (DVC/git) ; pipeline complet (entraînement, dérive, registry) en cours.",
            )
            state.append_run(run_record.model_dump())
            background_tasks.add_task(
                pipeline.run_continuous_training_job,
                trigger=trigger,
                rows_added=rows_added,
                dvc_md5=result["md5"],
                commit_sha=result["commit_sha"],
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
def ingest(request: IngestRequest, background_tasks: BackgroundTasks):
    rows = [t.model_dump() for t in request.transactions]
    return _ingest_and_maybe_trigger(rows, trigger="ingest", background_tasks=background_tasks)


@app.post("/data/simulate", response_model=IngestResponse)
def simulate_data(request: SimulateRequest, background_tasks: BackgroundTasks):
    try:
        rows = simulate.generate_synthetic_rows(request.n, request.drift_intensity)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _ingest_and_maybe_trigger(rows, trigger="simulate", background_tasks=background_tasks)


@app.get("/runs", response_model=list[RunRecord])
def runs(limit: int = 50):
    return [RunRecord(**r) for r in state.load_runs(limit)]
