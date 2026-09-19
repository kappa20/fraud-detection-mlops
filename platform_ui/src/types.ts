// Shapes returned by the FastAPI service (see platform_api/schemas.py).

export const V_KEYS = Array.from({ length: 28 }, (_, i) => `v${i + 1}`);

export interface Transaction {
  id: number;
  time: number;
  amount: number;
  is_fraud: number;
  load_id: string | null;
  [key: string]: number | string | null;
}

/** Editable subset sent to the API (all optional for partial updates). */
export type TransactionFields = Partial<Record<"time" | "amount" | "is_fraud" | (typeof V_KEYS)[number], number>>;

/** A row to create: time, amount, label and the 28 PCA components, all numeric. */
export type NewTransactionValues = { time: number; amount: number; is_fraud: number } & Record<string, number>;
export type NewTransaction = NewTransactionValues & { tempId: number };

export interface TransactionPage {
  items: Transaction[];
  total: number;
  page: number;
  page_size: number;
  base_version: string;
}

export interface Stage {
  name: string;
  status: "pending" | "running" | "completed" | "failed";
  started_at?: string | null;
  ended_at?: string | null;
}

export type RunStatus = "versioned" | "pipeline_running" | "running" | "completed" | "failed";

export interface Run {
  timestamp: string;
  trigger: string;
  rows_added: number;
  dvc_md5: string | null;
  commit_sha: string | null;
  status: RunStatus;
  note: string | null;
  run_id: string | null;
  job_kind: string | null;
  user: string | null;
  stages: Stage[];
  log_tail: string | null;
}

export interface Status {
  pending_count: number;
  threshold: number;
  dataset_rows: number;
  last_run: Run | null;
}

export interface Config {
  threshold: number;
  pending_count: number;
  auto_promote: boolean;
  auto_retrain_enabled: boolean;
  psi_threshold: number;
}

export interface DatasetVersion {
  commit_sha: string;
  timestamp: string;
  author: string;
  user: string | null;
  rows_changed: number | null;
  rows_total: number | null;
  summary: string;
  kind: string | null;
}

export type PsiLevel = "green" | "orange" | "red";

export interface DriftFeature {
  psi: number;
  level: PsiLevel;
  interpretation: string;
}

export interface DriftSummary {
  mode: "halves" | "new_data";
  reference_rows: number;
  recent_rows: number;
  max_psi: number;
  psi_threshold: number;
  alert: boolean;
  features: Record<string, DriftFeature>;
}

export interface DriftHistoryPoint {
  timestamp: string;
  source: string;
  max_psi: number;
  psi: Record<string, number>;
}

export interface DistributionBucket {
  bucket: string;
  reference: number;
  recent: number;
}

export interface ModelInfo {
  version: number;
  stage: string;
  run_id: string;
  metrics: Record<"pr_auc" | "roc_auc" | "f1" | "precision" | "recall", number | null>;
}

export interface ModelComparison {
  candidate: ModelInfo | null;
  production: ModelInfo | null;
  delta: Record<string, number | null>;
}

export interface ServiceHealth {
  key: string;
  label: string;
  url: string;
  up: boolean;
  latency_ms: number | null;
}

export interface ChangeResult {
  rows_created: number;
  rows_updated: number;
  rows_deleted: number;
  commit_sha: string | null;
  dvc_md5: string | null;
  message: string;
}
