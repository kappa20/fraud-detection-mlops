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
DVC_FILE_REL = "data/raw/creditcard.csv.dvc"
DATASET_REL = "data/raw/creditcard.csv"

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
    if not DVC_FILE.exists():
        return None
    match = re.search(r"md5:\s*(\S+)", DVC_FILE.read_text())
    return match.group(1) if match else None


def _bot_env() -> dict:
    import os

    return {
        **os.environ,
        "GIT_AUTHOR_NAME": BOT_NAME,
        "GIT_AUTHOR_EMAIL": BOT_EMAIL,
        "GIT_COMMITTER_NAME": BOT_NAME,
        "GIT_COMMITTER_EMAIL": BOT_EMAIL,
    }


def version_dataset(commit_message: str) -> dict:
    """Fait tourner dvc add + dvc push + git commit (local) sur le dataset
    brut, et renvoie les métadonnées de la nouvelle version (md5, commit)."""
    _run(["dvc", "add", DATASET_REL])
    _run(["dvc", "push"])
    _run(["git", "add", DVC_FILE_REL])
    _run(["git", "commit", "-m", commit_message], env=_bot_env())
    commit_sha = _run(["git", "rev-parse", "HEAD"])

    return {
        "md5": _extract_md5(),
        "commit_sha": commit_sha,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


_SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
_ROWS_IN_SUBJECT_RE = re.compile(r"data: \+(\d+) transactions")


def list_versions(limit: int = 50) -> list[dict]:
    """Historique des versions du dataset : un commit git touchant le .dvc
    = une version. Les métadonnées (lignes modifiées, résumé, total) viennent
    du journal versions.jsonl, alimenté par la plateforme ; pour les commits
    plus anciens (ou faits à la main) on retombe sur le sujet du commit."""
    from platform_api import state

    separator = "\x1f"
    output = _run(
        ["git", "log", f"-{limit}", f"--format=%H{separator}%an{separator}%aI{separator}%s", "--", DVC_FILE_REL]
    )
    recorded = {record["commit_sha"]: record for record in state.load_versions() if record.get("commit_sha")}

    versions = []
    for line in output.splitlines():
        sha, author, timestamp, subject = line.split(separator, 3)
        meta = recorded.get(sha, {})
        rows_changed = meta.get("rows_changed")
        if rows_changed is None:
            match = _ROWS_IN_SUBJECT_RE.search(subject)
            rows_changed = int(match.group(1)) if match else None
        versions.append(
            {
                "commit_sha": sha,
                "timestamp": timestamp,
                "author": author,
                "user": meta.get("user"),
                "rows_changed": rows_changed,
                "rows_total": meta.get("rows_total"),
                "summary": meta.get("summary") or subject,
                "kind": meta.get("kind"),
            }
        )
    return versions


def rollback(commit_sha: str, commit_message: str) -> dict:
    """Restaure le dataset tel qu'il était à `commit_sha`, sous la forme d'un
    NOUVEAU commit (l'historique n'est jamais réécrit, jamais poussé). Le blob
    doit exister dans le cache DVC local ou sur le remote MinIO."""
    if not _SHA_RE.match(commit_sha):
        raise VersioningError(f"Identifiant de commit invalide : {commit_sha!r}")
    known = {v["commit_sha"] for v in list_versions(limit=500)}
    if not any(sha.startswith(commit_sha) for sha in known):
        raise VersioningError(f"{commit_sha} n'est pas une version du dataset.")

    DVC_FILE.write_text(_run(["git", "show", f"{commit_sha}:{DVC_FILE_REL}"]) + "\n")
    try:
        try:
            _run(["dvc", "checkout", "--force", DATASET_REL])
        except VersioningError:
            # Blob absent du cache local : on le récupère depuis le remote MinIO.
            _run(["dvc", "pull", "--force", DATASET_REL])
    except VersioningError:
        # Échec : ne pas laisser un .dvc modifié mais non commité dans le dépôt.
        _run(["git", "checkout", "--", DVC_FILE_REL])
        raise

    _run(["git", "add", DVC_FILE_REL])
    _run(["git", "commit", "-m", commit_message], env=_bot_env())
    return {
        "md5": _extract_md5(),
        "commit_sha": _run(["git", "rev-parse", "HEAD"]),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def discard_uncommitted_dvc_change() -> None:
    """Annule un `dvc add` resté à moitié fait (ex. `dvc push` en échec) : le
    .dvc redevient identique au dernier commit, pour que le dépôt ne garde pas
    un pointeur modifié qui ne correspond à aucune version commitée."""
    try:
        _run(["git", "checkout", "--", DVC_FILE_REL])
    except VersioningError:
        pass  # rien à annuler, ou dépôt inaccessible : l'erreur d'origine prime
