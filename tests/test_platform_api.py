"""Tests de la plateforme d'opérations (platform_api/).

Isole le CSV et l'état (data/state/) dans un répertoire temporaire, et
mocke le versioning DVC/git, les sous-processus (Dagster) et MLflow : ces
tests vérifient le contrat de l'API (auth, pagination, corrections,
déclenchement, dérive), pas l'intégration réelle avec DVC/MinIO/Dagster —
déjà validée manuellement (voir data/README.md).
"""

import pytest
from fastapi.testclient import TestClient

from platform_api import auth, dataset, deploy, drift, jobs, main, models, services, state, transactions, versioning
from platform_api.main import app

CSV_HEADER = ["Time"] + [f"V{i}" for i in range(1, 29)] + ["Amount", "Class"]


def _valid_transaction(**overrides) -> dict:
    return {"time": 100.0, **{f"v{i}": 0.0 for i in range(1, 29)}, "amount": 25.0, "is_fraud": 0, **overrides}


def _write_csv(path, rows: int = 1) -> None:
    """CSV au format Kaggle : en-tête entre guillemets, `Class` entre guillemets
    sur les lignes d'origine — comme data/raw/creditcard.csv."""
    lines = [",".join(f'"{c}"' for c in CSV_HEADER)]
    for i in range(rows):
        values = [str(i * 100.0)] + ["0.5"] * 28 + [str(float(i)), f'"{1 if i % 10 == 0 and i else 0}"']
        lines.append(",".join(values))
    path.write_text("\n".join(lines) + "\n")


def _fake_version(monkeypatch, sha="abc123"):
    calls = []

    def _fake(message):
        calls.append(message)
        return {"md5": "deadbeef", "commit_sha": sha, "timestamp": "2026-01-01T00:00:00+00:00"}

    monkeypatch.setattr(versioning, "version_dataset", _fake)
    return calls


@pytest.fixture
def client(tmp_path, monkeypatch):
    csv_path = tmp_path / "creditcard.csv"
    _write_csv(csv_path, rows=40)

    monkeypatch.setattr(dataset, "RAW_CSV_PATH", csv_path)
    monkeypatch.setattr(dataset, "_row_count_cache", ("", 0))
    monkeypatch.setattr(state, "STATE_PATH", tmp_path / "pipeline_state.json")
    monkeypatch.setattr(state, "RUNS_LOG_PATH", tmp_path / "runs.jsonl")
    monkeypatch.setattr(state, "VERSIONS_LOG_PATH", tmp_path / "versions.jsonl")
    monkeypatch.setattr(state, "DRIFT_HISTORY_PATH", tmp_path / "drift_history.jsonl")
    monkeypatch.setattr(transactions, "DUCKDB_PATH", tmp_path / "absent.duckdb")
    monkeypatch.setattr(transactions, "_cache", {"fingerprint": None, "con": None})
    monkeypatch.setattr(drift, "_cache", {"fingerprint": None, "result": None})
    monkeypatch.setattr(jobs, "_jobs", {})
    monkeypatch.setattr(jobs, "_running_id", None)
    monkeypatch.setenv("PLATFORM_USERS", "analyste:secret")
    monkeypatch.setenv("PLATFORM_SECRET", "test-secret")

    c = TestClient(app)
    c.headers["Authorization"] = f"Bearer {auth.create_token('analyste')}"
    return c


# ---------------------------------------------------------------- public / auth


def test_health_is_public():
    with TestClient(app) as c:
        assert c.get("/health").json() == {"status": "ok"}


def test_dashboard_fallback_page_when_ui_not_built(monkeypatch, tmp_path):
    monkeypatch.setenv(main.UI_DIST_ENV, str(tmp_path / "missing"))
    with TestClient(app) as c:
        resp = c.get("/")
        assert resp.status_code == 200
        assert "Plateforme d'entraînement continu" in resp.text


