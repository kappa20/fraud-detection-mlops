"""Validation shift-left du schéma et de la qualité minimale des données ingérées.

Applique le principe "Shift Left" du Chapitre 3 du cours : contrôler dès
l'ingestion (avant les transformations dbt) plutôt que de découvrir un
problème en aval, dans le modèle ou en production. Reprend le pattern de
`td/tp_chapitre_2/tp_chapitre2_pipeline/pipeline/validate.py` (colonnes
requises + nullité), étendu avec des tests de domaine (Chapitre 3, famille
"Tests de Contenu").
"""

import argparse
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = PROJECT_ROOT / "fraud_detection.duckdb"

# dlt normalise les noms de colonnes en snake_case/minuscules à l'ingestion
# (ex: "Amount" -> "amount") : on valide donc sur les noms normalisés.
REQUIRED_COLUMNS = {"time", "amount", "class", *(f"v{i}" for i in range(1, 29))}


def validate(db_path: str, table: str = "raw.transactions_raw") -> None:
    con = duckdb.connect(db_path, read_only=True)
    try:
        # Test de schéma (Chapitre 3) : structure attendue présente
        columns = {row[0] for row in con.execute(f"DESCRIBE {table}").fetchall()}
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(f"Colonnes manquantes dans {table} : {sorted(missing)}")

        # Test de nullité (Chapitre 3, famille "Tests de Contenu")
        null_amount, null_class, total = con.execute(
            f"SELECT COUNT(*) FILTER (WHERE amount IS NULL), "
            f"       COUNT(*) FILTER (WHERE class IS NULL), "
            f"       COUNT(*) FROM {table}"
        ).fetchone()
        if null_amount or null_class:
            raise ValueError(
                f"Données invalides : {null_amount} amount nuls, "
                f"{null_class} class nuls sur {total} lignes"
            )

        # Test de domaine (Chapitre 3, famille "Tests de Contenu")
        invalid_class = con.execute(
            f"SELECT COUNT(*) FROM {table} WHERE class NOT IN (0, 1)"
        ).fetchone()[0]
        if invalid_class:
            raise ValueError(f"{invalid_class} lignes avec class hors domaine {{0,1}}")

        negative_amount = con.execute(
            f"SELECT COUNT(*) FROM {table} WHERE amount < 0"
        ).fetchone()[0]
        if negative_amount:
            raise ValueError(f"{negative_amount} lignes avec amount négatif")

        print(f"Validation réussie : {total} lignes, schéma et qualité minimale OK")
    finally:
        con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb", default=str(DEFAULT_DB))
    parser.add_argument("--table", default="raw.transactions_raw")
    args = parser.parse_args()
    validate(args.duckdb, args.table)


if __name__ == "__main__":
    main()
