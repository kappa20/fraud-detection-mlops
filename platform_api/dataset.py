"""Ajout de transactions au dataset brut (data/raw/creditcard.csv).

Écrit directement dans le CSV source, en préservant exactement l'en-tête
et l'ordre de colonnes du fichier Kaggle original ("Time","V1"..."V28",
"Amount","Class") pour qu'ingestion_dlt/sources.py continue de le lire
sans aucune modification — la plateforme fait grandir le même fichier que
celui déjà versionné par DVC, elle n'introduit pas un format parallèle.
"""

import csv
import threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_CSV_PATH = PROJECT_ROOT / "data" / "raw" / "creditcard.csv"

CSV_HEADER = ["Time"] + [f"V{i}" for i in range(1, 29)] + ["Amount", "Class"]

# Dataset Kaggle d'origine : au-delà, ce sont des lignes ajoutées par la
# plateforme (ingestion, simulation, corrections). Sert de référence à la
# simulation (échantillonnage) et au calcul de dérive (nouvelles données).
BASELINE_ROWS = 284_807
BASELINE_MAX_TIME = 172_792.0

# Sérialise toutes les écritures sur le CSV (ingestion/simulation en arrière-plan
# et corrections manuelles depuis le tableau de bord) : sans verrou, deux
# écritures concurrentes pourraient s'entrelacer ou perdre des lignes.
WRITE_LOCK = threading.RLock()


def fingerprint() -> str:
    """Empreinte peu coûteuse (mtime + taille) de la version courante du CSV.
    Sert de verrou optimiste côté interface (`base_version`) et d'invalidation
    du cache de lecture — bien moins cher qu'un md5 de 150 Mo à chaque requête."""
    if not RAW_CSV_PATH.exists():
        return "absent"
    stat = RAW_CSV_PATH.stat()
    return f"{stat.st_mtime_ns}-{stat.st_size}"


def append_rows(rows: list[dict]) -> None:
    """rows : dicts avec les clés du schéma API (minuscules) — time, v1..v28,
    amount, is_fraud — réécrites ici avec l'en-tête original (majuscules,
    "Class") attendu par le CSV source."""
    if not RAW_CSV_PATH.exists():
        raise FileNotFoundError(
            f"{RAW_CSV_PATH} introuvable — voir data/README.md ('dvc pull' requis avant de démarrer la plateforme)."
        )
    with WRITE_LOCK, RAW_CSV_PATH.open("a", newline="") as f:
        # lineterminator="\n" : le fichier Kaggle utilise LF ; le CRLF par défaut de
        # csv.writer produisait un fichier à fins de ligne mixtes.
        writer = csv.writer(f, lineterminator="\n")
        for row in rows:
            writer.writerow(row_to_csv_values(row))


def row_to_csv_values(row: dict) -> list:
    """Dict API (minuscules) -> valeurs dans l'ordre des colonnes du CSV source."""
    return [row["time"], *(row[f"v{i}"] for i in range(1, 29)), row["amount"], row["is_fraud"]]


_row_count_cache: tuple[str, int] = ("", 0)


def row_count() -> int:
    """Nombre de lignes de données (mis en cache tant que le CSV ne change pas :
    l'interface interroge /status toutes les quelques secondes)."""
    global _row_count_cache
    if not RAW_CSV_PATH.exists():
        return 0
    key = fingerprint()
    if _row_count_cache[0] != key:
        with RAW_CSV_PATH.open("r") as f:
            _row_count_cache = (key, sum(1 for _ in f) - 1)  # moins la ligne d'en-tête
    return _row_count_cache[1]
