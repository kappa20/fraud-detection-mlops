"""Ajout de transactions au dataset brut (data/raw/creditcard.csv).

Écrit directement dans le CSV source, en préservant exactement l'en-tête
et l'ordre de colonnes du fichier Kaggle original ("Time","V1"..."V28",
"Amount","Class") pour qu'ingestion_dlt/sources.py continue de le lire
sans aucune modification — la plateforme fait grandir le même fichier que
celui déjà versionné par DVC, elle n'introduit pas un format parallèle.
"""

import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_CSV_PATH = PROJECT_ROOT / "data" / "raw" / "creditcard.csv"

CSV_HEADER = ["Time"] + [f"V{i}" for i in range(1, 29)] + ["Amount", "Class"]


def append_rows(rows: list[dict]) -> None:
    """rows : dicts avec les clés du schéma API (minuscules) — time, v1..v28,
    amount, is_fraud — réécrites ici avec l'en-tête original (majuscules,
    "Class") attendu par le CSV source."""
    if not RAW_CSV_PATH.exists():
        raise FileNotFoundError(
            f"{RAW_CSV_PATH} introuvable — voir data/README.md ('dvc pull' requis avant de démarrer la plateforme)."
        )
    with RAW_CSV_PATH.open("a", newline="") as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(
                [row["time"], *(row[f"v{i}"] for i in range(1, 29)), row["amount"], row["is_fraud"]]
            )


def row_count() -> int:
    if not RAW_CSV_PATH.exists():
        return 0
    with RAW_CSV_PATH.open("r") as f:
        return sum(1 for _ in f) - 1  # moins la ligne d'en-tête
