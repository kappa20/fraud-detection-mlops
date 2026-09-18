"""Déclenchement du job Dagster complet (ingestion -> validation ->
transformation -> tests -> entraînement -> dérive -> registry/promotion,
voir orchestration_dagster/fraud_dagster/job.py::continuous_training_job)
une fois que platform_api/versioning.py a versionné le dataset.

Exécuté via FastAPI BackgroundTasks (voir main.py) plutôt qu'en bloquant
la requête HTTP : un ré-entraînement peut prendre plusieurs dizaines de
secondes (RandomForestClassifier sur ~285k lignes), et la banque/le
bouton de simulation ne doivent pas attendre cette durée pour recevoir
une réponse à leur appel d'ingestion.
"""

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from platform_api import state

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DAGSTER_CMD = [
    "dagster",
    "job",
    "execute",
    "-f",
    "orchestration_dagster/fraud_dagster/job.py",
    "-a",
    "continuous_training_job",
]


def run_continuous_training_job(trigger: str, rows_added: int, dvc_md5: str | None, commit_sha: str | None) -> None:
    """Fonction de fond (background task) : exécute le job Dagster complet
    et journalise le résultat dans data/state/runs.jsonl, en complément de
    l'entrée "versioned" déjà écrite au moment du déclenchement."""
    result = subprocess.run(DAGSTER_CMD, cwd=PROJECT_ROOT, capture_output=True, text=True)

    status = "completed" if result.returncode == 0 else "failed"
    note = (
        "Pipeline complet exécuté (ingestion, transformation, tests, entraînement, dérive, registry)."
        if result.returncode == 0
        else f"Le job Dagster a échoué : {result.stderr[-2000:]}"
    )

    state.append_run(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trigger": trigger,
            "rows_added": rows_added,
            "dvc_md5": dvc_md5,
            "commit_sha": commit_sha,
            "status": status,
            "note": note,
        }
    )
