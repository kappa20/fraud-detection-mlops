"""Tests unitaires de quality/validate_schema.py (Livrable 4/8).

Utilise une base DuckDB temporaire (pas la base réelle du projet) pour
tester chaque règle de validation indépendamment.
"""

import duckdb
import pandas as pd
import pytest

from quality.validate_schema import validate


def _valid_frame(n: int = 10) -> pd.DataFrame:
    data = {"time": list(range(n)), "amount": [10.0] * n, "class": [0] * n}
    for i in range(1, 29):
        data[f"v{i}"] = [0.1] * n
    return pd.DataFrame(data)


def _make_db(tmp_path, df: pd.DataFrame) -> str:
    db_path = str(tmp_path / "test.duckdb")
    con = duckdb.connect(db_path)
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    con.execute("CREATE TABLE raw.transactions_raw AS SELECT * FROM df")
    con.close()
    return db_path


def test_validate_passes_on_clean_data(tmp_path):
    db_path = _make_db(tmp_path, _valid_frame())
    validate(db_path)  # ne doit pas lever d'exception


def test_validate_fails_on_missing_column(tmp_path):
    df = _valid_frame().drop(columns=["amount"])
    db_path = _make_db(tmp_path, df)
    with pytest.raises(ValueError, match="Colonnes manquantes"):
        validate(db_path)


def test_validate_fails_on_null_amount(tmp_path):
    df = _valid_frame()
    df.loc[0, "amount"] = None
    db_path = _make_db(tmp_path, df)
    with pytest.raises(ValueError, match="Données invalides"):
        validate(db_path)


def test_validate_fails_on_invalid_class_domain(tmp_path):
    df = _valid_frame()
    df.loc[0, "class"] = 2
    db_path = _make_db(tmp_path, df)
    with pytest.raises(ValueError, match="hors domaine"):
        validate(db_path)


def test_validate_fails_on_negative_amount(tmp_path):
    df = _valid_frame()
    df.loc[0, "amount"] = -5.0
    db_path = _make_db(tmp_path, df)
    with pytest.raises(ValueError, match="négatif"):
        validate(db_path)
