"""Génération de transactions synthétiques (bouton "Générer" de la
plateforme), pour simuler l'arrivée de nouvelles données bancaires sans
attendre du vrai trafic — et démontrer la détection de dérive en
production (monitoring/drift_check.py).

Sans perturbation délibérée, des lignes ré-échantillonnées depuis le
dataset de référence auraient une distribution quasi identique et le PSI
resterait proche de 0 : la démonstration de dérive n'aurait aucun intérêt.
`drift_intensity` contrôle donc l'ampleur de la perturbation appliquée.
"""

import numpy as np
import pandas as pd

from platform_api import dataset

_REFERENCE_SAMPLE_SIZE = 5000

# Facteurs de perturbation par intensité de dérive choisie dans l'UI.
_DRIFT_PARAMS = {
    "none": {"amount_scale": 1.0, "fraud_rate_multiplier": 1.0, "v_shift": 0.0},
    "moderate": {"amount_scale": 1.8, "fraud_rate_multiplier": 3.0, "v_shift": 1.0},
    "strong": {"amount_scale": 3.5, "fraud_rate_multiplier": 8.0, "v_shift": 2.5},
}


def generate_synthetic_rows(n: int, drift_intensity: str, rng: np.random.Generator | None = None) -> list[dict]:
    rng = rng if rng is not None else np.random.default_rng()
    params = _DRIFT_PARAMS[drift_intensity]

    # Toujours échantillonner depuis les premières lignes du fichier
    # (dataset Kaggle d'origine), pas depuis les lignes déjà ajoutées par
    # la plateforme elle-même — sinon la "référence" dériverait avec le
    # temps et fausserait la comparaison PSI.
    reference = pd.read_csv(dataset.RAW_CSV_PATH, nrows=_REFERENCE_SAMPLE_SIZE)
    sample = reference.sample(n=n, replace=True, random_state=int(rng.integers(0, 2**31 - 1)))

    max_time = float(reference["Time"].max())
    base_fraud_rate = float(reference["Class"].mean())
    target_fraud_rate = min(base_fraud_rate * params["fraud_rate_multiplier"], 0.5)

    rows = []
    for _, base_row in sample.iterrows():
        row = {f"v{i}": float(base_row[f"V{i}"]) + rng.normal(0, params["v_shift"]) for i in range(1, 29)}
        row["time"] = max_time + float(rng.integers(1, 3600))
        row["amount"] = max(0.0, float(base_row["Amount"]) * params["amount_scale"] * rng.uniform(0.7, 1.3))
        row["is_fraud"] = int(rng.random() < target_fraud_rate)
        rows.append(row)
    return rows
