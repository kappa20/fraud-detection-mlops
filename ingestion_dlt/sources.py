"""Source dlt pour le dataset Kaggle "Credit Card Fraud Detection" (ULB).

Contrairement au TP du Chapitre 2 (qui écrit directement un DataFrame pandas
dans DuckDB via `CREATE OR REPLACE TABLE ... FROM df`), on passe ici par une
vraie ressource dlt : lecture par chunks (mémoire bornée quelle que soit la
taille du fichier source), inférence de schéma gérée par dlt, et ajout
automatique des colonnes de traçabilité `_dlt_load_id` / `_dlt_id` qui
permettent de savoir de quel run d'ingestion provient chaque ligne.
"""

from typing import Iterator

import dlt
import pandas as pd

DEFAULT_CHUNKSIZE = 50_000


@dlt.resource(name="transactions_raw", write_disposition="replace")
def transactions_resource(csv_path: str, chunksize: int = DEFAULT_CHUNKSIZE) -> Iterator[list[dict]]:
    """Lit le CSV source par blocs et fournit les enregistrements à dlt."""
    for chunk in pd.read_csv(csv_path, chunksize=chunksize):
        yield chunk.to_dict("records")


@dlt.source
def creditcard_source(csv_path: str, chunksize: int = DEFAULT_CHUNKSIZE):
    return transactions_resource(csv_path, chunksize)
