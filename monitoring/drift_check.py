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


def _reference_breakpoints(reference: pd.Series, buckets: int) -> np.ndarray | None:
    """Seuils de bucket = quantiles de la référence, bornes extérieures
    ouvertes (±inf) : sans cela, les valeurs récentes au-delà du min/max de
    la référence (typiquement des montants qui explosent) étaient ignorées
    par np.histogram et *sous-estimaient* justement la dérive la plus forte."""
    breakpoints = np.unique(reference.quantile(np.linspace(0, 1, buckets + 1)).values)
    if len(breakpoints) < 3:
        return None
    breakpoints[0], breakpoints[-1] = -np.inf, np.inf
    return breakpoints


def compute_psi(reference: pd.Series, current: pd.Series, buckets: int = 10) -> float:
    """Population Stability Index entre deux distributions, avec des
    seuils de bucket dérivés des quantiles de la distribution de référence."""
    breakpoints = _reference_breakpoints(reference, buckets)
    if breakpoints is None:
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


def psi_level(psi: float) -> str:
    """Niveau d'alerte du PSI, aligné sur `interpret_psi` : green / orange / red."""
    if psi < 0.10:
        return "green"
    if psi < 0.25:
        return "orange"
    return "red"


def _format_edge(value: float) -> str:
    return f"{value:.3g}"


def compare_distributions(reference: pd.Series, current: pd.Series, buckets: int = 10) -> list[dict]:
    """Part de chaque bucket (mêmes seuils que le PSI) dans la référence et
    dans les données récentes — de quoi tracer la comparaison de distributions."""
    breakpoints = _reference_breakpoints(reference, buckets)
    if breakpoints is None:
        return []
    ref_counts, _ = np.histogram(reference, bins=breakpoints)
    cur_counts, _ = np.histogram(current, bins=breakpoints)
    rows = []
    for i in range(len(breakpoints) - 1):
        low, high = breakpoints[i], breakpoints[i + 1]
        label = (
            f"< {_format_edge(high)}"
            if np.isinf(low)
            else f"≥ {_format_edge(low)}"
            if np.isinf(high)
            else f"{_format_edge(low)}–{_format_edge(high)}"
        )
        rows.append(
            {
                "bucket": label,
                "reference": float(ref_counts[i] / max(len(reference), 1)),
                "recent": float(cur_counts[i] / max(len(current), 1)),
            }
        )
    return rows


def with_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute log_amount / hour_of_day à partir de (time_seconds, amount) — même
    définition que dbt_fraud/models/marts/fct_transactions_features.sql."""
    out = df.copy()
    out["log_amount"] = np.log1p(out["amount"])
    out["hour_of_day"] = np.floor((out["time_seconds"] % 86400) / 3600.0)
    return out


def compute_drift(df: pd.DataFrame, new_data_after: float | None = None, min_recent: int = 100) -> dict:
    """PSI par colonne surveillée pour un DataFrame (time_seconds, amount).

    Par défaut (comme `main`) : référence = 1ère moitié temporelle, récent =
    2nde moitié. Si `new_data_after` est fourni et qu'au moins `min_recent`
    transactions le dépassent (temps), on compare plutôt tout l'historique
    d'origine aux *nouvelles* transactions : sur 285k lignes, quelques
    milliers de lignes dérivées seraient noyées dans la moitié entière, et une
    fenêtre "les N dernières" serait concentrée sur 1-2 heures, ce qui
    fausserait à coup sûr le PSI de hour_of_day."""
    df = with_derived_features(df).sort_values("time_seconds", kind="stable")
    mode = "halves"
    midpoint = df["time_seconds"].median()
    reference = df[df["time_seconds"] < midpoint]
    current = df[df["time_seconds"] >= midpoint]
    if new_data_after is not None:
        new_rows = df[df["time_seconds"] > new_data_after]
        if len(new_rows) >= min_recent:
            mode = "new_data"
            reference, current = df[df["time_seconds"] <= new_data_after], new_rows

    features = {}
    for col in MONITORED_COLUMNS:
        psi = compute_psi(reference[col], current[col])
        features[col] = {
            "psi": psi,
            "level": psi_level(psi),
            "interpretation": interpret_psi(psi),
            "distribution": compare_distributions(reference[col], current[col]),
        }
    return {
        "mode": mode,
        "reference_rows": int(len(reference)),
        "recent_rows": int(len(current)),
        "max_psi": max(f["psi"] for f in features.values()),
        "features": features,
    }


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
