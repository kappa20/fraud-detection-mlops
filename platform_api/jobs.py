"""Exécution suivie des jobs du pipeline (Dagster / entraînement) lancés par
la plateforme.

Remplace l'ancien `pipeline.py` : même principe (sous-processus en arrière-
plan, jamais dans la requête HTTP — un ré-entraînement RandomForest sur
~285k lignes prend plusieurs dizaines de secondes), mais le sous-processus
est lu ligne à ligne pour suivre l'avancement étape par étape, et chaque
changement d'état est journalisé dans data/state/runs.jsonl (dernière ligne
d'un `run_id` = état courant, voir state.load_runs).

Le suivi d'étapes repose sur les événements STEP_START / STEP_SUCCESS /
STEP_FAILURE que `dagster job execute` écrit dans ses logs. Si ce format
changait, l'exécution reste correcte : on retombe sur une étape unique
"Pipeline" avec la fin du journal.

Un seul job à la fois : les étapes écrivent le même DuckDB, les mêmes
artefacts MLflow et le même CSV.
"""

import os
import re
import subprocess
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from platform_api import state

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DAGSTER_FILE = "orchestration_dagster/fraud_dagster/job.py"

# Nom de l'op Dagster -> libellé affiché (ordre = ordre d'exécution).
STAGE_LABELS = {
    "ingest": "Ingestion",
    "validate": "Validation",
    "transform": "Transformation",
    "test_data": "Tests",
    "train_model": "Entraînement",
    "check_drift": "Contrôle de dérive",
    "register_and_promote": "Registry",
}

_PIPELINE_OPS = ["ingest", "validate", "transform", "test_data"]
_ALL_OPS = [*_PIPELINE_OPS, "train_model", "check_drift", "register_and_promote"]

# kind -> (commande, ops suivis). "pipeline" = ingestion -> tests ;
# "continuous" = pipeline complet jusqu'au registry, utilisé pour le
# ré-entraînement (le modèle s'entraîne sur le DuckDB, qui doit d'abord être
# reconstruit depuis le CSV à jour : entraîner seul serait trompeur).
JOB_KINDS: dict[str, tuple] = {
    "pipeline": (lambda: ["dagster", "job", "execute", "-f", DAGSTER_FILE, "-a", "fraud_pipeline_job"], _PIPELINE_OPS),
    "continuous": (
        lambda: ["dagster", "job", "execute", "-f", DAGSTER_FILE, "-a", "continuous_training_job"],
        _ALL_OPS,
    ),
}

_STEP_EVENT_RE = re.compile(r" - (\w+) - (STEP_START|STEP_SUCCESS|STEP_FAILURE) - ")
LOG_TAIL_LINES = 80


class JobBusyError(RuntimeError):
    """Un autre job est déjà en cours d'exécution."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Job:
    run_id: str
    kind: str
    trigger: str
    user: str | None
    rows_added: int
    dvc_md5: str | None
    commit_sha: str | None
    started_at: str
    stages: list[dict]
    status: str = "running"
    note: str | None = None
    log: deque = field(default_factory=lambda: deque(maxlen=LOG_TAIL_LINES))

    def record(self) -> dict:
        return {
            "timestamp": self.started_at,
            "trigger": self.trigger,
            "rows_added": self.rows_added,
            "dvc_md5": self.dvc_md5,
            "commit_sha": self.commit_sha,
            "status": self.status,
            "note": self.note,
            "run_id": self.run_id,
            "job_kind": self.kind,
            "user": self.user,
            "stages": [dict(stage) for stage in self.stages],
            "log_tail": "\n".join(self.log),
        }


_lock = threading.Lock()
_jobs: dict[str, Job] = {}
_running_id: str | None = None


def create_job(
    kind: str,
    trigger: str,
    user: str | None = None,
    rows_added: int = 0,
    dvc_md5: str | None = None,
    commit_sha: str | None = None,
) -> Job:
    """Enregistre un job "en cours" (et son entrée dans l'historique) ; lève
    JobBusyError si un autre job tourne. L'exécution se fait via `execute`."""
    global _running_id
    if kind not in JOB_KINDS:
        raise ValueError(f"Type de job inconnu : {kind!r}")
    with _lock:
        if _running_id is not None and _jobs[_running_id].status == "running":
            raise JobBusyError("Un job est déjà en cours d'exécution.")
        job = Job(
            run_id=uuid.uuid4().hex[:12],
            kind=kind,
            trigger=trigger,
            user=user,
            rows_added=rows_added,
            dvc_md5=dvc_md5,
            commit_sha=commit_sha,
            started_at=_now(),
            stages=[{"name": STAGE_LABELS[op], "status": "pending"} for op in JOB_KINDS[kind][1]],
        )
        _jobs[job.run_id] = job
        _running_id = job.run_id
    state.append_run(job.record())
    return job


def get_job(run_id: str) -> Job | None:
    return _jobs.get(run_id)


def _stage_by_op(job: Job, op: str) -> dict | None:
    label = STAGE_LABELS.get(op)
    return next((s for s in job.stages if s["name"] == label), None)


def _on_line(job: Job, line: str) -> None:
    job.log.append(line.rstrip())
    match = _STEP_EVENT_RE.search(line)
    if not match:
        return
    stage = _stage_by_op(job, match.group(1))
    if stage is None:
        return
    event = match.group(2)
    if event == "STEP_START":
        stage.update(status="running", started_at=_now())
    else:
        stage.update(status="completed" if event == "STEP_SUCCESS" else "failed", ended_at=_now())
    state.append_run(job.record())


def execute(job: Job) -> None:
    """Exécute le job (bloquant — à appeler depuis un thread ou une
    BackgroundTask) puis journalise son état final."""
    global _running_id

    cmd = JOB_KINDS[job.kind][0]()
    env = _job_env()
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=PROJECT_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        for line in proc.stdout:
            _on_line(job, line)
        returncode = proc.wait()

        succeeded = returncode == 0
        if succeeded and not any(s["status"] != "pending" for s in job.stages):
            job.stages = [{"name": "Pipeline", "status": "completed", "ended_at": _now()}]
        job.status = "completed" if succeeded else "failed"
        job.note = (
            "Pipeline exécuté avec succès."
            if succeeded
            else "Échec du job : " + "\n".join(list(job.log)[-15:])[-2000:]
        )
    except Exception as exc:  # noqa: BLE001 — toute erreur doit finir dans l'historique, pas tuer le thread
        job.status = "failed"
        job.note = f"Erreur d'exécution : {exc}"
    finally:
        with _lock:
            if _running_id == job.run_id:
                _running_id = None
        state.append_run(job.record())


def start_in_background(job: Job) -> None:
    threading.Thread(target=execute, args=(job,), daemon=True, name=f"job-{job.run_id}").start()


def _job_env() -> dict:
    env = dict(os.environ)
    # Promotion automatique désactivée : ml/register_model.py enregistre le
    # candidat en Staging et attend l'approbation dans le tableau de bord.
    if not state.load_state()["auto_promote"]:
        env["FRAUD_REGISTER_NO_PROMOTE"] = "1"
    return env


def snapshot(run_id: str) -> dict | None:
    job = _jobs.get(run_id)
    return job.record() if job else None


def is_busy() -> bool:
    with _lock:
        return _running_id is not None and _jobs[_running_id].status == "running"
