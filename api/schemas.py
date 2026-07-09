"""Schémas Pydantic du service de scoring (Livrable 7).

Le payload reprend le schéma brut d'une transaction (time, v1-v28, amount)
tel qu'ingéré par le pipeline dlt (voir docs/data/data_contract.yaml) :
c'est au service, et non à l'appelant, de recalculer les features dérivées
(log_amount, hour_of_day) exactement comme le fait
dbt_fraud/models/marts/fct_transactions_features.sql à l'entraînement —
condition nécessaire pour éviter un écart entraînement/service
(training/serving skew). Voir api/model_loader.py::build_features.
"""

from pydantic import BaseModel, Field


class TransactionInput(BaseModel):
    time: float = Field(..., ge=0, description="Secondes depuis la première transaction du jeu de référence")
    v1: float
    v2: float
    v3: float
    v4: float
    v5: float
    v6: float
    v7: float
    v8: float
    v9: float
    v10: float
    v11: float
    v12: float
    v13: float
    v14: float
    v15: float
    v16: float
    v17: float
    v18: float
    v19: float
    v20: float
    v21: float
    v22: float
    v23: float
    v24: float
    v25: float
    v26: float
    v27: float
    v28: float
    amount: float = Field(..., ge=0, description="Montant de la transaction")

    model_config = {
        "json_schema_extra": {
            "example": {
                "time": 406,
                **{f"v{i}": 0.0 for i in range(1, 29)},
                "amount": 149.62,
            }
        }
    }


class PredictionOutput(BaseModel):
    fraud_probability: float = Field(..., ge=0, le=1, description="Probabilité de fraude estimée par le modèle")
    is_fraud: bool = Field(..., description="fraud_probability >= threshold")
    threshold: float = Field(..., description="Seuil de décision retenu (docs/ml/experiments_summary.md)")
    model_version: str = Field(..., description="Version du modèle dans le MLflow Model Registry")
