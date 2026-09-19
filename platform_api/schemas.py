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


class StageRecord(BaseModel):
    name: str
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    started_at: str | None = None
    ended_at: str | None = None


class RunRecord(BaseModel):
    timestamp: str
    trigger: Literal[
        "ingest", "simulate", "manual_pipeline", "manual_retrain", "drift_auto", "dashboard_edit", "rollback", "rerun"
    ]
    rows_added: int
    dvc_md5: str | None = None
    commit_sha: str | None = None
    status: Literal["versioned", "pipeline_running", "running", "completed", "failed"]
    note: str | None = None
    run_id: str | None = None
    job_kind: str | None = None
    user: str | None = None
    stages: list[StageRecord] = Field(default_factory=list)
    log_tail: str | None = None


class StatusResponse(BaseModel):
    pending_count: int
    threshold: int
    dataset_rows: int
    last_run: RunRecord | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str


class ConfigResponse(BaseModel):
    threshold: int
    pending_count: int
    auto_promote: bool
    auto_retrain_enabled: bool
    psi_threshold: float


class ConfigUpdate(BaseModel):
    threshold: int | None = Field(None, gt=0)
    auto_promote: bool | None = None
    auto_retrain_enabled: bool | None = None
    psi_threshold: float | None = Field(None, gt=0, le=5)


class TransactionFields(BaseModel):
    """Champs modifiables d'une transaction (tous optionnels pour une mise à jour partielle)."""

    time: float | None = Field(None, ge=0)
    amount: float | None = Field(None, ge=0)
    is_fraud: int | None = Field(None, ge=0, le=1)
    v1: float | None = None
    v2: float | None = None
    v3: float | None = None
    v4: float | None = None
    v5: float | None = None
    v6: float | None = None
    v7: float | None = None
    v8: float | None = None
    v9: float | None = None
    v10: float | None = None
    v11: float | None = None
    v12: float | None = None
    v13: float | None = None
    v14: float | None = None
    v15: float | None = None
    v16: float | None = None
    v17: float | None = None
    v18: float | None = None
    v19: float | None = None
    v20: float | None = None
    v21: float | None = None
    v22: float | None = None
    v23: float | None = None
    v24: float | None = None
    v25: float | None = None
    v26: float | None = None
    v27: float | None = None
    v28: float | None = None


class TransactionUpdate(BaseModel):
    id: int = Field(..., ge=0, description="Position (0-based) de la ligne dans le dataset")
    fields: TransactionFields


class ChangeBatch(BaseModel):
    base_version: str = Field(..., description="Empreinte du dataset affiché par l'interface (verrou optimiste)")
    creates: list[BankTransactionInput] = Field(default_factory=list)
    updates: list[TransactionUpdate] = Field(default_factory=list)
    deletes: list[int] = Field(default_factory=list)


class ChangeResult(BaseModel):
    rows_created: int
    rows_updated: int
    rows_deleted: int
    commit_sha: str | None
    dvc_md5: str | None
    message: str


class PromotionDecision(BaseModel):
    version: int
