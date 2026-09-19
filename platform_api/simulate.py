"""Génération de transactions synthétiques (bouton "Générer" de la
plateforme), pour simuler l'arrivée de nouvelles données bancaires sans
attendre du vrai trafic — et démontrer la détection de dérive en
production (monitoring/drift_check.py).

Sans perturbation délibérée, des lignes ré-échantillonnées depuis le
dataset de référence auraient une distribution quasi identique et le PSI
resterait proche de 0 : la démonstration de dérive n'aurait aucun intérêt.
`drift_intensity` contrôle donc l'ampleur de la perturbation appliquée.

Deux points qui faussaient la démonstration :
- l'échantillon de référence couvre tout le dataset d'origine (et pas ses
  5000 premières lignes, toutes situées dans la première heure : la
  distribution de hour_of_day aurait été fausse dès l'intensité "none") ;
- les nouvelles transactions reçoivent un `time` postérieur à la fin du
  dataset d'origine (comme de vraies transactions récentes), tout en
  conservant l'heure de la journée de la ligne échantillonnée. Avant, elles
  tombaient dans la fenêtre "référence" du calcul de dérive.
"""

import numpy as np

from platform_api import dataset, transactions

# Facteurs de perturbation par intensité de dérive choisie dans l'UI.
_DRIFT_PARAMS = {
    "none": {"amount_scale": 1.0, "fraud_rate_multiplier": 1.0, "v_shift": 0.0},
    "moderate": {"amount_scale": 1.8, "fraud_rate_multiplier": 3.0, "v_shift": 1.0},
    "strong": {"amount_scale": 3.5, "fraud_rate_multiplier": 8.0, "v_shift": 2.5},
}

_SECONDS_PER_DAY = 86400


def generate_synthetic_rows(n: int, drift_intensity: str, rng: np.random.Generator | None = None) -> list[dict]:
    rng = rng if rng is not None else np.random.default_rng()
    params = _DRIFT_PARAMS[drift_intensity]

    # Toujours échantillonner dans le dataset d'origine (id < BASELINE_ROWS),
    # pas dans les lignes déjà ajoutées par la plateforme elle-même — sinon la
    # "référence" dériverait avec le temps et fausserait la comparaison PSI.
    con = transactions._connection()
    reference = con.execute("SELECT * FROM tx WHERE id < ?", [dataset.BASELINE_ROWS]).fetchdf()
    sample = reference.sample(n=n, replace=True, random_state=int(rng.integers(0, 2**31 - 1)))

    base_fraud_rate = float(reference["is_fraud"].mean())
    target_fraud_rate = min(base_fraud_rate * params["fraud_rate_multiplier"], 0.5)
    first_new_day = np.ceil(dataset.BASELINE_MAX_TIME / _SECONDS_PER_DAY) * _SECONDS_PER_DAY

    rows = []
    for _, base_row in sample.iterrows():
        row = {f"v{i}": float(base_row[f"v{i}"]) + rng.normal(0, params["v_shift"]) for i in range(1, 29)}
        row["time"] = float(first_new_day + (float(base_row["time"]) % _SECONDS_PER_DAY))
        row["amount"] = max(0.0, float(base_row["amount"]) * params["amount_scale"] * rng.uniform(0.7, 1.3))
        row["is_fraud"] = int(rng.random() < target_fraud_rate)
        rows.append(row)
    return rows
