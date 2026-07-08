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


@job
def fraud_pipeline_job():
    test_data(transform(validate(ingest())))
