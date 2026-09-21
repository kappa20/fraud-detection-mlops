"""Déploiement continu gardé par la CI : redéploie la stack Komodo *après* que
les tests ont réussi, puis attend le résultat.

Pourquoi : le webhook GitHub -> Komodo déploie à chaque push, que la CI soit
verte ou non. Ce script est appelé par le job `deploy` de
.github/workflows/ci.yml (`needs: test`) — le webhook doit donc être retiré de
GitHub (Settings > Webhooks) et/ou désactivé dans la stack Komodo, sinon un
commit cassé part quand même en production. Voir docs/03_installation.md.

Variables d'environnement (secrets GitHub Actions) :
    KOMODO_URL, KOMODO_API_KEY, KOMODO_API_SECRET, KOMODO_STACK
    DEPLOY_HEALTH_URL   (optionnel) URL sondée après le déploiement, ex.
                        http://exp.s3.fsbm.ma:4607/health

Si l'une des quatre premières manque, le déploiement est ignoré (avertissement,
code 0) : forks, dépôt pas encore configuré.

API Komodo (v2.x) : POST /execute {"type": "DeployStack", ...} renvoie un
`Update` ; POST /read {"type": "GetUpdate", ...} permet de suivre son statut
(Queued -> InProgress -> Complete, avec `success`). Même convention que
platform_api/deploy.py (RestartStack).
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

REQUIRED_ENV = ("KOMODO_URL", "KOMODO_API_KEY", "KOMODO_API_SECRET", "KOMODO_STACK")


def _call(base_url: str, path: str, body: dict, key: str, secret: str, timeout: float = 30.0) -> dict:
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "X-Api-Key": key, "X-Api-Secret": secret},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode())


def _update_id(update: dict) -> str | None:
    raw = update.get("_id")
    return raw.get("$oid") if isinstance(raw, dict) else raw


def _failure_details(update: dict) -> str:
    logs = update.get("logs") or []
    failed = [log for log in logs if not log.get("success", True)] or logs[-1:]
    return "\n".join(f"[{log.get('stage')}] {log.get('stderr') or log.get('stdout')}" for log in failed)[-3000:]


def deploy_stack(env: dict, timeout_s: float = 1200.0, poll_s: float = 10.0) -> None:
    base, key, secret, stack = (env[name] for name in REQUIRED_ENV)
    update = _call(base, "/execute", {"type": "DeployStack", "params": {"stack": stack}}, key, secret)
    update_id = _update_id(update)
    print(f"DeployStack demandé pour '{stack}' (update {update_id}).")

    deadline = time.monotonic() + timeout_s
    while update.get("status") != "Complete":
        if update_id is None:
            print("Réponse Komodo sans identifiant d'update : suivi impossible, on s'en remet au test de santé.")
            return
        if time.monotonic() > deadline:
            raise RuntimeError(f"Déploiement toujours en cours après {timeout_s:.0f} s.")
        time.sleep(poll_s)
        update = _call(base, "/read", {"type": "GetUpdate", "params": {"id": update_id}}, key, secret)

    if not update.get("success"):
        raise RuntimeError("Le déploiement Komodo a échoué :\n" + _failure_details(update))
    print("Déploiement Komodo terminé avec succès.")


def wait_healthy(url: str, timeout_s: float = 300.0, poll_s: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_s
    last_error = "aucune réponse"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                if 200 <= response.status < 300:
                    print(f"{url} répond HTTP {response.status}.")
                    return
                last_error = f"HTTP {response.status}"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
        time.sleep(poll_s)
    raise RuntimeError(f"{url} ne répond pas après {timeout_s:.0f} s ({last_error}).")


def main(env: dict | None = None) -> int:
    env = dict(os.environ if env is None else env)
    missing = [name for name in REQUIRED_ENV if not env.get(name)]
    if missing:
        print(f"::warning::Variables absentes ({', '.join(missing)}) : déploiement Komodo ignoré.")
        return 0
    try:
        deploy_stack(env)
        if env.get("DEPLOY_HEALTH_URL"):
            wait_healthy(env["DEPLOY_HEALTH_URL"])
    except (RuntimeError, urllib.error.URLError, TimeoutError) as exc:
        print(f"::error::{exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
