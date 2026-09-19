"""Surveillance de la dérive des données pour le tableau de bord.

Réutilise `monitoring/drift_check.py` (PSI, seuils, buckets) — rien n'est
recalculé "à la main" ici. Contrairement au script CLI, qui lit le DuckDB
(donc l'état du dernier run dbt), on part du CSV via le cache de
transactions.py : la dérive est visible dès qu'un lot de données arrive,
sans attendre la fin du pipeline. Même définition des features que
dbt_fraud/models/marts/fct_transactions_features.sql (voir
drift_check.with_derived_features).

Chaque vérification est ajoutée à data/state/drift_history.jsonl (une ligne
par version du dataset) pour tracer l'évolution du PSI.
"""

import threading
from datetime import datetime, timezone

from monitoring import drift_check
from platform_api import dataset, jobs, state, transactions

_lock = threading.Lock()
_cache: dict = {"fingerprint": None, "result": None}


def compute_current() -> dict:
    """PSI courant par feature (mis en cache tant que le dataset ne change pas)."""
    fingerprint = dataset.fingerprint()
    with _lock:
        if _cache["fingerprint"] != fingerprint:
            frame = transactions._connection().execute("SELECT time AS time_seconds, amount FROM tx").fetchdf()
            result = drift_check.compute_drift(frame, new_data_after=dataset.BASELINE_MAX_TIME)
            _cache.update(fingerprint=fingerprint, result=result)
        return {**_cache["result"], "fingerprint": fingerprint}


def summary(result: dict) -> dict:
    """Vue sans les distributions (badges + alerte)."""
    threshold = state.load_state()["psi_threshold"]
    return {
        "mode": result["mode"],
        "reference_rows": result["reference_rows"],
        "recent_rows": result["recent_rows"],
        "max_psi": result["max_psi"],
        "psi_threshold": threshold,
        "alert": result["max_psi"] >= threshold,
        "features": {
            name: {"psi": f["psi"], "level": f["level"], "interpretation": f["interpretation"]}
            for name, f in result["features"].items()
        },
    }


def record_check(source: str) -> dict:
    """Calcule le PSI courant et l'ajoute à l'historique s'il concerne une
    version du dataset pas encore enregistrée (évite les doublons quand
    l'interface interroge plusieurs fois de suite)."""
    result = compute_current()
    history = state.load_drift_history(limit=1)
    if not history or history[-1].get("fingerprint") != result["fingerprint"]:
        state.append_drift(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": source,
                "fingerprint": result["fingerprint"],
                "mode": result["mode"],
                "recent_rows": result["recent_rows"],
                "max_psi": result["max_psi"],
                "psi": {name: f["psi"] for name, f in result["features"].items()},
            }
        )
    return summary(result)


def distribution(feature: str) -> list[dict]:
    result = compute_current()
    if feature not in result["features"]:
        raise KeyError(feature)
    return result["features"][feature]["distribution"]


def should_auto_retrain(drift_summary: dict) -> bool:
    config = state.load_state()
    return bool(config["auto_retrain_enabled"] and drift_summary["max_psi"] >= config["psi_threshold"]) and not (
        jobs.is_busy()
    )
