const nf0 = new Intl.NumberFormat("fr-FR");
const nf2 = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const formatInt = (n: number) => nf0.format(n);
export const formatAmount = (n: number) => nf2.format(n);
const fixed = (n: number, digits: number) => n.toLocaleString("fr-FR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
export const formatMetric = (n: number | null | undefined) => (n == null ? "—" : fixed(n, 4));
export const formatPsi = (n: number) => fixed(n, 3);
export const shortHash = (h: string | null | undefined) => (h ? h.slice(0, 8) : "—");

export function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString("fr-FR");
}

/** The dataset has no wall-clock date: `time` is seconds since the first transaction. */
export function formatDatasetTime(seconds: number): string {
  const day = Math.floor(seconds / 86400) + 1;
  const rest = Math.floor(seconds % 86400);
  const hh = String(Math.floor(rest / 3600)).padStart(2, "0");
  const mm = String(Math.floor((rest % 3600) / 60)).padStart(2, "0");
  const ss = String(rest % 60).padStart(2, "0");
  return `J${day} ${hh}:${mm}:${ss}`;
}

export const transactionLabel = (id: number) => `TX-${String(id).padStart(6, "0")}`;

export const TRIGGER_LABELS: Record<string, string> = {
  ingest: "Ingestion",
  simulate: "Simulation",
  manual_pipeline: "Pipeline manuel",
  manual_retrain: "Ré-entraînement manuel",
  drift_auto: "Dérive (auto)",
  dashboard_edit: "Correction manuelle",
  rollback: "Rollback",
  rerun: "Relance",
};

export const STATUS_LABELS: Record<string, string> = {
  versioned: "Versionné",
  pipeline_running: "En cours",
  running: "En cours",
  completed: "Terminé",
  failed: "Échec",
};
