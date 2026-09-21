"""Service FastAPI de la plateforme d'opérations de la banque.

Distinct de api/main.py (scoring temps réel) : ce service reçoit les
nouvelles transactions de la banque (ou des transactions synthétiques
générées pour la démo), permet de corriger le dataset à la main depuis le
tableau de bord (chaque lot de corrections = une version DVC + un commit git,
voir versioning.py), surveille la dérive des données, et déclenche le
pipeline complet de ré-entraînement en arrière-plan (voir jobs.py).

Toutes les routes, sauf /health, /auth/login et l'interface statique,
exigent un jeton (voir auth.py).

Usage local :
    uvicorn platform_api.main:app --reload --port 8000
"""

import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse

from platform_api import (
    auth,
    dataset,
    deploy,
    drift,
    jobs,
    metrics,
    models,
    services,
    simulate,
    state,
    transactions,
    versioning,
)
from platform_api.schemas import (
    ChangeBatch,
    ChangeResult,
    ConfigResponse,
    ConfigUpdate,
    IngestRequest,
    IngestResponse,
    LoginRequest,
    LoginResponse,
    PromotionDecision,
    RunRecord,
    SimulateRequest,
    StatusResponse,
    ThresholdResponse,
    ThresholdUpdate,
)

app = FastAPI(
    title="Fraud Detection — Plateforme d'opérations",
    description="Transactions, versions du dataset (DVC), pipeline, dérive, registry.",
    version="0.2.0",
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Interface React construite par Dockerfile.platform (hors de /app, que
# docker-compose remplace par un bind mount du dépôt) ou, en local,
# `npm run build` dans platform_ui/.
UI_DIST_ENV = "PLATFORM_UI_DIST"
DEFAULT_UI_DIST = PROJECT_ROOT / "platform_ui" / "dist"

_UI_MISSING_PAGE = """<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
<title>Plateforme d'entraînement continu</title></head><body style="font-family:sans-serif;padding:2rem">
<h1>Plateforme d'entraînement continu</h1>
<p>L'interface n'est pas construite : lancez <code>npm run build</code> dans <code>platform_ui/</code>
(ou utilisez l'image Docker), ou consultez l'API sur <a href="/docs">/docs</a>.</p></body></html>"""

# Routes protégées : toutes, sauf santé, login et interface statique.
protected = APIRouter(dependencies=[Depends(auth.current_user)])


def _ui_dist() -> Path:
    return Path(os.environ.get(UI_DIST_ENV, DEFAULT_UI_DIST))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------- public


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics():
    """Dérive (PSI), dataset, dernier run — scrapé par Prometheus (metrics.py)."""
    return Response(content=metrics.render(), media_type=metrics.CONTENT_TYPE)


@app.post("/auth/login", response_model=LoginResponse)
def login(request: LoginRequest):
    if not auth.verify_credentials(request.username, request.password):
        raise HTTPException(status_code=401, detail="Identifiant ou mot de passe incorrect.")
    return LoginResponse(token=auth.create_token(request.username), username=request.username)


@app.get("/", response_class=HTMLResponse)
def dashboard():
    index = _ui_dist() / "index.html"
    return index.read_text() if index.exists() else _UI_MISSING_PAGE


@app.get("/assets/{asset_path:path}")
def ui_asset(asset_path: str):
    assets_root = (_ui_dist() / "assets").resolve()
    target = (assets_root / asset_path).resolve()
    if assets_root not in target.parents or not target.is_file():  # refuse aussi ../ (path traversal)
        raise HTTPException(status_code=404)
    return FileResponse(target)


# ------------------------------------------------- pipeline / versioning helpers


def _version_and_launch(trigger: str, user: str | None, background_tasks: BackgroundTasks) -> bool:
    """Versionne (DVC + git) les lignes en attente puis lance le pipeline
    complet en arrière-plan. Renvoie True si le pipeline a démarré.

    Échec de versioning : l'échec est journalisé et le compteur n'est PAS remis
    à zéro (ces lignes n'ont pas été prises en compte, le prochain déclencheur
    doit retenter). Job déjà en cours : la version est créée mais le pipeline
    n'est pas relancé (noté dans l'historique)."""
    current_state = state.load_state()
    rows_added = current_state["pending_count"]
    reasons = {
        "ingest": f"seuil de {current_state['threshold']} atteint",
        "simulate": f"seuil de {current_state['threshold']} atteint",
        "drift_auto": f"PSI ≥ {current_state['psi_threshold']}",
    }
    commit_sha, dvc_md5 = None, versioning._extract_md5()

    if rows_added > 0:
        message = f"data: +{rows_added} transactions ({trigger}) — {reasons.get(trigger, 'déclenchement manuel')}"
        try:
            result = versioning.version_dataset(message)
        except versioning.VersioningError as exc:
            state.append_run(
                RunRecord(
                    timestamp=_now(),
                    trigger=trigger,
                    rows_added=rows_added,
                    status="failed",
                    note=str(exc),
                    user=user,
                ).model_dump()
            )
            return False
        commit_sha, dvc_md5 = result["commit_sha"], result["md5"]
        state.append_version(
            {
                "commit_sha": commit_sha,
                "timestamp": result["timestamp"],
                "kind": trigger,
                "user": user,
                "rows_changed": rows_added,
                "rows_total": dataset.row_count(),
                "summary": message,
            }
        )

    try:
        job = jobs.create_job(
            "continuous", trigger, user=user, rows_added=rows_added, dvc_md5=dvc_md5, commit_sha=commit_sha
        )
    except jobs.JobBusyError:
        state.append_run(
            RunRecord(
                timestamp=_now(),
                trigger=trigger,
                rows_added=rows_added,
                dvc_md5=dvc_md5,
                commit_sha=commit_sha,
                status="versioned",
                note="Dataset versionné ; pipeline non relancé (un job est déjà en cours).",
                user=user,
            ).model_dump()
        )
        _reset_pending()
        return False

    background_tasks.add_task(jobs.execute, job)
    _reset_pending()
    return True


def _bump_epoch() -> None:
    current_state = state.load_state()
    current_state["dataset_epoch"] += 1
    state.save_state(current_state)


def _reset_pending() -> None:
    current_state = state.load_state()
    current_state["pending_count"] = 0
    state.save_state(current_state)


def _check_drift_and_maybe_retrain(trigger: str, user: str | None, background_tasks: BackgroundTasks) -> bool:
    """Après une modification du dataset : enregistre le PSI et, si le
    ré-entraînement automatique est activé et le seuil dépassé, lance le pipeline."""
    try:
        summary = drift.record_check(trigger)
    except Exception:  # noqa: BLE001 — la dérive est un signal annexe : elle ne doit jamais faire échouer l'ingestion
        return False
    if drift.should_auto_retrain(summary):
        return _version_and_launch("drift_auto", user, background_tasks)
    return False


def _ingest_and_maybe_trigger(
    rows: list[dict], trigger: str, user: str | None, background_tasks: BackgroundTasks
) -> IngestResponse:
    dataset.append_rows(rows)

    current_state = state.load_state()
    current_state["pending_count"] += len(rows)
    state.save_state(current_state)

    if current_state["pending_count"] >= current_state["threshold"]:
        triggered = _version_and_launch(trigger, user, background_tasks)
        _record_drift_quietly(trigger)
    else:
        triggered = _check_drift_and_maybe_retrain(trigger, user, background_tasks)

    current_state = state.load_state()
    return IngestResponse(
        rows_ingested=len(rows),
        pending_count=current_state["pending_count"],
        threshold=current_state["threshold"],
        triggered=triggered,
    )


def _record_drift_quietly(source: str) -> None:
    try:
        drift.record_check(source)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------- status / config


@protected.get("/status", response_model=StatusResponse, tags=["Pilotage"])
def status():
    current_state = state.load_state()
    last_run = state.load_last_run()
    return StatusResponse(
        pending_count=current_state["pending_count"],
        threshold=current_state["threshold"],
        dataset_rows=dataset.row_count(),
        last_run=RunRecord(**last_run) if last_run else None,
    )


@protected.get("/config/threshold", response_model=ThresholdResponse, tags=["Pilotage"])
def get_threshold():
    current_state = state.load_state()
    return ThresholdResponse(threshold=current_state["threshold"], pending_count=current_state["pending_count"])


@protected.put("/config/threshold", response_model=ThresholdResponse, tags=["Pilotage"])
def set_threshold(update: ThresholdUpdate):
    current_state = state.load_state()
    current_state["threshold"] = update.threshold
    state.save_state(current_state)
    return ThresholdResponse(threshold=current_state["threshold"], pending_count=current_state["pending_count"])


@protected.get("/config", response_model=ConfigResponse, tags=["Pilotage"])
def get_config():
    current_state = state.load_state()
    return ConfigResponse(**{k: current_state[k] for k in ConfigResponse.model_fields})


@protected.put("/config", response_model=ConfigResponse, tags=["Pilotage"])
def update_config(update: ConfigUpdate):
    current_state = state.load_state()
    current_state.update(update.model_dump(exclude_none=True))
    state.save_state(current_state)
    return ConfigResponse(**{k: current_state[k] for k in ConfigResponse.model_fields})


# ---------------------------------------------------------------- ingestion


@protected.post("/data/ingest", response_model=IngestResponse, tags=["Pilotage"])
def ingest(request: IngestRequest, background_tasks: BackgroundTasks, user: str = Depends(auth.current_user)):
    rows = [t.model_dump() for t in request.transactions]
    return _ingest_and_maybe_trigger(rows, trigger="ingest", user=user, background_tasks=background_tasks)


@protected.post("/data/simulate", response_model=IngestResponse, tags=["Pilotage"])
def simulate_data(
    request: SimulateRequest, background_tasks: BackgroundTasks, user: str = Depends(auth.current_user)
):
    try:
        rows = simulate.generate_synthetic_rows(request.n, request.drift_intensity)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _ingest_and_maybe_trigger(rows, trigger="simulate", user=user, background_tasks=background_tasks)


# ---------------------------------------------------------------- transactions (CRUD)


@protected.get("/transactions", tags=["Transactions"])
def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=transactions.MAX_PAGE_SIZE),
    sort: str = "id",
    order: str = Query("asc", pattern="^(asc|desc)$"),
    amount_min: float | None = None,
    amount_max: float | None = None,
    is_fraud: int | None = Query(None, ge=0, le=1),
    time_min: float | None = None,
    time_max: float | None = None,
):
    try:
        return transactions.query_transactions(
            page, page_size, sort, order, amount_min, amount_max, is_fraud, time_min, time_max
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@protected.get("/transactions/export", tags=["Transactions"])
def export_transactions(ids: str = Query(..., description="Identifiants séparés par des virgules")):
    try:
        id_list = [int(part) for part in ids.split(",") if part.strip()]
        stream = transactions.export_csv(id_list)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return StreamingResponse(
        stream,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="transactions_selection.csv"'},
    )


@protected.get("/transactions/{row_id}", tags=["Transactions"])
def get_transaction(row_id: int):
    row = transactions.get_transaction(row_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Transaction {row_id} introuvable.")
    return row


@protected.post("/transactions/changes", response_model=ChangeResult, tags=["Transactions"])
def apply_changes(batch: ChangeBatch, user: str = Depends(auth.current_user)):
    """Applique un lot de créations / modifications / suppressions au CSV, puis
    `dvc add` + commit git (un commit par lot). Si le versioning échoue, le CSV
    est remis dans son état d'avant : le lot n'est appliqué qu'en entier."""
    if not (batch.creates or batch.updates or batch.deletes):
        raise HTTPException(status_code=422, detail="Aucune modification à enregistrer.")
    if jobs.is_busy():
        raise HTTPException(status_code=409, detail="Un job est en cours : réessayez à la fin de son exécution.")

    backup = Path(tempfile.mkstemp(suffix=".csv.bak")[1])
    try:
        with dataset.WRITE_LOCK:
            shutil.copy2(dataset.RAW_CSV_PATH, backup)
            try:
                counts = transactions.apply_changes(
                    batch.base_version,
                    [c.model_dump() for c in batch.creates],
                    [(u.id, u.fields.model_dump(exclude_none=True)) for u in batch.updates],
                    batch.deletes,
                )
            except transactions.StaleDatasetError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            except transactions.UnknownRowError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

            parts = [
                f"{counts[key]} row{'s' if counts[key] > 1 else ''} {label}"
                for key, label in (("rows_created", "created"), ("rows_updated", "updated"), ("rows_deleted", "deleted"))
                if counts[key]
            ]
            message = f"Manual correction: {', '.join(parts)} — via dashboard, user {user}, {_now()}"
            try:
                result = versioning.version_dataset(message)
            except versioning.VersioningError as exc:
                _restore_csv(backup)
                versioning.discard_uncommitted_dvc_change()
                raise HTTPException(
                    status_code=502, detail=f"Versioning impossible, corrections annulées : {exc}"
                ) from exc
            _bump_epoch()
    finally:
        backup.unlink(missing_ok=True)

    total_changed = counts["rows_created"] + counts["rows_updated"] + counts["rows_deleted"]
    state.append_version(
        {
            "commit_sha": result["commit_sha"],
            "timestamp": result["timestamp"],
            "kind": "dashboard_edit",
            "user": user,
            "rows_changed": total_changed,
            "rows_total": dataset.row_count(),
            "summary": message,
        }
    )
    state.append_run(
        RunRecord(
            timestamp=result["timestamp"],
            trigger="dashboard_edit",
            rows_added=total_changed,
            dvc_md5=result["md5"],
            commit_sha=result["commit_sha"],
            status="versioned",
            note=message,
            user=user,
        ).model_dump()
    )
    _record_drift_quietly("dashboard_edit")
    return ChangeResult(
        **counts, commit_sha=result["commit_sha"], dvc_md5=result["md5"], message=message
    )


def _restore_csv(backup: Path) -> None:
    shutil.copy2(backup, dataset.RAW_CSV_PATH)


# ---------------------------------------------------------------- versions


@protected.get("/versions", tags=["Versions du dataset"])
def list_versions(limit: int = Query(50, ge=1, le=200)):
    try:
        return versioning.list_versions(limit)
    except versioning.VersioningError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@protected.post("/versions/{commit_sha}/rollback", tags=["Versions du dataset"])
def rollback_version(commit_sha: str, user: str = Depends(auth.current_user)):
    if jobs.is_busy():
        raise HTTPException(status_code=409, detail="Un job est en cours : réessayez à la fin de son exécution.")
    with dataset.WRITE_LOCK:
        current_state = state.load_state()
        try:
            if current_state["pending_count"] > 0:
                # Ne rien perdre : les lignes en attente sont d'abord versionnées.
                pre_message = f"data: +{current_state['pending_count']} transactions (avant rollback)"
                pre = versioning.version_dataset(pre_message)
                state.append_version(
                    {
                        "commit_sha": pre["commit_sha"],
                        "timestamp": pre["timestamp"],
                        "kind": "pre_rollback",
                        "user": user,
                        "rows_changed": current_state["pending_count"],
                        "rows_total": dataset.row_count(),
                        "summary": pre_message,
                    }
                )
            message = f"Rollback dataset to {commit_sha[:8]} — via dashboard, user {user}, {_now()}"
            result = versioning.rollback(commit_sha, message)
        except versioning.VersioningError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        state.append_version(
            {
                "commit_sha": result["commit_sha"],
                "timestamp": result["timestamp"],
                "kind": "rollback",
                "user": user,
                "rows_changed": None,
                "rows_total": dataset.row_count(),
                "summary": message,
            }
        )
        state.append_run(
            RunRecord(
                timestamp=result["timestamp"],
                trigger="rollback",
                rows_added=0,
                dvc_md5=result["md5"],
                commit_sha=result["commit_sha"],
                status="versioned",
                note=message,
                user=user,
            ).model_dump()
        )
        _reset_pending()
        _bump_epoch()
    _record_drift_quietly("rollback")
    return {"commit_sha": result["commit_sha"], "dvc_md5": result["md5"], "message": message}


# ---------------------------------------------------------------- runs / jobs


_STATUS_FILTERS = {
    "completed": {"completed", "versioned"},
    "running": {"running", "pipeline_running"},
    "failed": {"failed"},
}


@protected.get("/runs", response_model=list[RunRecord], tags=["Historique"])
def runs(limit: int = Query(50, ge=1, le=500), status: str | None = Query(None, pattern="^(completed|running|failed)$")):
    records = state.load_runs(500 if status else limit)
    if status:
        records = [r for r in records if r["status"] in _STATUS_FILTERS[status]][-limit:]
    return [RunRecord(**r) for r in records]


@protected.get("/jobs/{run_id}", response_model=RunRecord, tags=["Historique"])
def job_status(run_id: str):
    live = jobs.snapshot(run_id)
    if live:
        return RunRecord(**live)
    for record in state.load_runs(500):
        if record["run_id"] == run_id:
            return RunRecord(**record)
    raise HTTPException(status_code=404, detail=f"Run {run_id} introuvable.")


def _start_job(kind: str, trigger: str, user: str, background_tasks: BackgroundTasks) -> dict:
    try:
        job = jobs.create_job(kind, trigger, user=user, dvc_md5=versioning._extract_md5())
    except jobs.JobBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    background_tasks.add_task(jobs.execute, job)
    return {"run_id": job.run_id}


@protected.post("/pipeline/run", tags=["Pipeline"])
def run_pipeline(background_tasks: BackgroundTasks, user: str = Depends(auth.current_user)):
    """Job Dagster fraud_pipeline_job : ingestion -> validation -> transformation -> tests."""
    return _start_job("pipeline", "manual_pipeline", user, background_tasks)


@protected.post("/pipeline/retrain", tags=["Pipeline"])
def retrain(background_tasks: BackgroundTasks, user: str = Depends(auth.current_user)):
    """Job Dagster continuous_training_job (pipeline complet jusqu'au registry).
    Les lignes en attente sont d'abord versionnées, comme pour un déclenchement automatique."""
    if jobs.is_busy():
        raise HTTPException(status_code=409, detail="Un job est déjà en cours d'exécution.")
    if state.load_state()["pending_count"] > 0:
        if not _version_and_launch("manual_retrain", user, background_tasks):
            raise HTTPException(status_code=502, detail="Versioning des lignes en attente impossible (voir l'historique).")
        return {"run_id": _latest_run_id()}
    return _start_job("continuous", "manual_retrain", user, background_tasks)


def _latest_run_id() -> str | None:
    latest = state.load_runs(1)
    return latest[-1]["run_id"] if latest else None


@protected.post("/runs/{run_id}/rerun", tags=["Historique"])
def rerun(run_id: str, background_tasks: BackgroundTasks, user: str = Depends(auth.current_user)):
    original = next((r for r in state.load_runs(500) if r["run_id"] == run_id), None)
    if original is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} introuvable.")
    if original["trigger"] in {"dashboard_edit", "rollback"}:
        raise HTTPException(status_code=422, detail="Ce type d'entrée (correction/rollback) n'est pas relançable.")
    return _start_job(original.get("job_kind") or "continuous", "rerun", user, background_tasks)


# ---------------------------------------------------------------- drift


@protected.get("/drift/current", tags=["Dérive"])
def drift_current():
    try:
        return drift.summary(drift.compute_current())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@protected.post("/drift/check", tags=["Dérive"])
def drift_check():
    """Recalcule le PSI et l'ajoute à l'historique (une fois par version du dataset)."""
    try:
        return drift.record_check("manual")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@protected.get("/drift/history", tags=["Dérive"])
def drift_history(n: int = Query(30, ge=1, le=200)):
    return state.load_drift_history(n)


@protected.get("/drift/distribution", tags=["Dérive"])
def drift_distribution(feature: str):
    try:
        return drift.distribution(feature)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Feature inconnue : {feature}") from exc


# ---------------------------------------------------------------- registry / déploiement


@protected.get("/models/comparison", tags=["Registry"])
def models_comparison():
    try:
        return models.comparison()
    except Exception as exc:  # noqa: BLE001 — MLflow (sqlite) indisponible ou schéma incompatible
        raise HTTPException(status_code=503, detail=f"MLflow Registry indisponible : {exc}") from exc


@protected.post("/models/approve", tags=["Registry"])
def models_approve(decision: PromotionDecision, user: str = Depends(auth.current_user)):
    try:
        result = models.approve(decision.version)
    except models.NoCandidateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    state.append_run(
        RunRecord(
            timestamp=_now(),
            trigger="manual_retrain",
            rows_added=0,
            commit_sha=result["commit_sha"],
            status="completed",
            note=f"Modèle v{result['version']} promu en Production par {user} ; redéploiement : {result['redeploy']['status']}.",
            user=user,
        ).model_dump()
    )
    return result


@protected.post("/models/reject", tags=["Registry"])
def models_reject(decision: PromotionDecision):
    try:
        return models.reject(decision.version)
    except models.NoCandidateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@protected.post("/models/redeploy", tags=["Registry"])
def models_redeploy():
    """Redemande le redémarrage de fraud-api (ex. si le premier essai a échoué)."""
    return deploy.restart_api()


# ---------------------------------------------------------------- écosystème


@protected.get("/services/health", tags=["Écosystème"])
def services_health():
    return services.check_all()


app.include_router(protected)
