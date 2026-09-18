"""Orchestration Dagster du pipeline DataOps (ingestion -> validation ->
transformation -> tests), pattern @op/@job identique à celui déjà validé
par le professeur dans le TP Chapitre 2
(td/tp_chapitre_2/tp_chapitre2_pipeline/pipeline/orchestrate.py), avec deux
améliorations : vérification explicite du code de retour de chaque étape
(fail-fast, absent du TP) et dépendances typées `Nothing` (idiome Dagster
documenté pour enchaîner des étapes sans transfert de données).

Usage :
    cd projet
    dagster job execute -f orchestration_dagster/fraud_dagster/job.py -a fraud_pipeline_job
    # ou, pour l'UI web :
    dagster dev -f orchestration_dagster/fraud_dagster/job.py
"""

import subprocess
from pathlib import Path

from dagster import In, Nothing, job, op

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _run(cmd: str) -> None:
    """Exécute une commande shell depuis la racine du projet et échoue
    explicitement (fail-fast) si le code de retour est non nul."""
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
