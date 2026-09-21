"""Vérification de l'état des services de l'écosystème (MLflow, Grafana,
Prometheus, API de scoring, Dagster, MinIO).

Les pings partent du *serveur* : depuis le navigateur ils seraient bloqués
par CORS, ou par le contenu mixte (interface en https, services en http).
Dans le réseau docker on joint les services par leur nom interne ; les
URL publiques (exp.s3.fsbm.ma:46xx) restent celles des liens de l'interface.
Chaque URL se surcharge par variable d'environnement (HEALTH_URL_<CLE>).
"""

import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

# clé -> (libellé, URL de santé interne par défaut, URL publique)
SERVICES = {
    "mlflow": ("MLflow Registry", "http://mlflow:5000/health", "http://exp.s3.fsbm.ma:4602/#/models"),
    "grafana": ("Grafana", "http://grafana:3000/api/health", "http://exp.s3.fsbm.ma:4603/?orgId=1"),
    "prometheus": ("Prometheus", "http://prometheus:9090/-/healthy", "http://exp.s3.fsbm.ma:4604/graph"),
    "scoring": ("API de scoring (Swagger)", "http://api:8000/health", "http://exp.s3.fsbm.ma:4601/docs"),
    "dagster": ("Dagster (orchestration)", "http://dagster:3000/server_info", "http://exp.s3.fsbm.ma:4608"),
    "minio": ("MinIO (stockage DVC)", "http://minio:9000/minio/health/live", "http://exp.s3.fsbm.ma:4606"),
}


def _ping(url: str, timeout: float) -> tuple[bool, int | None]:
    started = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            ok = 200 <= response.status < 400
    except urllib.error.HTTPError:
        ok = False
    except (urllib.error.URLError, TimeoutError, OSError):
        return False, None
    return ok, int((time.monotonic() - started) * 1000)


def check_all(timeout: float = 2.0) -> list[dict]:
    def check(item: tuple[str, tuple[str, str, str]]) -> dict:
        key, (label, default_url, public_url) = item
        url = os.environ.get(f"HEALTH_URL_{key.upper()}", default_url)
        up, latency_ms = _ping(url, timeout)
        return {"key": key, "label": label, "url": public_url, "up": up, "latency_ms": latency_ms}

    with ThreadPoolExecutor(max_workers=len(SERVICES)) as pool:
        return list(pool.map(check, SERVICES.items()))
