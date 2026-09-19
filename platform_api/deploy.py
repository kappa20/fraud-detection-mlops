"""Redéploiement du service de scoring après approbation d'un modèle.

`fraud-api` monte ./ml/artifacts en lecture seule (docker-compose.yml) et
api/model_loader.py charge model.pkl au démarrage : une fois le nouveau
model.pkl écrit par ml/register_model.py::promote_version, un simple
*redémarrage* du conteneur suffit — pas de rebuild ni de git push.

Le redémarrage passe par l'API de Komodo (le conteneur platform-api n'a pas
accès au socket Docker). Variables d'environnement, à définir dans
l'Environment de la stack Komodo :

    KOMODO_URL         ex. https://komodo.s3.fsbm.ma
    KOMODO_API_KEY     clé d'API Komodo
    KOMODO_API_SECRET  secret associé
    KOMODO_STACK       nom ou id de la stack (ex. detection_de_fraude_bancaire)
    KOMODO_API_SERVICE service à redémarrer (défaut : api)

Si l'une d'elles manque, le redéploiement est "skipped" et l'interface
l'indique — la promotion MLflow, elle, a bien eu lieu.
"""

import json
import os
import urllib.error
import urllib.request

REQUIRED_ENV = ("KOMODO_URL", "KOMODO_API_KEY", "KOMODO_API_SECRET", "KOMODO_STACK")


def restart_api(timeout: float = 15.0) -> dict:
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        return {"status": "skipped", "detail": f"Variables non définies : {', '.join(missing)}"}

    # Exécution d'une action Komodo : POST {KOMODO_URL}/execute avec les
    # en-têtes X-Api-Key / X-Api-Secret ; RestartStack accepte la liste des
    # services à redémarrer. À valider contre la doc Komodo de la version
    # déployée (v2.x) au premier essai réel.
    body = {
        "type": "RestartStack",
        "params": {
            "stack": os.environ["KOMODO_STACK"],
            "services": [os.environ.get("KOMODO_API_SERVICE", "api")],
        },
    }
    request = urllib.request.Request(
        os.environ["KOMODO_URL"].rstrip("/") + "/execute",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Api-Key": os.environ["KOMODO_API_KEY"],
            "X-Api-Secret": os.environ["KOMODO_API_SECRET"],
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {"status": "requested", "detail": f"Komodo a répondu HTTP {response.status}."}
    except urllib.error.HTTPError as exc:
        return {"status": "failed", "detail": f"Komodo a répondu HTTP {exc.code}."}
    except (urllib.error.URLError, TimeoutError) as exc:
        return {"status": "failed", "detail": f"Komodo injoignable : {exc}"}
