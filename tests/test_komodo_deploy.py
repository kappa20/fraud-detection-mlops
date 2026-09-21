"""Déploiement Komodo gardé par la CI (scripts/komodo_deploy.py) — l'API de
Komodo est simulée, aucun appel réseau réel."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import komodo_deploy  # noqa: E402

ENV = {
    "KOMODO_URL": "https://komodo.example",
    "KOMODO_API_KEY": "k",
    "KOMODO_API_SECRET": "s",
    "KOMODO_STACK": "detection_de_fraude_bancaire",
}


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(komodo_deploy.time, "sleep", lambda _: None)


def _fake_api(monkeypatch, responses):
    calls = []

    def fake(base_url, path, body, key, secret, timeout=30.0):
        calls.append((path, body))
        return responses.pop(0)

    monkeypatch.setattr(komodo_deploy, "_call", fake)
    return calls


def test_missing_credentials_skips_without_failing(capsys):
    assert komodo_deploy.main({**ENV, "KOMODO_API_KEY": ""}) == 0
    assert "ignoré" in capsys.readouterr().out


def test_deploy_waits_for_update_to_complete(monkeypatch):
    calls = _fake_api(
        monkeypatch,
        [
            {"_id": {"$oid": "abc"}, "status": "InProgress"},
            {"_id": {"$oid": "abc"}, "status": "InProgress"},
            {"_id": {"$oid": "abc"}, "status": "Complete", "success": True},
        ],
    )
    assert komodo_deploy.main(ENV) == 0
    assert calls[0] == ("/execute", {"type": "DeployStack", "params": {"stack": "detection_de_fraude_bancaire"}})
    assert [c[0] for c in calls] == ["/execute", "/read", "/read"]
    assert calls[1][1] == {"type": "GetUpdate", "params": {"id": "abc"}}


def test_failed_deploy_returns_error_with_logs(monkeypatch, capsys):
    _fake_api(
        monkeypatch,
        [
            {
                "_id": {"$oid": "abc"},
                "status": "Complete",
                "success": False,
                "logs": [
                    {"stage": "Compose Up", "success": False, "stderr": "port is already allocated"},
                ],
            }
        ],
    )
    assert komodo_deploy.main(ENV) == 1
    out = capsys.readouterr().out
    assert "échoué" in out and "port is already allocated" in out


def test_deploy_still_running_past_timeout_fails(monkeypatch):
    _fake_api(monkeypatch, [{"_id": {"$oid": "abc"}, "status": "InProgress"}] * 50)
    monkeypatch.setattr(komodo_deploy.time, "monotonic", iter(range(0, 10_000, 500)).__next__)
    with pytest.raises(RuntimeError, match="toujours en cours"):
        komodo_deploy.deploy_stack(ENV, timeout_s=1000)


def test_health_url_is_polled_after_deploy(monkeypatch):
    _fake_api(monkeypatch, [{"_id": {"$oid": "abc"}, "status": "Complete", "success": True}])
    probed = []
    monkeypatch.setattr(komodo_deploy, "wait_healthy", probed.append)
    assert komodo_deploy.main({**ENV, "DEPLOY_HEALTH_URL": "http://exp.example:4607/health"}) == 0
    assert probed == ["http://exp.example:4607/health"]
