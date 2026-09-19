"""Enregistrement du meilleur modèle dans le MLflow Model Registry
(Livrable 6) et export local pour le service FastAPI (Livrable 7, qui
chargera un .pkl plutôt que de dépendre d'un serveur MLflow vivant à
l'intérieur du conteneur Docker en production).

Porte de promotion (ajoutée pour la plateforme d'entraînement continu) :
le nouveau candidat n'est promu en Production que s'il fait mieux (PR-AUC)
que le modèle actuellement en Production — sinon il reste enregistré (visible
dans le registry, comparable) mais en Staging, et le service de scoring
continue de servir l'ancien modèle. Sans cette porte, un ré-entraînement
sur des données bruitées/dérivées pourrait dégrader silencieusement le
modèle en production à chaque déclenchement automatique.

Usage :
    python ml/register_model.py                     # usage manuel (comme avant)
    python ml/register_model.py --commit-artifacts   # usage automatisé (plateforme
                                                       # d'entraînement continu) : si promu,
                                                       # committe model.pkl/model_version.txt
                                                       # (identité bot, jamais de push) et
                                                       # republie l'instantané MLflow servi
                                                       # par Komodo (mlflow_snapshot/).
"""

import argparse
import json
import os
import shutil
from pathlib import Path

import joblib
import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MLFLOW_DB = PROJECT_ROOT / "mlflow.db"
MLRUNS_DIR = PROJECT_ROOT / "mlruns"
MLFLOW_SNAPSHOT_DIR = PROJECT_ROOT / "mlflow_snapshot"
ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
LATEST_RUN_MARKER = ARTIFACTS_DIR / "latest_training_run.json"
MODEL_NAME = "fraud-detection-classifier"
EXPERIMENT_NAME = "fraud_detection"

BOT_NAME = "Fraud Pipeline Bot"
BOT_EMAIL = "pipeline@fraud-detection-mlops.local"


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


def get_candidate_run(client: MlflowClient):
    """Sélectionne le run à évaluer pour promotion : le run que ml/train.py
    vient de produire (marqueur JSON) s'il existe, sinon le meilleur run de
    tout l'historique de l'experiment (comportement historique, usage manuel)."""
    if LATEST_RUN_MARKER.exists():
        marker = json.loads(LATEST_RUN_MARKER.read_text())
        run = client.get_run(marker["run_id"])
        return run
    return get_best_run(client, EXPERIMENT_NAME)


def get_current_production_pr_auc(client: MlflowClient) -> float | None:
    try:
        versions = client.get_latest_versions(MODEL_NAME, stages=["Production"])
    except mlflow.exceptions.MlflowException:
        return None  # modèle pas encore enregistré (tout premier run)
    if not versions:
        return None
    run = client.get_run(versions[0].run_id)
    return run.data.metrics.get("pr_auc")


def _run_git(cmd: list[str]) -> str:
    import os
    import subprocess

    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": BOT_NAME,
        "GIT_AUTHOR_EMAIL": BOT_EMAIL,
        "GIT_COMMITTER_NAME": BOT_NAME,
        "GIT_COMMITTER_EMAIL": BOT_EMAIL,
    }
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"Commande échouée ({' '.join(cmd)}) : {result.stderr.strip()}")
    return result.stdout.strip()


def publish_mlflow_snapshot() -> None:
    """Republie mlflow.db/mlruns vers mlflow_snapshot/, servi en lecture
    seule par le conteneur mlflow de docker-compose.yml sur Komodo — sans
    cette étape, le MLflow déployé resterait figé sur l'instantané pris
    manuellement au moment du déploiement initial, et les ré-entraînements
    de la plateforme n'y apparaîtraient jamais."""
    MLFLOW_SNAPSHOT_DIR.mkdir(exist_ok=True)
    shutil.copy2(MLFLOW_DB, MLFLOW_SNAPSHOT_DIR / "mlflow.db")
    snapshot_mlruns = MLFLOW_SNAPSHOT_DIR / "mlruns"
    if snapshot_mlruns.exists():
        shutil.rmtree(snapshot_mlruns)
    shutil.copytree(MLRUNS_DIR, snapshot_mlruns)


def commit_artifacts(version: int, promoted: bool) -> str:
    _run_git(["git", "add", "ml/artifacts/model.pkl", "ml/artifacts/model_version.txt"])
    message = f"model: {MODEL_NAME} v{version} — {'promu en Production' if promoted else 'enregistré (non promu)'}"
    _run_git(["git", "commit", "-m", message])
    return _run_git(["git", "rev-parse", "HEAD"])


