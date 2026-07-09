"""Ingestion automatisée : data/raw/creditcard.csv -> DuckDB (schéma raw).

Usage :
    python ingestion_dlt/run_pipeline.py
    python ingestion_dlt/run_pipeline.py --csv chemin/vers.csv --duckdb chemin/vers.duckdb
"""

import argparse
from pathlib import Path

import dlt
from sources import creditcard_source

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = PROJECT_ROOT / "data" / "raw" / "creditcard.csv"
DEFAULT_DB = PROJECT_ROOT / "fraud_detection.duckdb"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default=str(DEFAULT_CSV))
    parser.add_argument("--duckdb", default=str(DEFAULT_DB))
    args = parser.parse_args()

    if not Path(args.csv).exists():
        raise FileNotFoundError(
            f"Fichier source introuvable : {args.csv}\n"
            "Voir data/README.md pour les instructions de telechargement du dataset Kaggle."
        )

    # dlt persiste localement (~/.dlt/pipelines/<nom>/) le CWD du premier run
    # et l'utilise pour resoudre les chemins relatifs des runs suivants, meme
    # depuis un autre repertoire : on resout donc toujours en chemin absolu
    # pour ne pas dependre de cet etat cache (piege reproductibilite —
    # cf. Chapitre 2, "ca marche sur mon laptop / ca marche pas ailleurs").
    duckdb_path = str(Path(args.duckdb).resolve())

    pipeline = dlt.pipeline(
        pipeline_name="fraud_ingestion",
        destination=dlt.destinations.duckdb(duckdb_path),
        dataset_name="raw",
    )
    load_info = pipeline.run(creditcard_source(args.csv))
    print(load_info)


if __name__ == "__main__":
    main()
