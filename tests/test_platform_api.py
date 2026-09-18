"""Tests de la plateforme d'ingestion continue (platform_api/).

Isole le CSV et l'état (data/state/) dans un répertoire temporaire, et
mocke le versioning DVC/git (platform_api.versioning.version_dataset) :
ces tests vérifient le contrat de l'API (seuil, compteur, déclenchement),
pas l'intégration réelle avec DVC/MinIO — déjà validée manuellement (voir
data/README.md).
"""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from platform_api import dataset, pipeline, state, versioning
from platform_api.main import app

CSV_HEADER = ["Time"] + [f"V{i}" for i in range(1, 29)] + ["Amount", "Class"]


def _valid_transaction() -> dict:
    return {"time": 100.0, **{f"v{i}": 0.0 for i in range(1, 29)}, "amount": 25.0, "is_fraud": 0}


@pytest.fixture
def client(tmp_path, monkeypatch):
    csv_path = tmp_path / "creditcard.csv"
    pd.DataFrame([[0.0] + [0.0] * 28 + [10.0, 0]], columns=CSV_HEADER).to_csv(csv_path, index=False)

    monkeypatch.setattr(dataset, "RAW_CSV_PATH", csv_path)
    monkeypatch.setattr(state, "STATE_PATH", tmp_path / "pipeline_state.json")
    monkeypatch.setattr(state, "RUNS_LOG_PATH", tmp_path / "runs.jsonl")

    return TestClient(app)


def test_health():
    with TestClient(app) as c:
        assert c.get("/health").json() == {"status": "ok"}


def test_ingest_below_threshold_does_not_trigger(client, monkeypatch):
    monkeypatch.setattr(state, "load_state", lambda: {"threshold": 10, "pending_count": 0})
    resp = client.post("/data/ingest", json={"transactions": [_valid_transaction()]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["rows_ingested"] == 1
    assert body["pending_count"] == 1
    assert body["triggered"] is False


def test_ingest_reaching_threshold_triggers_versioning(client, monkeypatch):
    monkeypatch.setattr(state, "load_state", lambda: {"threshold": 2, "pending_count": 0})
    monkeypatch.setattr(
        versioning,
        "version_dataset",
        lambda msg: {"md5": "deadbeef", "commit_sha": "abc123", "timestamp": "2026-01-01T00:00:00Z"},
    )
    # Le pipeline complet (Dagster) est déclenché en tâche de fond : on le
    # mocke pour ne pas réellement lancer `dagster job execute` en test.
    pipeline_calls = []
    monkeypatch.setattr(
        pipeline, "run_continuous_training_job", lambda **kwargs: pipeline_calls.append(kwargs)
    )

    resp = client.post(
        "/data/ingest",
        json={"transactions": [_valid_transaction(), _valid_transaction()]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["triggered"] is True
    assert body["pending_count"] == 0  # reset après déclenchement
    assert len(pipeline_calls) == 1
    assert pipeline_calls[0]["dvc_md5"] == "deadbeef"

    runs = client.get("/runs").json()
    assert len(runs) == 1
    assert runs[0]["status"] == "pipeline_running"
    assert runs[0]["dvc_md5"] == "deadbeef"


def test_ingest_versioning_failure_is_recorded_but_not_fatal(client, monkeypatch):
    monkeypatch.setattr(state, "load_state", lambda: {"threshold": 1, "pending_count": 0})

    def _boom(msg):
        raise versioning.VersioningError("dvc push a échoué (test)")

    monkeypatch.setattr(versioning, "version_dataset", _boom)

    resp = client.post("/data/ingest", json={"transactions": [_valid_transaction()]})
    assert resp.status_code == 200
    assert resp.json()["triggered"] is False  # échec du versioning : pas "réussi"

    runs = client.get("/runs").json()
    assert runs[0]["status"] == "failed"


def test_threshold_get_and_put(client):
    resp = client.put("/config/threshold", json={"threshold": 250})
    assert resp.status_code == 200
    assert resp.json()["threshold"] == 250

    resp = client.get("/config/threshold")
    assert resp.json()["threshold"] == 250


def test_ingest_rejects_invalid_transaction(client):
    payload = _valid_transaction()
    payload["is_fraud"] = 2  # hors domaine {0, 1}
    resp = client.post("/data/ingest", json={"transactions": [payload]})
    assert resp.status_code == 422


def test_simulate_generates_requested_row_count(client, monkeypatch):
    monkeypatch.setattr(state, "load_state", lambda: {"threshold": 10_000, "pending_count": 0})
    resp = client.post("/data/simulate", json={"n": 5, "drift_intensity": "strong"})
    assert resp.status_code == 200
    assert resp.json()["rows_ingested"] == 5
    assert dataset.row_count() == 6  # 1 ligne de référence + 5 générées


def test_run_continuous_training_job_records_completion(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "STATE_PATH", tmp_path / "pipeline_state.json")
    monkeypatch.setattr(state, "RUNS_LOG_PATH", tmp_path / "runs.jsonl")

    class _FakeCompletedProcess:
        returncode = 0
        stderr = ""

    monkeypatch.setattr("subprocess.run", lambda *a, **k: _FakeCompletedProcess())

    pipeline.run_continuous_training_job(trigger="ingest", rows_added=42, dvc_md5="abc", commit_sha="def")

    runs = state.load_runs()
    assert len(runs) == 1
    assert runs[0]["status"] == "completed"
    assert runs[0]["rows_added"] == 42


def test_run_continuous_training_job_records_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "STATE_PATH", tmp_path / "pipeline_state.json")
    monkeypatch.setattr(state, "RUNS_LOG_PATH", tmp_path / "runs.jsonl")

    class _FakeFailedProcess:
        returncode = 1
        stderr = "dbt test failed"

    monkeypatch.setattr("subprocess.run", lambda *a, **k: _FakeFailedProcess())

    pipeline.run_continuous_training_job(trigger="simulate", rows_added=10, dvc_md5=None, commit_sha=None)

    runs = state.load_runs()
    assert runs[0]["status"] == "failed"
    assert "dbt test failed" in runs[0]["note"]
