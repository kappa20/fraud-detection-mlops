"""Détection de dérive simple (Livrable 9) via le Population Stability
Index (PSI), calculé "à la main" plutôt qu'avec une librairie dédiée
(Evidently, etc.) pour rester dans le scope du module sans ajouter une
dépendance lourde supplémentaire.

Faute de trafic de production réel à ce stade du projet, la comparaison
se fait en coupant le dataset en deux fenêtres temporelles
(time_seconds) : la première moitié sert de référence ("entraînement"),
la seconde de "récent" — ce qui permet de démontrer la technique sur des
données réelles. Si des prédictions ont déjà été journalisées par l'API
(monitoring/predictions_log.jsonl), leur distribution de `amount` est
comparée en complément.

Grille de lecture usuelle du PSI :
    PSI < 0.10        : pas de dérive significative
    0.10 <= PSI < 0.25 : dérive modérée, à surveiller
    PSI >= 0.25        : dérive significative, ré-entraînement à envisager

Usage :
    python monitoring/drift_check.py
"""

import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = PROJECT_ROOT / "fraud_detection.duckdb"
PREDICTIONS_LOG = Path(__file__).resolve().parent / "predictions_log.jsonl"
REPORT_PATH = Path(__file__).resolve().parent / "drift_report.md"

MONITORED_COLUMNS = ["amount", "log_amount", "hour_of_day"]


def compute_psi(reference: pd.Series, current: pd.Series, buckets: int = 10) -> float:
    """Population Stability Index entre deux distributions, avec des
    seuils de bucket dérivés des quantiles de la distribution de référence."""
    quantiles = np.linspace(0, 1, buckets + 1)
    breakpoints = np.unique(reference.quantile(quantiles).values)
    if len(breakpoints) < 3:
        return 0.0  # distribution trop peu variée pour être découpée utilement

    ref_counts, _ = np.histogram(reference, bins=breakpoints)
    cur_counts, _ = np.histogram(current, bins=breakpoints)

    ref_pct = np.clip(ref_counts / max(len(reference), 1), 1e-6, None)
    cur_pct = np.clip(cur_counts / max(len(current), 1), 1e-6, None)

    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


def interpret_psi(psi: float) -> str:
    if psi < 0.10:
        return "pas de dérive significative"
    if psi < 0.25:
        return "dérive modérée — à surveiller"
    return "dérive significative — ré-entraînement à envisager"


def load_reference_and_current(db_path: str = str(DEFAULT_DB)) -> tuple[pd.DataFrame, pd.DataFrame]:
    con = duckdb.connect(db_path, read_only=True)
    try:
        df = con.execute(
            "SELECT amount, log_amount, hour_of_day, time_seconds "
            "FROM main.fct_transactions_features ORDER BY time_seconds"
        ).fetchdf()
    finally:
        con.close()
    midpoint = df["time_seconds"].median()
    reference = df[df["time_seconds"] < midpoint]
    current = df[df["time_seconds"] >= midpoint]
    return reference, current


def load_predictions_amount() -> pd.Series | None:
    if not PREDICTIONS_LOG.exists():
        return None
    records = [json.loads(line) for line in PREDICTIONS_LOG.read_text().splitlines() if line.strip()]
    if not records:
        return None
    return pd.DataFrame(records)["amount"]


def main() -> None:
    reference, current = load_reference_and_current()

    lines = [
        "# Rapport de dérive (Livrable 9)",
        "",
        f"Référence : {len(reference)} transactions (1ère moitié temporelle) "
        f"— Récent : {len(current)} transactions (2nde moitié temporelle).",
        "",
        "| Colonne | PSI | Interprétation |",
        "|---|---|---|",
    ]
    print(f"{'Colonne':<15} {'PSI':>8}  Interprétation")
    for col in MONITORED_COLUMNS:
        psi = compute_psi(reference[col], current[col])
        verdict = interpret_psi(psi)
        print(f"{col:<15} {psi:>8.4f}  {verdict}")
        lines.append(f"| {col} | {psi:.4f} | {verdict} |")

    live_amount = load_predictions_amount()
    if live_amount is not None:
        psi = compute_psi(reference["amount"], live_amount)
        verdict = interpret_psi(psi)
        print(f"\n{'amount (API live)':<15} {psi:>8.4f}  {verdict}  (n={len(live_amount)})")
        lines += [
            "",
            f"Comparaison avec {len(live_amount)} prédictions réelles journalisées par l'API "
            f"(`monitoring/predictions_log.jsonl`) :",
            "",
            "| Colonne | PSI | Interprétation |",
            "|---|---|---|",
            f"| amount (trafic API) | {psi:.4f} | {verdict} |",
        ]
    else:
        lines += [
            "",
            "Aucune prédiction journalisée par l'API à ce jour "
            "(`monitoring/predictions_log.jsonl` absent ou vide) — "
            "comparaison limitée aux deux fenêtres temporelles du dataset d'entraînement.",
        ]

    REPORT_PATH.write_text("\n".join(lines) + "\n")
    print(f"\nRapport écrit : {REPORT_PATH}")


if __name__ == "__main__":
    main()
