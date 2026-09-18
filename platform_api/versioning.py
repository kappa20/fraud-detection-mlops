"""Versioning DVC + git du dataset brut, déclenché quand le compteur de
mises à jour en attente atteint le seuil configuré (voir state.py).

Deux choix assumés :

- `dvc push` est exécuté automatiquement : il ne fait que pousser vers le
  remote MinIO déjà dédié à cet usage (voir data/README.md), aucun risque
  particulier.
- `git commit` reste local — jamais de `git push` automatique vers
  GitHub : embarquer un token d'écriture GitHub dans un conteneur exposé
  sur un serveur mutualisé (Komodo/vh3) serait un risque disproportionné
  pour un projet étudiant. Le commit local suffit à démontrer le
  versioning (hash du .dvc qui change, historique git visible dans le
  conteneur) ; le push vers GitHub, si souhaité, reste une action humaine
  volontaire.
- Le commit est attribué à une identité "bot" dédiée (et non à un membre
  de l'équipe) : c'est la plateforme elle-même qui déclenche ce commit,
  pas un développeur qui tape la commande à la main.
"""

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DVC_FILE = PROJECT_ROOT / "data" / "raw" / "creditcard.csv.dvc"

BOT_NAME = "Fraud Pipeline Bot"
BOT_EMAIL = "pipeline@fraud-detection-mlops.local"


class VersioningError(RuntimeError):
    """Levée quand une étape dvc/git échoue lors du versioning automatique."""


def _run(cmd: list[str], env: dict | None = None) -> str:
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise VersioningError(f"Commande échouée ({' '.join(cmd)}) : {result.stderr.strip()}")
    return result.stdout.strip()


def _extract_md5() -> str | None:
    match = re.search(r"md5:\s*(\S+)", DVC_FILE.read_text())
    return match.group(1) if match else None


def version_dataset(commit_message: str) -> dict:
    """Fait tourner dvc add + dvc push + git commit (local) sur le dataset
    brut, et renvoie les métadonnées de la nouvelle version (md5, commit)."""
    import os

    _run(["dvc", "add", "data/raw/creditcard.csv"])
    _run(["dvc", "push"])
    _run(["git", "add", "data/raw/creditcard.csv.dvc"])

    commit_env = {
        **os.environ,
        "GIT_AUTHOR_NAME": BOT_NAME,
        "GIT_AUTHOR_EMAIL": BOT_EMAIL,
        "GIT_COMMITTER_NAME": BOT_NAME,
        "GIT_COMMITTER_EMAIL": BOT_EMAIL,
    }
    _run(["git", "commit", "-m", commit_message], env=commit_env)
    commit_sha = _run(["git", "rev-parse", "HEAD"])

    return {
        "md5": _extract_md5(),
        "commit_sha": commit_sha,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