def promote_version(client: MlflowClient, version: int | str, commit_artifacts_flag: bool = False) -> dict:
    """Passe la version `version` en Production (archive l'ancienne), exporte
    model.pkl/model_version.txt pour le service de scoring et, si demandé,
    committe ces artefacts et republie l'instantané MLflow. Utilisé par la
    porte de promotion automatique (`main`) et par l'approbation manuelle
    depuis le tableau de bord (platform_api/models.py)."""
    model_version = client.get_model_version(MODEL_NAME, str(version))
    run_id = model_version.run_id
    pr_auc = client.get_run(run_id).data.metrics.get("pr_auc")

    client.transition_model_version_stage(
        name=MODEL_NAME, version=str(version), stage="Production", archive_existing_versions=True
    )
    print(f"{MODEL_NAME} v{version} -> Production")

    # Export local pour api/model_loader.py (Livrable 7).
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    download_path = ARTIFACTS_DIR / "_download"
    if download_path.exists():
        shutil.rmtree(download_path)
    model_uri = f"runs:/{run_id}/model"
    mlflow.artifacts.download_artifacts(artifact_uri=model_uri, dst_path=str(download_path))

    model = mlflow.sklearn.load_model(str(download_path / "model"))
    joblib.dump(model, ARTIFACTS_DIR / "model.pkl")
    shutil.rmtree(download_path)
    print(f"Modèle exporté : {ARTIFACTS_DIR / 'model.pkl'}")

    pr_auc_text = f"{pr_auc:.4f}" if pr_auc is not None else "n/a"
    (ARTIFACTS_DIR / "model_version.txt").write_text(
        f"{MODEL_NAME} v{version} (run_id={run_id}, pr_auc={pr_auc_text}, stage=Production)\n"
    )

    commit_sha = None
    if commit_artifacts_flag:
        commit_sha = commit_artifacts(int(version), promoted=True)
        publish_mlflow_snapshot()
    return {"version": int(version), "run_id": run_id, "pr_auc": pr_auc, "commit_sha": commit_sha}


def main(commit_artifacts_flag: bool = False, no_promote: bool = False) -> dict:
    mlflow.set_tracking_uri(f"sqlite:///{MLFLOW_DB}")
    client = MlflowClient()

    candidate = get_candidate_run(client)
    run_id = candidate.info.run_id
    pr_auc = candidate.data.metrics.get("pr_auc")
    print(f"Candidat : {run_id} (pr_auc={pr_auc:.4f})")

    current_production_pr_auc = get_current_production_pr_auc(client)
    promote = current_production_pr_auc is None or pr_auc > current_production_pr_auc
    if current_production_pr_auc is None:
        print("Aucun modèle en Production actuellement -> promotion automatique du premier candidat.")
    else:
        verdict = "meilleur" if promote else "pas meilleur"
        print(f"Production actuelle : pr_auc={current_production_pr_auc:.4f} — candidat {verdict}.")

    model_uri = f"runs:/{run_id}/model"
    registered_model = mlflow.register_model(model_uri=model_uri, name=MODEL_NAME)
    version = registered_model.version
    print(f"Modèle enregistré : {MODEL_NAME} v{version}")

    client.transition_model_version_stage(
        name=MODEL_NAME, version=version, stage="Staging", archive_existing_versions=False
    )
    print(f"{MODEL_NAME} v{version} -> Staging")

    result = {
        "version": version,
        "run_id": run_id,
        "pr_auc": pr_auc,
        "previous_production_pr_auc": current_production_pr_auc,
        "promoted": False,
        "commit_sha": None,
    }

    if no_promote:
        print(f"{MODEL_NAME} v{version} reste en Staging (promotion manuelle : approbation requise).")
        if commit_artifacts_flag:
            publish_mlflow_snapshot()
        return result

    if not promote:
        print(f"{MODEL_NAME} v{version} reste en Staging (porte de promotion non franchie).")
        if commit_artifacts_flag:
            publish_mlflow_snapshot()
        return result

    promoted = promote_version(client, version, commit_artifacts_flag)
    result["promoted"] = True
    result["commit_sha"] = promoted["commit_sha"]
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--commit-artifacts",
        action="store_true",
        help="Committer model.pkl/model_version.txt (si promu) et republier mlflow_snapshot/ — "
        "réservé à l'usage automatisé par la plateforme d'entraînement continu.",
    )
    parser.add_argument(
        "--no-promote",
        action="store_true",
        default=os.environ.get("FRAUD_REGISTER_NO_PROMOTE") == "1",
        help="Enregistrer le candidat en Staging sans le promouvoir : la promotion est décidée par un "
        "humain dans le tableau de bord (équivalent : variable FRAUD_REGISTER_NO_PROMOTE=1, posée par "
        "la plateforme quand la promotion automatique est désactivée).",
    )
    args = parser.parse_args()
    main(commit_artifacts_flag=args.commit_artifacts, no_promote=args.no_promote)
