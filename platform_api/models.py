"""Candidat de ré-entraînement, comparaison avec la Production, approbation
ou rejet — la décision humaine derrière la promotion (voir le réglage
`auto_promote` dans state.py).

Sans état propre : le candidat est simplement la dernière version du modèle
au stade Staging dans le MLflow Model Registry (celle que
ml/register_model.py --no-promote laisse en attente, ou qu'une porte de
promotion automatique a refusée).
"""

import mlflow
from mlflow.tracking import MlflowClient

from ml import register_model
from platform_api import deploy

METRIC_KEYS = ("pr_auc", "roc_auc", "f1", "precision", "recall")


class NoCandidateError(RuntimeError):
    """Aucune version en attente dans le registry."""


def _client() -> MlflowClient:
    mlflow.set_tracking_uri(f"sqlite:///{register_model.MLFLOW_DB}")
    return MlflowClient()


def _describe(client: MlflowClient, model_version) -> dict:
    run = client.get_run(model_version.run_id)
    return {
        "version": int(model_version.version),
        "stage": model_version.current_stage,
        "run_id": model_version.run_id,
        "created_at": model_version.creation_timestamp,
        "metrics": {key: run.data.metrics.get(key) for key in METRIC_KEYS},
    }


def _latest(client: MlflowClient, stage: str):
    versions = client.get_latest_versions(register_model.MODEL_NAME, stages=[stage])
    return versions[0] if versions else None


def comparison() -> dict:
    """{"candidate": {...}|None, "production": {...}|None, "delta": {...}}."""
    client = _client()
    candidate_version = _latest(client, "Staging")
    production_version = _latest(client, "Production")
    candidate = _describe(client, candidate_version) if candidate_version else None
    production = _describe(client, production_version) if production_version else None

    delta = {}
    if candidate and production:
        for key in METRIC_KEYS:
            new, old = candidate["metrics"].get(key), production["metrics"].get(key)
            delta[key] = None if new is None or old is None else new - old
    return {"candidate": candidate, "production": production, "delta": delta}


def approve(version: int) -> dict:
    """Promeut `version` en Production, exporte le modèle pour fraud-api, puis
    demande son redémarrage. Refuse une version qui n'est pas en Staging."""
    client = _client()
    model_version = client.get_model_version(register_model.MODEL_NAME, str(version))
    if model_version.current_stage != "Staging":
        raise NoCandidateError(f"La version {version} n'est pas en attente (stade {model_version.current_stage}).")
    promoted = register_model.promote_version(client, version, commit_artifacts_flag=True)
    return {**promoted, "redeploy": deploy.restart_api()}


def reject(version: int) -> dict:
    client = _client()
    model_version = client.get_model_version(register_model.MODEL_NAME, str(version))
    if model_version.current_stage != "Staging":
        raise NoCandidateError(f"La version {version} n'est pas en attente (stade {model_version.current_stage}).")
    client.transition_model_version_stage(
        name=register_model.MODEL_NAME, version=str(version), stage="Archived", archive_existing_versions=False
    )
    return {"version": int(version), "stage": "Archived"}
