"""Entraînement et tracking MLflow des modèles de détection de fraude
(Livrable 5 — Machine Learning / Livrable 6 — MLflow).

Deux modèles scikit-learn comparés :
- Baseline : LogisticRegression(class_weight="balanced")
- Modèle principal : RandomForestClassifier(class_weight="balanced_subsample")

Chaque run MLflow est tagué pour la traçabilité — mapping direct sur les
"5 Q" du Chapitre 1 (quelle donnée / quelle version / quel modèle / quel
responsable / quelle validation) :
    data_version, code_version, trained_by, dbt_test_status.

Usage :
    python ml/train.py
    mlflow ui --backend-store-uri sqlite:///mlflow.db   # pour consulter les runs

Avec la variable MLFLOW_TRACKING_URI (ex. http://mlflow:5000 dans la stack
docker-compose), les runs sont écrits sur le serveur MLflow vivant
(PostgreSQL + artefacts MinIO) au lieu de ./mlflow.db.
"""

import json
import os
import subprocess
from pathlib import Path

import mlflow
import mlflow.sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from evaluate import best_threshold_by_f1, compute_metrics, plot_confusion_matrix, plot_precision_recall_curve
from prepare_data import get_train_test_data

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MLFLOW_DB = PROJECT_ROOT / "mlflow.db"
ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
DBT_RUN_RESULTS = PROJECT_ROOT / "dbt_fraud" / "target" / "run_results.json"
LATEST_RUN_MARKER = ARTIFACTS_DIR / "latest_training_run.json"

EXPERIMENT_NAME = "fraud_detection"
TRAINED_BY = "ML Engineer 1"


def _git_commit() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT_ROOT)
            .decode()
            .strip()
        )
    except Exception:
        return "unknown"


def _dbt_test_status() -> str:
    if not DBT_RUN_RESULTS.exists():
        return "unknown (executer dbt build avant l'entrainement)"
    data = json.loads(DBT_RUN_RESULTS.read_text())
    results = [r for r in data.get("results", []) if "test" in r.get("unique_id", "")]
    if not results:
        return "unknown"
    passed = sum(1 for r in results if r.get("status") == "pass")
    return f"{passed}/{len(results)} PASS"


def train_and_log(name, estimator, params, X_train, X_test, y_train, y_test, tags):
    with mlflow.start_run(run_name=name):
        pipeline = Pipeline([("scaler", StandardScaler()), ("clf", estimator)])
        pipeline.fit(X_train, y_train)

        y_proba = pipeline.predict_proba(X_test)[:, 1]
        threshold = best_threshold_by_f1(y_test, y_proba)
        metrics = compute_metrics(y_test, y_proba, threshold=threshold)

        mlflow.log_params(params)
        mlflow.log_param("n_train", len(X_train))
        mlflow.log_param("n_test", len(X_test))
        mlflow.log_metrics(
            {k: v for k, v in metrics.items() if isinstance(v, (int, float))}
        )

        ARTIFACTS_DIR.mkdir(exist_ok=True)
        cm_path = ARTIFACTS_DIR / f"confusion_matrix_{name}.png"
        pr_path = ARTIFACTS_DIR / f"pr_curve_{name}.png"
        plot_confusion_matrix(y_test, y_proba, threshold, cm_path)
        plot_precision_recall_curve(y_test, y_proba, pr_path)
        mlflow.log_artifact(str(cm_path))
        mlflow.log_artifact(str(pr_path))

        mlflow.set_tags(tags)
        mlflow.sklearn.log_model(
            pipeline,
            artifact_path="model",
            input_example=X_train.head(3),
        )

        run_id = mlflow.active_run().info.run_id
        print(
            f"[{name}] run_id={run_id} "
            f"pr_auc={metrics['pr_auc']:.4f} recall={metrics['recall']:.4f} "
            f"precision={metrics['precision']:.4f} f1={metrics['f1']:.4f}"
        )
        return run_id, metrics


def main() -> None:
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI") or f"sqlite:///{MLFLOW_DB}")
    mlflow.set_experiment(EXPERIMENT_NAME)

    X_train, X_test, y_train, y_test = get_train_test_data()

    tags = {
        "data_version": f"{len(X_train) + len(X_test)}_rows",
        "code_version": _git_commit(),
        "trained_by": TRAINED_BY,
        "dbt_test_status": _dbt_test_status(),
    }

    results = {}

    results["logreg_baseline"] = train_and_log(
        "logreg_baseline",
        LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42),
        {
            "model_type": "LogisticRegression",
            "class_weight": "balanced",
            "max_iter": 1000,
            "random_state": 42,
        },
        X_train, X_test, y_train, y_test, tags,
    )

    results["rf_balanced_v1"] = train_and_log(
        "rf_balanced_v1",
        RandomForestClassifier(
            n_estimators=200,
            max_depth=12,
            class_weight="balanced_subsample",
            random_state=42,
            n_jobs=-1,
        ),
        {
            "model_type": "RandomForestClassifier",
            "n_estimators": 200,
            "max_depth": 12,
            "class_weight": "balanced_subsample",
            "random_state": 42,
        },
        X_train, X_test, y_train, y_test, tags,
    )

    best_name = max(results, key=lambda k: results[k][1]["pr_auc"])
    best_run_id, best_metrics = results[best_name]
    print(f"\nMeilleur modèle (PR-AUC) : {best_name} -> run_id={best_run_id}")

    # Marqueur du run "juste entraîné" (par opposition au meilleur run de
    # tout l'historique de l'experiment) : consommé par ml/register_model.py
    # pour que la porte de promotion compare le nouveau candidat au modèle
    # actuellement en Production, plutôt que de re-sélectionner un vieux run.
    LATEST_RUN_MARKER.write_text(
        json.dumps({"run_id": best_run_id, "model_name": best_name, "pr_auc": best_metrics["pr_auc"]}, indent=2)
    )


if __name__ == "__main__":
    main()
