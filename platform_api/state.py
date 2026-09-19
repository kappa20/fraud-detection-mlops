"""État persistant du déclencheur (seuil de mises à jour, compteur en attente).

Stocké dans data/state/pipeline_state.json plutôt qu'en mémoire process :
un redémarrage/redéploiement du conteneur (fréquent sur Komodo, cf.
webhook auto-deploy) ne doit pas remettre silencieusement le compteur à
zéro ni perdre le seuil configuré par la banque.
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = PROJECT_ROOT / "data" / "state" / "pipeline_state.json"
RUNS_LOG_PATH = PROJECT_ROOT / "data" / "state" / "runs.jsonl"
VERSIONS_LOG_PATH = PROJECT_ROOT / "data" / "state" / "versions.jsonl"
DRIFT_HISTORY_PATH = PROJECT_ROOT / "data" / "state" / "drift_history.jsonl"

DEFAULT_THRESHOLD = 100
DEFAULT_PSI_THRESHOLD = 0.25

# Valeurs par défaut de la configuration ; un fichier d'état plus ancien
# (sans les clés ajoutées par le tableau de bord) est complété à la lecture.
DEFAULT_STATE = {
    "threshold": DEFAULT_THRESHOLD,
    "pending_count": 0,
    "auto_promote": False,  # False = un humain approuve la promotion dans le tableau de bord
    "auto_retrain_enabled": False,
    "psi_threshold": DEFAULT_PSI_THRESHOLD,
    # Incrémenté à chaque correction manuelle ou rollback (jamais à un simple
    # ajout de lignes) : sert de verrou optimiste, car les identifiants de
    # ligne sont des positions qui ne se décalent qu'à une suppression.
    "dataset_epoch": 0,
}


def load_state() -> dict:
    if STATE_PATH.exists():
        return {**DEFAULT_STATE, **json.loads(STATE_PATH.read_text())}
    return dict(DEFAULT_STATE)


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))


def append_run(run_record: dict) -> None:
    RUNS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RUNS_LOG_PATH.open("a") as f:
        f.write(json.dumps(run_record) + "\n")


def load_last_run() -> dict | None:
    if not RUNS_LOG_PATH.exists():
        return None
    lines = [line for line in RUNS_LOG_PATH.read_text().splitlines() if line.strip()]
    if not lines:
        return None
    return json.loads(lines[-1])


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")


def load_runs(limit: int = 50) -> list[dict]:
    """Derniers runs, dédoublonnés par `run_id` (un run "en cours" est réécrit
    à chaque changement d'étape : la dernière ligne d'un run_id fait foi)."""
    latest: dict[str, dict] = {}
    for index, record in enumerate(_read_jsonl(RUNS_LOG_PATH)):
        # Anciennes lignes (avant le suivi par étapes) sans run_id : identifiant
        # synthétique stable (le fichier est en ajout seul, l'index ne bouge pas).
        run_id = record.get("run_id") or f"legacy-{index}"
        latest[run_id] = {**record, "run_id": run_id}
    return list(latest.values())[-limit:]


def append_version(record: dict) -> None:
    _append_jsonl(VERSIONS_LOG_PATH, record)


def load_versions() -> list[dict]:
    return _read_jsonl(VERSIONS_LOG_PATH)


def append_drift(record: dict) -> None:
    _append_jsonl(DRIFT_HISTORY_PATH, record)


def load_drift_history(limit: int = 30) -> list[dict]:
    return _read_jsonl(DRIFT_HISTORY_PATH)[-limit:]
