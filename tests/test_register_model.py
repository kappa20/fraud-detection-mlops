"""Tests de la porte de promotion (ml/register_model.py — plateforme
d'entraînement continu). Utilise un tracking MLflow isolé (sqlite +
artifact store dans tmp_path), jamais le mlflow.db réel du projet, et un
estimateur scikit-learn minimal (pas le vrai pipeline d'entraînement,
déjà couvert manuellement — voir docs/ml/experiments_summary.md).
"""

import json

import mlflow
import mlflow.sklearn
import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

import ml.register_model as register_model

MODEL_NAME = register_model.MODEL_NAME


@pytest.fixture(autouse=True)
def isolated_mlflow(tmp_path, monkeypatch):
    monkeypatch.delenv(register_model.TRACKING_URI_ENV, raising=False)  # jamais le vrai serveur MLflow
    monkeypatch.setattr(register_model, "MLFLOW_DB", tmp_path / "mlflow.db")
    monkeypatch.setattr(register_model, "ARTIFACTS_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(register_model, "LATEST_RUN_MARKER", tmp_path / "artifacts" / "latest_training_run.json")
    monkeypatch.setattr(register_model, "MLFLOW_SNAPSHOT_DIR", tmp_path / "mlflow_snapshot")
    monkeypatch.setattr(register_model, "MLRUNS_DIR", tmp_path / "mlruns")

    mlflow.set_tracking_uri(f"sqlite:///{tmp_path / 'mlflow.db'}")
    mlflow.create_experiment(register_model.EXPERIMENT_NAME, artifact_location=str(tmp_path / "mlruns"))
    mlflow.set_experiment(register_model.EXPERIMENT_NAME)
    yield
    mlflow.set_experiment("Default")


def _log_candidate_run(pr_auc: float) -> str:
    X = np.array([[0.0], [1.0], [2.0], [3.0]])
    y = np.array([0, 0, 1, 1])
    model = LogisticRegression().fit(X, y)
    with mlflow.start_run() as run:
        mlflow.log_metric("pr_auc", pr_auc)
        mlflow.sklearn.log_model(model, artifact_path="model")
        run_id = run.info.run_id
    register_model.LATEST_RUN_MARKER.parent.mkdir(parents=True, exist_ok=True)
    register_model.LATEST_RUN_MARKER.write_text(json.dumps({"run_id": run_id, "pr_auc": pr_auc}))
    return run_id


def test_first_candidate_is_promoted_when_no_production_exists():
    _log_candidate_run(pr_auc=0.5)
    result = register_model.main(commit_artifacts_flag=False)
    assert result["promoted"] is True
    assert result["previous_production_pr_auc"] is None


def test_worse_candidate_is_not_promoted():
    _log_candidate_run(pr_auc=0.7)
    register_model.main(commit_artifacts_flag=False)

    _log_candidate_run(pr_auc=0.4)
    result = register_model.main(commit_artifacts_flag=False)

    assert result["promoted"] is False
    assert result["previous_production_pr_auc"] == 0.7


def test_better_candidate_is_promoted_and_exported():
    _log_candidate_run(pr_auc=0.5)
    register_model.main(commit_artifacts_flag=False)

    _log_candidate_run(pr_auc=0.9)
    result = register_model.main(commit_artifacts_flag=False)

    assert result["promoted"] is True
    assert result["previous_production_pr_auc"] == 0.5
    assert (register_model.ARTIFACTS_DIR / "model.pkl").exists()
    version_text = (register_model.ARTIFACTS_DIR / "model_version.txt").read_text()
    assert "Production" in version_text


def test_tracking_uri_defaults_to_local_sqlite_and_honours_env(monkeypatch, tmp_path):
    assert register_model.tracking_uri() == f"sqlite:///{tmp_path / 'mlflow.db'}"
    assert register_model.is_remote_tracking() is False

    monkeypatch.setenv(register_model.TRACKING_URI_ENV, "http://mlflow:5000")
    assert register_model.tracking_uri() == "http://mlflow:5000"
    assert register_model.is_remote_tracking() is True


def test_snapshot_is_skipped_with_a_live_mlflow_server(monkeypatch, tmp_path):
    monkeypatch.setenv(register_model.TRACKING_URI_ENV, "http://mlflow:5000")
    register_model.publish_mlflow_snapshot()
    assert not (tmp_path / "mlflow_snapshot").exists()
