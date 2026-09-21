"""Métriques Prometheus de la plateforme (GET /metrics, public comme /health).

Prometheus ne sait pas lire `data/state/*.jsonl` ni le CSV : ce module expose
l'état que le tableau de bord affiche déjà — dérive (PSI par feature vs seuil),
taille du dataset, dernier run du pipeline — pour que Grafana le trace dans le
temps et que les règles d'alerte (monitoring/prometheus/alerts.yml) puissent
réagir. Rien n'est recalculé "à la main" : on relit drift.compute_current()
(mis en cache tant que le dataset ne change pas), state et jobs.

Collecteur "à la demande" : les valeurs sont calculées à chaque scrape, dans un
registre dédié (pas de doublon de séries au rechargement du module, pas de
mélange avec les métriques par défaut du processus).
"""

from datetime import datetime

from prometheus_client import CollectorRegistry, generate_latest
from prometheus_client.core import GaugeMetricFamily

from platform_api import dataset, drift, jobs, state

CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"

# Runs lancés par le pipeline (et non les corrections manuelles / rollbacks,
# aussi journalisés dans runs.jsonl mais qui ne sont pas des exécutions).
_FINISHED = {"completed", "failed"}


def _last_finished_pipeline_run() -> dict | None:
    for run in reversed(state.load_runs(limit=200)):
        if run.get("job_kind") and run.get("status") in _FINISHED:
            return run
    return None


class PlatformCollector:
    def collect(self):
        config = state.load_state()

        yield _gauge("fraud_dataset_rows", "Lignes du dataset brut (data/raw/creditcard.csv).", dataset.row_count())
        yield _gauge(
            "fraud_pending_updates", "Mises à jour ingérées depuis le dernier ré-entraînement.", config["pending_count"]
        )
        yield _gauge("fraud_update_threshold", "Seuil de mises à jour déclenchant le pipeline.", config["threshold"])
        yield _gauge("fraud_pipeline_running", "1 si un job du pipeline est en cours.", int(jobs.is_busy()))

        last = _last_finished_pipeline_run()
        if last:
            yield _gauge(
                "fraud_pipeline_last_run_success", "1 si le dernier run terminé du pipeline a réussi, 0 sinon.",
                int(last["status"] == "completed"),
            )
            yield _gauge(
                "fraud_pipeline_last_run_timestamp_seconds", "Début du dernier run terminé du pipeline (epoch).",
                _epoch(last["timestamp"]),
            )

        yield from self._drift(config)

    @staticmethod
    def _drift(config: dict):
        try:
            summary = drift.summary(drift.compute_current())
        except Exception:  # noqa: BLE001 — CSV absent / DuckDB indisponible : on signale, on ne casse pas le scrape
            summary = None
        yield _gauge("fraud_drift_available", "1 si le PSI a pu être calculé à ce scrape.", int(summary is not None))
        if summary is None:
            return

        yield _gauge("fraud_drift_max_psi", "PSI maximal parmi les features surveillées.", summary["max_psi"])
        yield _gauge("fraud_drift_threshold", "Seuil de PSI au-delà duquel la dérive est signalée.", config["psi_threshold"])
        yield _gauge("fraud_drift_alert", "1 si max PSI >= seuil.", int(summary["alert"]))
        yield _gauge("fraud_drift_recent_rows", "Lignes de la fenêtre récente comparée à la référence.", summary["recent_rows"])

        per_feature = GaugeMetricFamily("fraud_drift_psi", "PSI par feature surveillée.", labels=["feature"])
        for name, feature in summary["features"].items():
            per_feature.add_metric([name], feature["psi"])
        yield per_feature


def _gauge(name: str, doc: str, value: float) -> GaugeMetricFamily:
    family = GaugeMetricFamily(name, doc)
    family.add_metric([], value)
    return family


def _epoch(iso_timestamp: str) -> float:
    return datetime.fromisoformat(iso_timestamp).timestamp()


def render() -> bytes:
    registry = CollectorRegistry()
    registry.register(PlatformCollector())
    return generate_latest(registry)
