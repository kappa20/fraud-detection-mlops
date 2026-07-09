"""Génère une fixture synthétique (tests/fixtures/sample_transactions.csv)
utilisée par la CI/CD pour exercer le pipeline complet (dlt -> DuckDB ->
dbt -> ML) sans dépendre du fichier réel creditcard.csv (non versionné,
licence Kaggle — voir data/README.md).

Le schéma généré (colonnes, types) est strictement identique à celui du
dataset réel pour que le pipeline se comporte de façon identique en CI.

Usage :
    python scripts/make_sample_fixture.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = PROJECT_ROOT / "tests" / "fixtures" / "sample_transactions.csv"

N_ROWS = 500
FRAUD_RATIO = 0.05
SEED = 42


def main() -> None:
    rng = np.random.default_rng(SEED)

    n_fraud = int(N_ROWS * FRAUD_RATIO)
    is_fraud = np.array([0] * (N_ROWS - n_fraud) + [1] * n_fraud)
    rng.shuffle(is_fraud)

    data = {
        "Time": rng.integers(0, 172_792, size=N_ROWS),
        **{f"V{i}": rng.normal(0, 1, size=N_ROWS) for i in range(1, 29)},
        "Amount": np.round(rng.exponential(scale=80, size=N_ROWS), 2),
        "Class": is_fraud,
    }
    df = pd.DataFrame(data)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Fixture générée : {OUTPUT_PATH} ({len(df)} lignes, {int(is_fraud.sum())} fraudes)")


if __name__ == "__main__":
    main()
