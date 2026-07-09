"""Chargement du modèle exporté par ml/register_model.py (Livrable 6) et
recalcul des features dérivées pour le service d'inférence (Livrable 7).

Le service ne dépend volontairement pas d'un serveur MLflow vivant : il
charge le fichier `.pkl` exporté localement, ce qui simplifie la
conteneurisation Docker (Livrable 7) et évite un point de défaillance
supplémentaire en production.
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = PROJECT_ROOT / "ml" / "artifacts" / "model.pkl"
VERSION_PATH = PROJECT_ROOT / "ml" / "artifacts" / "model_version.txt"

# Doit rester synchronisé avec ml/prepare_data.py::FEATURE_COLUMNS.
FEATURE_ORDER = [f"v{i}" for i in range(1, 29)] + ["amount", "log_amount", "hour_of_day"]

# Seuil retenu pour rf_balanced_v1 (docs/ml/experiments_summary.md).
DEFAULT_THRESHOLD = 0.4998


class ModelNotLoadedError(RuntimeError):
    """Levée quand une prédiction est demandée avant chargement du modèle."""


class FraudModel:
    def __init__(self, model_path: Path = MODEL_PATH, threshold: float = DEFAULT_THRESHOLD):
        self._model_path = model_path
        self.threshold = threshold
        self._model = None

    def load(self) -> None:
        if not self._model_path.exists():
            raise ModelNotLoadedError(
                f"Modèle introuvable : {self._model_path}. "
                "Lancer 'python ml/train.py' puis 'python ml/register_model.py'."
            )
        self._model = joblib.load(self._model_path)

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @staticmethod
    def build_features(transaction: dict) -> pd.DataFrame:
        """Reproduit exactement dbt_fraud/models/marts/fct_transactions_features.sql :
        hour_of_day = floor((time % 86400) / 3600), log_amount = ln(amount + 1).
        """
        hour_of_day = int((transaction["time"] % 86400) // 3600)
        log_amount = float(np.log1p(transaction["amount"]))

        row = {f"v{i}": transaction[f"v{i}"] for i in range(1, 29)}
        row["amount"] = transaction["amount"]
        row["log_amount"] = log_amount
        row["hour_of_day"] = hour_of_day
        return pd.DataFrame([row], columns=FEATURE_ORDER)

    def predict_proba(self, transaction: dict) -> float:
        if self._model is None:
            raise ModelNotLoadedError("Modèle non chargé. Appeler .load() d'abord.")
        X = self.build_features(transaction)
        return float(self._model.predict_proba(X)[0, 1])


def get_model_version() -> str:
    if VERSION_PATH.exists():
        return VERSION_PATH.read_text().strip()
    return "unknown"