def test_built_ui_served_with_assets_and_no_path_traversal(monkeypatch, tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>SPA</html>")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "secret.txt").write_text("nope")
    monkeypatch.setenv(main.UI_DIST_ENV, str(tmp_path))
    with TestClient(app) as c:
        assert "SPA" in c.get("/").text
        assert c.get("/assets/app.js").status_code == 200
        assert c.get("/assets/../secret.txt").status_code == 404
        assert c.get("/assets/%2e%2e/secret.txt").status_code == 404


def test_protected_routes_require_a_token(client):
    anonymous = TestClient(app)
    for method, path in [("get", "/status"), ("get", "/transactions"), ("get", "/versions"), ("post", "/pipeline/run")]:
        assert getattr(anonymous, method)(path).status_code == 401
    assert anonymous.get("/status", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_login_success_and_failure(client):
    anonymous = TestClient(app)
    assert anonymous.post("/auth/login", json={"username": "analyste", "password": "wrong"}).status_code == 401
    assert anonymous.post("/auth/login", json={"username": "inconnu", "password": "secret"}).status_code == 401

    resp = anonymous.post("/auth/login", json={"username": "analyste", "password": "secret"})
    assert resp.status_code == 200
    token = resp.json()["token"]
    assert anonymous.get("/status", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_token_expiry_and_tampering():
    token = auth.create_token("analyste", now=1_000)
    assert auth.decode_token(token, now=1_000 + 60) == "analyste"
    assert auth.decode_token(token, now=1_000 + auth.TOKEN_TTL_SECONDS + 1) is None
    payload, _, signature = token.partition(".")
    assert auth.decode_token(payload + "." + signature[:-2] + "xx") is None
    assert auth.decode_token("nodot") is None


# ---------------------------------------------------------------- ingestion / déclencheur


def test_ingest_below_threshold_does_not_trigger(client, monkeypatch):
    state.save_state({**state.DEFAULT_STATE, "threshold": 10})
    resp = client.post("/data/ingest", json={"transactions": [_valid_transaction()]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["rows_ingested"] == 1
    assert body["pending_count"] == 1
    assert body["triggered"] is False


def test_ingest_reaching_threshold_triggers_versioning_and_job(client, monkeypatch):
    state.save_state({**state.DEFAULT_STATE, "threshold": 2})
    _fake_version(monkeypatch)
    executed = []
    monkeypatch.setattr(jobs, "execute", lambda job: executed.append(job))

    resp = client.post("/data/ingest", json={"transactions": [_valid_transaction(), _valid_transaction()]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["triggered"] is True
    assert body["pending_count"] == 0  # reset après déclenchement
    assert len(executed) == 1
    assert executed[0].dvc_md5 == "deadbeef"
    assert executed[0].user == "analyste"

    runs = client.get("/runs").json()
    assert len(runs) == 1
    assert runs[0]["status"] == "running"
    assert runs[0]["commit_sha"] == "abc123"
    assert [s["name"] for s in runs[0]["stages"]][:2] == ["Ingestion", "Validation"]


def test_ingest_versioning_failure_is_recorded_but_not_fatal(client, monkeypatch):
    state.save_state({**state.DEFAULT_STATE, "threshold": 1})

    def _boom(msg):
        raise versioning.VersioningError("dvc push a échoué (test)")

    monkeypatch.setattr(versioning, "version_dataset", _boom)

    resp = client.post("/data/ingest", json={"transactions": [_valid_transaction()]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["triggered"] is False
    # Le compteur ne doit pas être remis à zéro sur échec : le prochain ingest doit retenter.
    assert body["pending_count"] == 1
    assert client.get("/runs").json()[0]["status"] == "failed"


def test_threshold_get_and_put(client):
    assert client.put("/config/threshold", json={"threshold": 250}).json()["threshold"] == 250
    assert client.get("/config/threshold").json()["threshold"] == 250


def test_config_defaults_and_update(client):
    config = client.get("/config").json()
    assert config["auto_promote"] is False and config["auto_retrain_enabled"] is False
    assert config["psi_threshold"] == 0.25

    updated = client.put("/config", json={"auto_retrain_enabled": True, "psi_threshold": 0.3}).json()
    assert updated["auto_retrain_enabled"] is True and updated["psi_threshold"] == 0.3
    assert updated["threshold"] == config["threshold"]  # champ non fourni : inchangé


def test_ingest_rejects_invalid_transaction(client):
    payload = _valid_transaction(is_fraud=2)  # hors domaine {0, 1}
    assert client.post("/data/ingest", json={"transactions": [payload]}).status_code == 422


def test_simulate_generates_requested_row_count_after_baseline_time(client, monkeypatch):
    state.save_state({**state.DEFAULT_STATE, "threshold": 10_000})
    resp = client.post("/data/simulate", json={"n": 5, "drift_intensity": "strong"})
    assert resp.status_code == 200
    assert resp.json()["rows_ingested"] == 5
    assert dataset.row_count() == 45  # 40 lignes de référence + 5 générées
    newest = client.get("/transactions?sort=time&order=desc&page_size=5").json()["items"]
    # Les lignes simulées doivent être postérieures à la fin du dataset d'origine
    # (sinon elles tombent dans la fenêtre "référence" du calcul de dérive).
    assert all(row["time"] > dataset.BASELINE_MAX_TIME for row in newest)


def test_auto_retrain_launches_job_when_psi_exceeds_threshold(client, monkeypatch):
    state.save_state({**state.DEFAULT_STATE, "threshold": 10_000, "auto_retrain_enabled": True, "psi_threshold": 0.01})
    _fake_version(monkeypatch)
    executed = []
    monkeypatch.setattr(jobs, "execute", lambda job: executed.append(job))
    monkeypatch.setattr(main.drift, "should_auto_retrain", lambda summary: True)

    body = client.post("/data/simulate", json={"n": 3, "drift_intensity": "strong"}).json()
    assert body["triggered"] is True
    assert executed[0].trigger == "drift_auto"


# ---------------------------------------------------------------- transactions (lecture)


def test_transactions_pagination_sort_and_totals(client):
    page = client.get("/transactions?page=2&page_size=15&sort=amount&order=desc").json()
    assert page["total"] == 40
    assert page["page"] == 2 and len(page["items"]) == 15
    amounts = [row["amount"] for row in page["items"]]
    assert amounts == sorted(amounts, reverse=True)
    assert amounts[0] == 24.0  # 40 lignes, montants 0..39 : page 2 de 15 en tri décroissant = 24..10
    assert page["base_version"] == "0"


def test_transactions_filters(client):
    fraud = client.get("/transactions?is_fraud=1&page_size=100").json()
    assert fraud["total"] == 3 and all(row["is_fraud"] == 1 for row in fraud["items"])

    ranged = client.get("/transactions?amount_min=10&amount_max=12&page_size=100").json()
    assert sorted(row["amount"] for row in ranged["items"]) == [10.0, 11.0, 12.0]

    windowed = client.get("/transactions?time_min=500&time_max=800&page_size=100").json()
    assert windowed["total"] == 4


def test_transactions_sort_column_is_whitelisted(client):
    resp = client.get("/transactions?sort=amount;DROP TABLE tx")
    assert resp.status_code == 422
    assert client.get("/transactions?page_size=1000").status_code == 422  # au-dessus du plafond


def test_transaction_detail_and_export(client):
    detail = client.get("/transactions/3").json()
    assert detail["id"] == 3 and detail["amount"] == 3.0
    assert client.get("/transactions/9999").status_code == 404

    exported = client.get("/transactions/export?ids=1,3")
    assert exported.headers["content-type"].startswith("text/csv")
    lines = exported.text.strip().splitlines()
    assert lines[0].startswith("transaction_id,time,v1")
    assert len(lines) == 3


# ---------------------------------------------------------------- transactions (corrections)


def _first_data_lines(n: int) -> list[str]:
    return dataset.RAW_CSV_PATH.read_text().splitlines()[1 : n + 1]


def test_changes_apply_update_delete_create_and_version_once(client, monkeypatch):
    calls = _fake_version(monkeypatch)
    before_lines = dataset.RAW_CSV_PATH.read_text().splitlines()
    version = client.get("/transactions?page_size=1").json()["base_version"]

    resp = client.post(
        "/transactions/changes",
        json={
            "base_version": version,
            "updates": [{"id": 2, "fields": {"amount": 999.5, "is_fraud": 1}}],
            "deletes": [5],
            "creates": [_valid_transaction(amount=77.0)],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert (body["rows_created"], body["rows_updated"], body["rows_deleted"]) == (1, 1, 1)
    assert body["commit_sha"] == "abc123"
    assert len(calls) == 1  # un seul commit pour tout le lot
    assert "1 row created, 1 row updated, 1 row deleted" in calls[0]
    assert "via dashboard, user analyste" in calls[0]

    after = dataset.RAW_CSV_PATH.read_text().splitlines()
    assert len(after) == len(before_lines)  # +1 créée, -1 supprimée
    assert after[3].split(",")[29] == "999.5" and after[3].split(",")[30] == "1"  # ligne id=2 (+1 en-tête)
    # Les lignes non touchées restent identiques à l'octet près (diff DVC minimal).
    assert after[1] == before_lines[1] and after[5] == before_lines[5]  # avant la ligne supprimée
    assert after[6] == before_lines[7]  # après la suppression de l'id 5 : décalage d'une ligne, contenu intact
    assert after[-1].split(",")[29] == "77.0"

    assert client.get("/transactions/5").json()["amount"] == 6.0  # la ligne suivante a pris la position 5
    run = client.get("/runs").json()[-1]
    assert run["trigger"] == "dashboard_edit" and run["commit_sha"] == "abc123" and run["user"] == "analyste"


def test_epoch_bumps_on_edits_but_not_on_appends(client, monkeypatch):
    _fake_version(monkeypatch)
    state.save_state({**state.DEFAULT_STATE, "threshold": 10_000})
    client.post("/data/simulate", json={"n": 2, "drift_intensity": "none"})  # ajout : les positions ne bougent pas
    assert client.get("/transactions?page_size=1").json()["base_version"] == "0"

    assert client.post("/transactions/changes", json={"base_version": "0", "deletes": [1]}).status_code == 200
    assert client.get("/transactions?page_size=1").json()["base_version"] == "1"
    # Un second éditeur resté sur l'ancienne version est refusé (les positions ont changé).
    assert client.post("/transactions/changes", json={"base_version": "0", "deletes": [1]}).status_code == 409


def test_changes_stale_base_version_is_rejected(client, monkeypatch):
    _fake_version(monkeypatch)
    resp = client.post("/transactions/changes", json={"base_version": "old", "deletes": [1]})
    assert resp.status_code == 409
    assert len(dataset.RAW_CSV_PATH.read_text().splitlines()) == 41


def test_changes_unknown_row_and_empty_batch(client, monkeypatch):
    _fake_version(monkeypatch)
    version = "0"
    assert client.post("/transactions/changes", json={"base_version": version, "deletes": [500]}).status_code == 422
    assert client.post("/transactions/changes", json={"base_version": version}).status_code == 422


def test_changes_are_rolled_back_when_versioning_fails(client, monkeypatch):
    original = dataset.RAW_CSV_PATH.read_text()
    discarded = []
    monkeypatch.setattr(versioning, "discard_uncommitted_dvc_change", lambda: discarded.append(True))

    def _boom(msg):
        raise versioning.VersioningError("dvc push a échoué")

    monkeypatch.setattr(versioning, "version_dataset", _boom)
    resp = client.post("/transactions/changes", json={"base_version": "0", "deletes": [1, 2]})
    assert resp.status_code == 502
    assert dataset.RAW_CSV_PATH.read_text() == original
    assert discarded == [True]


def test_changes_blocked_while_a_job_runs(client, monkeypatch):
    _fake_version(monkeypatch)
    jobs.create_job("continuous", "manual_retrain", user="x")
    resp = client.post("/transactions/changes", json={"base_version": "0", "deletes": [1]})
    assert resp.status_code == 409


# ---------------------------------------------------------------- versions


def test_list_versions_merges_recorded_metadata(client, monkeypatch):
    sep = "\x1f"
    log = "\n".join(
        [
            sep.join(["a" * 40, "Fraud Pipeline Bot", "2026-09-19T10:00:00+00:00", "Manual correction: 3 rows updated"]),
            sep.join(["b" * 40, "Yassin Farih", "2026-09-18T10:00:00+00:00", "data: +500 transactions (simulate) — seuil"]),
        ]
    )
    monkeypatch.setattr(versioning, "_run", lambda cmd, env=None: log)
    state.append_version({"commit_sha": "a" * 40, "user": "analyste", "rows_changed": 3, "rows_total": 284807, "kind": "dashboard_edit"})

    versions = client.get("/versions").json()
    assert versions[0]["rows_changed"] == 3 and versions[0]["user"] == "analyste"
    assert versions[1]["rows_changed"] == 500  # retrouvé dans le sujet du commit
    assert versions[1]["author"] == "Yassin Farih"


def test_rollback_rejects_unknown_or_malformed_commit(client, monkeypatch):
    monkeypatch.setattr(versioning, "_run", lambda cmd, env=None: "")
    assert client.post("/versions/not-a-sha/rollback").status_code == 422
    assert client.post("/versions/" + "c" * 40 + "/rollback").status_code == 422


def test_rollback_versions_pending_rows_first_then_restores(client, monkeypatch):
    state.save_state({**state.DEFAULT_STATE, "pending_count": 7})
    messages = _fake_version(monkeypatch, sha="pre1")
    monkeypatch.setattr(
        versioning, "rollback", lambda sha, message: {"md5": "old", "commit_sha": "rb1", "timestamp": "2026-01-02T00:00:00+00:00"}
    )
    resp = client.post("/versions/" + "d" * 40 + "/rollback")
    assert resp.status_code == 200
    assert resp.json()["commit_sha"] == "rb1"
    assert "avant rollback" in messages[0]
    assert state.load_state()["pending_count"] == 0
    assert client.get("/runs").json()[-1]["trigger"] == "rollback"


# ---------------------------------------------------------------- jobs / runs


class _FakePopen:
    def __init__(self, lines, returncode=0):
        self.stdout = iter(lines)
        self._returncode = returncode

    def wait(self):
        return self._returncode


def _dagster_line(op: str, event: str) -> str:
    return f"2026-09-19 19:08:14 +0100 - dagster - DEBUG - job - abc - 1 - {op} - {event} - message\n"


def test_execute_tracks_stages_from_dagster_events(client, monkeypatch):
    lines = []
    for op in ("ingest", "validate", "transform", "test_data"):
        lines += [_dagster_line(op, "STEP_START"), _dagster_line(op, "STEP_SUCCESS")]
    monkeypatch.setattr(jobs.subprocess, "Popen", lambda *a, **k: _FakePopen(lines))

    job = jobs.create_job("pipeline", "manual_pipeline", user="analyste")
    jobs.execute(job)

    record = client.get(f"/jobs/{job.run_id}").json()
    assert record["status"] == "completed"
    assert [s["status"] for s in record["stages"]] == ["completed"] * 4
    assert [s["name"] for s in record["stages"]] == ["Ingestion", "Validation", "Transformation", "Tests"]
    assert not jobs.is_busy()


def test_execute_marks_failed_stage_and_keeps_log(client, monkeypatch):
    lines = [
        _dagster_line("ingest", "STEP_START"),
        _dagster_line("ingest", "STEP_SUCCESS"),
        _dagster_line("validate", "STEP_START"),
        _dagster_line("validate", "STEP_FAILURE"),
        "RuntimeError: boom\n",
    ]
    monkeypatch.setattr(jobs.subprocess, "Popen", lambda *a, **k: _FakePopen(lines, returncode=1))

    job = jobs.create_job("pipeline", "manual_pipeline")
    jobs.execute(job)

    record = client.get(f"/jobs/{job.run_id}").json()
    assert record["status"] == "failed"
    assert [s["status"] for s in record["stages"]] == ["completed", "failed", "pending", "pending"]
    assert "boom" in record["note"]


def test_execute_falls_back_to_single_stage_when_log_format_unknown(client, monkeypatch):
    monkeypatch.setattr(jobs.subprocess, "Popen", lambda *a, **k: _FakePopen(["something unexpected\n"]))
    job = jobs.create_job("pipeline", "manual_pipeline")
    jobs.execute(job)
    stages = client.get(f"/jobs/{job.run_id}").json()["stages"]
    assert [(s["name"], s["status"]) for s in stages] == [("Pipeline", "completed")]


def test_only_one_job_at_a_time(client):
    jobs.create_job("pipeline", "manual_pipeline")
    with pytest.raises(jobs.JobBusyError):
        jobs.create_job("continuous", "manual_retrain")
    assert client.post("/pipeline/run").status_code == 409


def test_job_environment_disables_promotion_unless_auto_promote(client, monkeypatch):
    assert jobs._job_env()["FRAUD_REGISTER_NO_PROMOTE"] == "1"
    state.save_state({**state.DEFAULT_STATE, "auto_promote": True})
    monkeypatch.delenv("FRAUD_REGISTER_NO_PROMOTE", raising=False)
    assert "FRAUD_REGISTER_NO_PROMOTE" not in jobs._job_env()


def test_pipeline_endpoints_start_a_job(client, monkeypatch):
    started = []
    monkeypatch.setattr(jobs, "execute", lambda job: started.append(job))
    run_id = client.post("/pipeline/run").json()["run_id"]
    assert started[0].kind == "pipeline" and started[0].trigger == "manual_pipeline"
    assert client.get(f"/jobs/{run_id}").json()["status"] == "running"


def test_runs_status_filter_and_rerun(client, monkeypatch):
    state.append_run({"timestamp": "t1", "trigger": "simulate", "rows_added": 5, "status": "completed", "run_id": "r1", "job_kind": "continuous"})
    state.append_run({"timestamp": "t2", "trigger": "ingest", "rows_added": 5, "status": "failed", "run_id": "r2"})
    state.append_run({"timestamp": "t3", "trigger": "dashboard_edit", "rows_added": 1, "status": "versioned", "run_id": "r3"})
    state.append_run({"timestamp": "t1", "trigger": "simulate", "rows_added": 5, "status": "failed", "run_id": "r1"})  # état final de r1

    assert [r["run_id"] for r in client.get("/runs?status=failed").json()] == ["r1", "r2"]
    assert [r["run_id"] for r in client.get("/runs?status=completed").json()] == ["r3"]
    assert client.get("/runs?status=bogus").status_code == 422

    started = []
    monkeypatch.setattr(jobs, "execute", lambda job: started.append(job))
    assert client.post("/runs/r2/rerun").status_code == 200
    assert started[0].trigger == "rerun" and started[0].kind == "continuous"
    assert client.post("/runs/r3/rerun").status_code == 422  # une correction n'est pas relançable
    assert client.post("/runs/nope/rerun").status_code == 404


# ---------------------------------------------------------------- dérive


def test_drift_current_history_and_distribution(client):
    current = client.get("/drift/current").json()
    assert set(current["features"]) == {"amount", "log_amount", "hour_of_day"}
    assert all(f["level"] in {"green", "orange", "red"} for f in current["features"].values())
    assert current["mode"] == "halves"  # pas assez de nouvelles données : 2 moitiés temporelles

    client.post("/drift/check")
    client.post("/drift/check")  # même version du dataset : pas de doublon dans l'historique
    assert len(client.get("/drift/history").json()) == 1

    distribution = client.get("/drift/distribution?feature=amount").json()
    assert distribution and {"bucket", "reference", "recent"} <= set(distribution[0])
    assert client.get("/drift/distribution?feature=nope").status_code == 404


def test_drift_uses_new_data_mode_and_flags_alert(client, monkeypatch):
    state.save_state({**state.DEFAULT_STATE, "threshold": 10_000})
    client.post("/data/simulate", json={"n": 300, "drift_intensity": "strong"})
    current = client.get("/drift/current").json()
    assert current["mode"] == "new_data"
    assert current["recent_rows"] == 300
    assert current["features"]["amount"]["level"] == "red"
    assert current["alert"] is True


# ---------------------------------------------------------------- registry / déploiement / services


class _FakeVersion:
    def __init__(self, version, stage, run_id):
        self.version, self.current_stage, self.run_id, self.creation_timestamp = str(version), stage, run_id, 0


class _FakeRun:
    def __init__(self, metrics):
        self.data = type("D", (), {"metrics": metrics})()


class _FakeClient:
    def __init__(self):
        self.versions = {
            "Staging": _FakeVersion(3, "Staging", "run3"),
            "Production": _FakeVersion(2, "Production", "run2"),
        }
        self.metrics = {"run3": {"pr_auc": 0.86, "roc_auc": 0.98, "f1": 0.83}, "run2": {"pr_auc": 0.84, "roc_auc": 0.97, "f1": 0.81}}
        self.transitions = []

    def get_latest_versions(self, name, stages):
        version = self.versions.get(stages[0])
        return [version] if version else []

    def get_run(self, run_id):
        return _FakeRun(self.metrics[run_id])

    def get_model_version(self, name, version):
        return next(v for v in self.versions.values() if v.version == str(version))

    def transition_model_version_stage(self, **kwargs):
        self.transitions.append(kwargs)


def test_models_comparison_shows_candidate_vs_production(client, monkeypatch):
    monkeypatch.setattr(models, "_client", lambda: _FakeClient())
    body = client.get("/models/comparison").json()
    assert body["candidate"]["version"] == 3 and body["production"]["version"] == 2
    assert body["delta"]["pr_auc"] == pytest.approx(0.02)


def test_models_comparison_with_an_empty_registry(client, monkeypatch):
    class _EmptyRegistry(_FakeClient):
        def get_latest_versions(self, name, stages):
            raise models.mlflow.exceptions.MlflowException("Registered Model with name=x not found")

    monkeypatch.setattr(models, "_client", lambda: _EmptyRegistry())
    resp = client.get("/models/comparison")
    assert resp.status_code == 200
    assert resp.json() == {"candidate": None, "production": None, "delta": {}}


def test_models_approve_promotes_then_requests_redeploy(client, monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(models, "_client", lambda: fake)
    promoted = []
    monkeypatch.setattr(
        models.register_model,
        "promote_version",
        lambda c, v, commit_artifacts_flag: promoted.append((v, commit_artifacts_flag)) or {"version": v, "run_id": "run3", "pr_auc": 0.86, "commit_sha": "m1"},
    )
    monkeypatch.setattr(deploy, "restart_api", lambda: {"status": "requested", "detail": "ok"})

    body = client.post("/models/approve", json={"version": 3}).json()
    assert promoted == [(3, True)]
    assert body["redeploy"]["status"] == "requested"
    # Approuver une version qui n'est pas (ou plus) en Staging est refusé.
    assert client.post("/models/approve", json={"version": 2}).status_code == 409


def test_models_reject_archives_candidate(client, monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(models, "_client", lambda: fake)
    assert client.post("/models/reject", json={"version": 3}).json()["stage"] == "Archived"
    assert fake.transitions[0]["stage"] == "Archived"


def test_redeploy_is_skipped_without_komodo_configuration(monkeypatch):
    for name in deploy.REQUIRED_ENV:
        monkeypatch.delenv(name, raising=False)
    result = deploy.restart_api()
    assert result["status"] == "skipped" and "KOMODO_URL" in result["detail"]


def test_services_health_reports_up_and_down(client, monkeypatch):
    monkeypatch.setattr(services, "_ping", lambda url, timeout: ("mlflow" in url, 12 if "mlflow" in url else None))
    body = {s["key"]: s for s in client.get("/services/health").json()}
    assert body["mlflow"]["up"] is True and body["mlflow"]["latency_ms"] == 12
    assert body["grafana"]["up"] is False


# ---------------------------------------------------------------- /metrics (Prometheus)


def _metric_values(text: str) -> dict[str, float]:
    return {
        line.rsplit(" ", 1)[0]: float(line.rsplit(" ", 1)[1])
        for line in text.splitlines()
        if line and not line.startswith("#")
    }


def test_metrics_endpoint_is_public_and_exposes_drift_and_dataset(client):
    response = TestClient(app).get("/metrics")  # sans jeton : Prometheus ne s'authentifie pas
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")

    values = _metric_values(response.text)
    assert values["fraud_dataset_rows"] == 40
    assert values["fraud_drift_available"] == 1
    assert values["fraud_drift_threshold"] == 0.25
    assert values["fraud_drift_alert"] in (0, 1)
    assert 'fraud_drift_psi{feature="amount"}' in values
    assert values["fraud_drift_max_psi"] == max(v for k, v in values.items() if k.startswith("fraud_drift_psi{"))


def test_metrics_reports_last_finished_pipeline_run(client):
    assert "fraud_pipeline_last_run_success" not in TestClient(app).get("/metrics").text  # aucun run encore

    base = {"trigger": "manual", "rows_added": 0, "commit_sha": None, "note": None, "job_kind": "pipeline"}
    state.append_run({**base, "run_id": "a", "timestamp": "2026-01-01T00:00:00+00:00", "status": "completed"})
    state.append_run({**base, "run_id": "b", "timestamp": "2026-01-02T00:00:00+00:00", "status": "failed"})
    state.append_run({**base, "run_id": "c", "timestamp": "2026-01-03T00:00:00+00:00", "status": "running"})

    values = _metric_values(TestClient(app).get("/metrics").text)
    assert values["fraud_pipeline_last_run_success"] == 0  # 'b' : dernier run *terminé*
    assert values["fraud_pipeline_last_run_timestamp_seconds"] == 1767312000.0


def test_metrics_survives_missing_dataset(client, monkeypatch, tmp_path):
    monkeypatch.setattr(dataset, "RAW_CSV_PATH", tmp_path / "absent.csv")
    values = _metric_values(TestClient(app).get("/metrics").text)
    assert values["fraud_drift_available"] == 0
    assert "fraud_drift_max_psi" not in values
