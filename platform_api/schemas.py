"""Schémas Pydantic de la plateforme d'ingestion continue.

Reprend le schéma brut d'une transaction (voir api/schemas.py) et y ajoute
le label `is_fraud`, fourni par la banque a posteriori (confirmation de
fraude ou non) : nécessaire pour ré-entraîner le modèle, contrairement à
api/schemas.py::TransactionInput qui sert uniquement à l'inférence (pas de
label disponible au moment de la prédiction).
"""

from typing import Literal

from pydantic import BaseModel, Field


class BankTransactionInput(BaseModel):
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
    is_fraud: int = Field(..., ge=0, le=1, description="0 = légitime, 1 = fraude confirmée par la banque")


class IngestRequest(BaseModel):
    transactions: list[BankTransactionInput] = Field(..., min_length=1)


class IngestResponse(BaseModel):
    rows_ingested: int
    pending_count: int
    threshold: int
    triggered: bool


class SimulateRequest(BaseModel):
    n: int = Field(..., gt=0, le=5000, description="Nombre de transactions synthétiques à générer")
    drift_intensity: Literal["none", "moderate", "strong"] = Field(
        "none",
        description="none = même distribution que le jeu d'entraînement (pas de dérive) ; "
        "moderate/strong = distributions perturbées (Amount, ratio de fraude, quelques Vn)",
    )


class ThresholdUpdate(BaseModel):
    threshold: int = Field(..., gt=0)


class ThresholdResponse(BaseModel):
    threshold: int
    pending_count: int


class RunRecord(BaseModel):
    timestamp: str
    trigger: Literal["ingest", "simulate"]
    rows_added: int
    dvc_md5: str | None = None
    commit_sha: str | None = None
    status: Literal["versioned", "pipeline_running", "completed", "failed"]
    note: str | None = None


class StatusResponse(BaseModel):
    pending_count: int
    threshold: int
    dataset_rows: int
    last_run: RunRecord | None = None
