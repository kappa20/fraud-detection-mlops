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

DEFAULT_THRESHOLD = 100


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"threshold": DEFAULT_THRESHOLD, "pending_count": 0}


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


def load_runs(limit: int = 50) -> list[dict]:
    if not RUNS_LOG_PATH.exists():
        return []
    lines = [line for line in RUNS_LOG_PATH.read_text().splitlines() if line.strip()]
    return [json.loads(line) for line in lines[-limit:]]
