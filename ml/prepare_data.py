"""Chargement des features et split stratifié train/test.

Source : table dbt `fct_transactions_features` (DuckDB), produite par la
Phase B du pipeline DataOps. Split stratifié sur `is_fraud` pour préserver
le ratio de fraude (0,17 %) dans les deux jeux — un split aléatoire simple
risquerait de produire un jeu de test avec trop peu (voire aucune) fraude.

Les colonnes v1-v28 (PCA anonymisées), amount, log_amount et hour_of_day
sont utilisées comme features numériques. `amount_bucket` (catégorielle)
est volontairement exclue de ce jeu de features de base pour rester simple
(cf. docs/ml/experiments_summary.md pour les pistes d'amélioration).
"""

from pathlib import Path
from typing import Tuple

import duckdb
import pandas as pd
from sklearn.model_selection import train_test_split

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = PROJECT_ROOT / "fraud_detection.duckdb"

FEATURE_COLUMNS = [f"v{i}" for i in range(1, 29)] + ["amount", "log_amount", "hour_of_day"]
TARGET_COLUMN = "is_fraud"


def load_features(db_path: str = str(DEFAULT_DB)) -> pd.DataFrame:
    con = duckdb.connect(db_path, read_only=True)
    try:
        return con.execute("SELECT * FROM main.fct_transactions_features").fetchdf()
    finally:
        con.close()


def split_train_test(
    df: pd.DataFrame, test_size: float = 0.2, random_state: int = 42
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]
    return train_test_split(X, y, test_size=test_size, random_state=random_state, stratify=y)


def get_train_test_data(
    db_path: str = str(DEFAULT_DB), test_size: float = 0.2, random_state: int = 42
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    df = load_features(db_path)
    return split_train_test(df, test_size=test_size, random_state=random_state)


if __name__ == "__main__":
    X_train, X_test, y_train, y_test = get_train_test_data()
    print(f"Train : {len(X_train)} lignes ({y_train.mean() * 100:.4f}% fraude)")
    print(f"Test  : {len(X_test)} lignes ({y_test.mean() * 100:.4f}% fraude)")
