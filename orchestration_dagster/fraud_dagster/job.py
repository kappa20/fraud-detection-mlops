"""Orchestration Dagster du pipeline DataOps (ingestion -> validation ->
transformation -> tests), pattern @op/@job identique à celui déjà validé
par le professeur dans le TP Chapitre 2
(td/tp_chapitre_2/tp_chapitre2_pipeline/pipeline/orchestrate.py), avec deux
améliorations : vérification explicite du code de retour de chaque étape
(fail-fast, absent du TP) et dépendances typées `Nothing` (idiome Dagster
documenté pour enchaîner des étapes sans transfert de données).

Déclenchement automatique (voir `defs` en bas de fichier) :
    - `nightly_pipeline_schedule` : fraud_pipeline_job chaque nuit à 02:00 ;
    - `dataset_version_sensor`    : fraud_pipeline_job quand le dataset change
      hors plateforme (nouvelle version DVC tirée par git pull / dvc pull).
Les deux nécessitent le démon Dagster (fourni par `dagster dev`, et par le
service `dagster` de docker-compose.yml, UI sur le port 4608).

Usage :
    cd projet
    dagster job execute -f orchestration_dagster/fraud_dagster/job.py -a fraud_pipeline_job
    # ou, pour l'UI web (+ démon : schedule et sensor) :
    dagster dev -f orchestration_dagster/fraud_dagster/job.py
"""

import fcntl
import json
import re
import subprocess
from contextlib import contextmanager
from pathlib import Path

from dagster import (
    DefaultScheduleStatus,
    DefaultSensorStatus,
    Definitions,
    In,
    Nothing,
    RunRequest,
    ScheduleDefinition,
    SensorEvaluationContext,
    SkipReason,
    job,
    op,
    sensor,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DVC_POINTER = PROJECT_ROOT / "data" / "raw" / "creditcard.csv.dvc"
RUNS_LOG = PROJECT_ROOT / "data" / "state" / "runs.jsonl"
LOCK_PATH = PROJECT_ROOT / "data" / "state" / "pipeline.lock"


@contextmanager
def _pipeline_lock():
    """Verrou inter-processus (fichier partagé via le bind mount du dépôt) :
    le DuckDB, le CSV et les artefacts MLflow n'admettent qu'un écrivain à la
    fois. `dagster job execute` (lancé par platform-api) et le démon Dagster
    (schedule/sensor) sont des processus distincts — leur file d'attente
    interne ne se voit pas, ce verrou sérialise donc leurs étapes."""
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _run(cmd: str) -> None:
    """Exécute une commande shell depuis la racine du projet et échoue
    explicitement (fail-fast) si le code de retour est non nul."""
    with _pipeline_lock():
        result = subprocess.run(cmd, shell=True, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        raise RuntimeError(f"Commande échouée (code {result.returncode}) : {cmd}")


@op
def ingest() -> None:
    """Étape 1 : ingestion automatisée dlt (CSV -> DuckDB, schéma raw)."""
    _run("python ingestion_dlt/run_pipeline.py")


@op(ins={"start": In(Nothing)})
def validate() -> None:
    """Étape 2 : validation shift-left du schéma et de la qualité minimale."""
    _run("python quality/validate_schema.py")


@op(ins={"start": In(Nothing)})
def transform() -> None:
    """Étape 3 : transformations dbt (staging + marts)."""
    _run("cd dbt_fraud && dbt run --profiles-dir .")


@op(ins={"start": In(Nothing)})
def test_data() -> None:
    """Étape 4 : tests de qualité dbt (schéma, contenu, métier)."""
    _run("cd dbt_fraud && dbt test --profiles-dir .")


@op(ins={"start": In(Nothing)})
def train_model() -> None:
    """Étape 5 (plateforme d'entraînement continu) : ré-entraînement sur le
    dataset à jour (voir ml/train.py)."""
    _run("python ml/train.py")


@op(ins={"start": In(Nothing)})
def check_drift() -> None:
    """Étape 6 : rafraîchit monitoring/drift_report.md sur le dataset à jour."""
    _run("python monitoring/drift_check.py")


@op(ins={"start": In(Nothing)})
def register_and_promote() -> None:
    """Étape 7 : enregistrement MLflow + porte de promotion (voir
    ml/register_model.py) — ne promeut en Production que si le nouveau
    candidat fait mieux (PR-AUC) que le modèle actuellement déployé.
    `--commit-artifacts` committe model.pkl/model_version.txt (si promu,
    identité bot, jamais de push) et republie mlflow_snapshot/."""
    _run("python ml/register_model.py --commit-artifacts")


@job
def fraud_pipeline_job():
    test_data(transform(validate(ingest())))


@job
def continuous_training_job():
    """Pipeline complet déclenché par platform_api quand le seuil de mises
    à jour en attente est atteint (voir platform_api/versioning.py, appelé
    en amont pour versionner le dataset avant ce job) : ingestion ->
    validation -> transformation -> tests -> entraînement -> dérive ->
    enregistrement/promotion."""
    after_tests = test_data(transform(validate(ingest())))
    after_training = train_model(start=after_tests)
    after_drift = check_drift(start=after_training)
    register_and_promote(start=after_drift)


# ---------------------------------------------------------------- déclencheurs


nightly_pipeline_schedule = ScheduleDefinition(
    name="nightly_pipeline_schedule",
    job=fraud_pipeline_job,
    cron_schedule="0 2 * * *",
    execution_timezone="Africa/Casablanca",
    default_status=DefaultScheduleStatus.RUNNING,
    description="Ingestion -> validation -> transformation -> tests, chaque nuit à 02:00.",
)


def _dvc_md5(pointer: Path = DVC_POINTER) -> str | None:
    match = re.search(r"^- md5: (\w+)", pointer.read_text(), re.MULTILINE) if pointer.exists() else None
    return match.group(1) if match else None


def _platform_already_processed(md5: str, runs_log: Path = RUNS_LOG) -> bool:
    """Vrai si un run de la plateforme (platform_api/jobs.py) a déjà traité
    cette version du dataset : évite de relancer en double le pipeline que la
    plateforme vient de déclencher elle-même après `dvc add`."""
    if not runs_log.exists():
        return False
    for line in runs_log.read_text().splitlines():
        if line.strip() and json.loads(line).get("dvc_md5") == md5:
            return True
    return False


@sensor(
    job=fraud_pipeline_job,
    minimum_interval_seconds=60,
    default_status=DefaultSensorStatus.RUNNING,
    description="Relance le pipeline quand data/raw/creditcard.csv.dvc change hors plateforme.",
)
def dataset_version_sensor(context: SensorEvaluationContext):
    md5 = _dvc_md5()
    if md5 is None:
        return SkipReason("Pas de pointeur DVC (data/raw/creditcard.csv.dvc).")
    if context.cursor is None:
        context.update_cursor(md5)  # premier tick : on mémorise, on ne relance pas
        return SkipReason("Version initiale du dataset mémorisée.")
    if md5 == context.cursor:
        return SkipReason("Dataset inchangé.")
    context.update_cursor(md5)
    if _platform_already_processed(md5):
        return SkipReason(f"Version {md5[:8]} déjà traitée par la plateforme.")
    return RunRequest(run_key=md5, tags={"dataset_md5": md5})


defs = Definitions(
    jobs=[fraud_pipeline_job, continuous_training_job],
    schedules=[nightly_pipeline_schedule],
    sensors=[dataset_version_sensor],
)
