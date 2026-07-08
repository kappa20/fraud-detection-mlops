"""Enregistrement du meilleur modèle dans le MLflow Model Registry
(Livrable 6) et export local pour le service FastAPI (Livrable 7, qui
chargera un .pkl plutôt que de dépendre d'un serveur MLflow vivant à
l'intérieur du conteneur Docker en production).

Usage :
    python ml/register_model.py
"""

import shutil
from pathlib import Path

import joblib
import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MLFLOW_DB = PROJECT_ROOT / "mlflow.db"
ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
MODEL_NAME = "fraud-detection-classifier"
EXPERIMENT_NAME = "fraud_detection"


def get_best_run(client: MlflowClient, experiment_name: str, metric: str = "pr_auc"):
    experiment = client.get_experiment_by_name(experiment_name)
    if experiment is None:
        raise RuntimeError(f"Experiment '{experiment_name}' introuvable. Lancer ml/train.py d'abord.")
    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        order_by=[f"metrics.{metric} DESC"],
        max_results=1,
    )
    if not runs:
        raise RuntimeError(f"Aucun run trouvé dans l'experiment '{experiment_name}'.")
    return runs[0]


def main() -> None:
    mlflow.set_tracking_uri(f"sqlite:///{MLFLOW_DB}")
    client = MlflowClient()

    best_run = get_best_run(client, EXPERIMENT_NAME)
    run_id = best_run.info.run_id
    pr_auc = best_run.data.metrics.get("pr_auc")
    print(f"Meilleur run : {run_id} (pr_auc={pr_auc:.4f})")

    model_uri = f"runs:/{run_id}/model"
    registered_model = mlflow.register_model(model_uri=model_uri, name=MODEL_NAME)
    version = registered_model.version
    print(f"Modèle enregistré : {MODEL_NAME} v{version}")

    # Staging -> Production : dans un contexte industriel réel, cette
    # transition serait précédée d'une validation humaine ou de tests
    # d'intégration supplémentaires (non simulés ici par souci de simplicité).
    client.transition_model_version_stage(
        name=MODEL_NAME, version=version, stage="Staging", archive_existing_versions=False
    )
    print(f"{MODEL_NAME} v{version} -> Staging")

    client.transition_model_version_stage(
        name=MODEL_NAME, version=version, stage="Production", archive_existing_versions=True
    )
    print(f"{MODEL_NAME} v{version} -> Production")

    # Export local pour api/model_loader.py (Livrable 7).
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    download_path = ARTIFACTS_DIR / "_download"
    if download_path.exists():
        shutil.rmtree(download_path)
    mlflow.artifacts.download_artifacts(artifact_uri=model_uri, dst_path=str(download_path))

    model = mlflow.sklearn.load_model(str(download_path / "model"))
    joblib.dump(model, ARTIFACTS_DIR / "model.pkl")
    shutil.rmtree(download_path)
    print(f"Modèle exporté : {ARTIFACTS_DIR / 'model.pkl'}")

    (ARTIFACTS_DIR / "model_version.txt").write_text(
        f"{MODEL_NAME} v{version} (run_id={run_id}, pr_auc={pr_auc:.4f}, stage=Production)\n"
    )


if __name__ == "__main__":
    main()
