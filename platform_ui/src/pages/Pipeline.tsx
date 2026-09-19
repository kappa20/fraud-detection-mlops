import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { api, post, put } from "../api";
import { ErrorNote, Modal, Panel, StageStepper, StatusBadge, Switch } from "../components/ui";
import { formatInt, formatMetric, formatTimestamp, TRIGGER_LABELS } from "../format";
import { useToast } from "../toast";
import type { Config, ModelComparison, Run, Status } from "../types";

const METRICS: { key: "pr_auc" | "roc_auc" | "f1" | "precision" | "recall"; label: string }[] = [
  { key: "pr_auc", label: "PR-AUC" },
  { key: "roc_auc", label: "ROC-AUC" },
  { key: "f1", label: "F1" },
  { key: "precision", label: "Précision" },
  { key: "recall", label: "Rappel" },
];

interface RedeployResult {
  version: number;
  commit_sha: string | null;
  redeploy: { status: "requested" | "skipped" | "failed"; detail: string };
}

const isRunning = (run?: Run) => run?.status === "running" || run?.status === "pipeline_running";

export default function PipelinePage() {
  const queryClient = useQueryClient();
  const toast = useToast();

  const config = useQuery({ queryKey: ["config"], queryFn: () => api<Config>("/config") });
  const status = useQuery({ queryKey: ["status"], queryFn: () => api<Status>("/status"), refetchInterval: 4000 });
  const latest = useQuery({ queryKey: ["runs", "latest"], queryFn: () => api<Run[]>("/runs?limit=3"), refetchInterval: 2000 });
  const comparison = useQuery({ queryKey: ["models", "comparison"], queryFn: () => api<ModelComparison>("/models/comparison"), retry: false });

  const [threshold, setThreshold] = useState("");
  const [psi, setPsi] = useState("");
  const [simN, setSimN] = useState("500");
  const [simDrift, setSimDrift] = useState("strong");
  const [confirm, setConfirm] = useState<"approve" | "reject" | null>(null);
  const [deployResult, setDeployResult] = useState<RedeployResult | null>(null);

  useEffect(() => {
    if (config.data) {
      setThreshold(String(config.data.threshold));
      setPsi(String(config.data.psi_threshold));
    }
  }, [config.data]);

  const lastRun = (latest.data ?? []).filter((r) => r.job_kind).slice(-1)[0];
  const active = isRunning(lastRun);

  // When a job ends, the registry may have a new candidate: refresh the comparison once.
  const wasActive = useRef(false);
  useEffect(() => {
    if (wasActive.current && !active) {
      queryClient.invalidateQueries({ queryKey: ["models"] });
      queryClient.invalidateQueries({ queryKey: ["runs"] });
      queryClient.invalidateQueries({ queryKey: ["status"] });
      queryClient.invalidateQueries({ queryKey: ["drift"] });
    }
    wasActive.current = active;
  }, [active, queryClient]);

  const refreshAll = () => {
    for (const key of ["config", "status", "runs", "drift", "transactions"]) queryClient.invalidateQueries({ queryKey: [key] });
  };

  const saveConfig = useMutation({
    mutationFn: (patch: Partial<Config>) => put<Config>("/config", patch),
    onSuccess: (data) => {
      queryClient.setQueryData(["config"], data);
      refreshAll();
    },
    onError: (e) => toast("error", "Enregistrement impossible", e instanceof Error ? e.message : String(e)),
  });

  const simulate = useMutation({
    mutationFn: () => post<{ pending_count: number; threshold: number; triggered: boolean }>("/data/simulate", { n: Number(simN), drift_intensity: simDrift }),
    onSuccess: (r) => {
      toast(
        "success",
        `${simN} transactions ajoutées`,
        r.triggered ? "Seuil atteint : dataset versionné et pipeline déclenché." : `${r.pending_count}/${r.threshold} en attente.`,
      );
      refreshAll();
    },
  });

  const startJob = useMutation({
    mutationFn: (path: string) => post<{ run_id: string }>(path),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["runs"] });
      toast("info", "Job démarré");
    },
    onError: (e) => toast("error", "Lancement impossible", e instanceof Error ? e.message : String(e)),
  });

  const approve = useMutation({
    mutationFn: (version: number) => post<RedeployResult>("/models/approve", { version }),
    onSuccess: (result) => {
      setDeployResult(result);
      setConfirm(null);
      toast("success", `Modèle v${result.version} promu en Production`, `Redéploiement : ${result.redeploy.status}. ${result.redeploy.detail}`);
      queryClient.invalidateQueries({ queryKey: ["models"] });
      queryClient.invalidateQueries({ queryKey: ["runs"] });
    },
  });
  const reject = useMutation({
    mutationFn: (version: number) => post("/models/reject", { version }),
    onSuccess: () => {
      setConfirm(null);
      toast("info", "Candidat rejeté", "La version reste archivée dans le registry.");
      queryClient.invalidateQueries({ queryKey: ["models"] });
    },
  });

  const pct = status.data ? Math.min(100, Math.round((status.data.pending_count / status.data.threshold) * 100)) : 0;
  const cmp = comparison.data;
  const candidate = cmp?.candidate ?? null;

  return (
    <>
      <div className="grid-2">
        <Panel title="État du déclencheur">
          <div className="kpi-value">
            {status.data?.pending_count ?? "—"} <span className="dim" style={{ fontSize: 14, fontWeight: 400 }}>/ {status.data?.threshold ?? "—"} en attente</span>
          </div>
          <div className="progress">
            <div style={{ width: `${pct}%` }} />
          </div>
          <div className="dim" style={{ marginBottom: 14 }}>
            {status.data ? formatInt(status.data.dataset_rows) : "—"} transactions dans le dataset
          </div>
          <div className="row">
            <label className="field">
              <span>Seuil de déclenchement</span>
              <input type="number" min="1" value={threshold} onChange={(e) => setThreshold(e.target.value)} />
            </label>
            <div className="shrink" style={{ marginBottom: 10 }}>
              <button className="btn" onClick={() => saveConfig.mutate({ threshold: Number(threshold) })} disabled={saveConfig.isPending}>
                Enregistrer le seuil
              </button>
            </div>
          </div>
          <ErrorNote error={saveConfig.error} />
        </Panel>

        <Panel title="Simuler l'arrivée de données">
          <div className="row">
            <label className="field">
              <span>Nombre de transactions</span>
              <input type="number" min="1" max="5000" value={simN} onChange={(e) => setSimN(e.target.value)} />
            </label>
            <label className="field">
              <span>Intensité de dérive</span>
              <select value={simDrift} onChange={(e) => setSimDrift(e.target.value)}>
                <option value="none">Aucune (référence)</option>
                <option value="moderate">Modérée</option>
                <option value="strong">Forte</option>
              </select>
            </label>
          </div>
          <button className="btn" onClick={() => simulate.mutate()} disabled={simulate.isPending}>
            {simulate.isPending ? "Génération…" : "Générer"}
          </button>
          <p className="dim" style={{ fontSize: 12.5, marginBottom: 0 }}>
            Astuce : quelques milliers de lignes avec une dérive forte suffisent à faire passer le PSI au rouge.
          </p>
          <ErrorNote error={simulate.error} />
        </Panel>
      </div>

      <Panel title="Automatisation">
        <div className="grid-2">
          <div>
            <Switch checked={config.data?.auto_retrain_enabled ?? false} disabled={!config.data} onChange={(v) => saveConfig.mutate({ auto_retrain_enabled: v })}>
              Ré-entraînement automatique quand la dérive dépasse le seuil PSI
            </Switch>
            <div className="row">
              <label className="field">
                <span>Seuil PSI de ré-entraînement</span>
                <input type="number" step="0.01" min="0.01" value={psi} onChange={(e) => setPsi(e.target.value)} />
              </label>
              <div className="shrink" style={{ marginBottom: 10 }}>
                <button className="btn btn-secondary" onClick={() => saveConfig.mutate({ psi_threshold: Number(psi) })} disabled={saveConfig.isPending}>
                  Enregistrer
                </button>
              </div>
            </div>
            <Switch checked={config.data?.auto_promote ?? false} disabled={!config.data} onChange={(v) => saveConfig.mutate({ auto_promote: v })}>
              Promotion automatique (porte PR-AUC) — sinon approbation manuelle ci-dessous
            </Switch>
          </div>
          <div>
            <div className="actions">
              <button className="btn" onClick={() => startJob.mutate("/pipeline/run")} disabled={active || startJob.isPending}>
                Lancer le pipeline complet
              </button>
              <button className="btn" onClick={() => startJob.mutate("/pipeline/retrain")} disabled={active || startJob.isPending}>
                Ré-entraîner le modèle maintenant
              </button>
            </div>
            <p className="dim" style={{ fontSize: 12.5 }}>
              <strong>Pipeline complet</strong> : ingestion → validation → transformation → tests (Dagster). <strong>Ré-entraînement</strong> : pipeline complet
              puis entraînement, contrôle de dérive et enregistrement du candidat dans le registry.
            </p>
          </div>
        </div>
      </Panel>

      <Panel title="Dernier job" actions={lastRun && <StatusBadge status={lastRun.status} />}>
        {lastRun ? (
          <>
            <div className="dim" style={{ marginBottom: 6 }}>
              {TRIGGER_LABELS[lastRun.trigger] ?? lastRun.trigger} · {formatTimestamp(lastRun.timestamp)}
              {lastRun.user ? ` · ${lastRun.user}` : ""}
            </div>
            <StageStepper stages={lastRun.stages} />
            {lastRun.status === "failed" && <div className="msg err">{lastRun.note}</div>}
            {lastRun.log_tail && (
              <details open={active}>
                <summary>Journal d'exécution</summary>
                <pre className="log">{lastRun.log_tail}</pre>
              </details>
            )}
          </>
        ) : (
          <div className="empty">Aucun job pour l'instant.</div>
        )}
      </Panel>

      <Panel title="Modèle : Production et candidat">
        {comparison.isError && <ErrorNote error={comparison.error} />}
        {cmp && (
          <>
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th />
                    <th>Production actuelle</th>
                    <th>Candidat (Staging)</th>
                    <th className="num">Écart</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Version</td>
                    <td>{cmp.production ? `v${cmp.production.version}` : "—"}</td>
                    <td>{candidate ? `v${candidate.version}` : "aucun candidat en attente"}</td>
                    <td />
                  </tr>
                  {METRICS.map(({ key, label }) => {
                    const delta = cmp.delta[key];
                    return (
                      <tr key={key}>
                        <td>{label}</td>
                        <td>{formatMetric(cmp.production?.metrics[key])}</td>
                        <td>{formatMetric(candidate?.metrics[key])}</td>
                        <td className="num" style={{ color: delta == null ? undefined : delta >= 0 ? "var(--green)" : "var(--red)" }}>
                          {delta == null ? "—" : `${delta >= 0 ? "+" : ""}${delta.toFixed(4)}`}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {candidate ? (
              <div className="actions" style={{ marginTop: 14 }}>
                <button className="btn" onClick={() => (approve.reset(), setConfirm("approve"))}>
                  Enregistrer &amp; déployer…
                </button>
                <button className="btn btn-danger-outline" onClick={() => (reject.reset(), setConfirm("reject"))}>
                  Rejeter le candidat
                </button>
              </div>
            ) : (
              <p className="dim" style={{ marginBottom: 0 }}>
                Aucun candidat en attente. Lancez un ré-entraînement (promotion automatique désactivée) pour qu'un candidat apparaisse ici.
              </p>
            )}
          </>
        )}
        {deployResult && (
          <div className={`banner ${deployResult.redeploy.status === "requested" ? "banner-info" : "banner-orange"}`} style={{ marginTop: 14 }}>
            <div>
              <strong>
                v{deployResult.version} promu en Production — redéploiement {deployResult.redeploy.status === "requested" ? "demandé" : deployResult.redeploy.status === "skipped" ? "non effectué" : "en échec"}
              </strong>
              {deployResult.redeploy.detail}
              {deployResult.redeploy.status === "skipped" && " Le service de scoring continue de servir l'ancien modèle jusqu'à son redémarrage."}
            </div>
          </div>
        )}
      </Panel>

      {confirm && candidate && (
        <Modal
          title={confirm === "approve" ? "Promouvoir le candidat en Production" : "Rejeter le candidat"}
          onClose={() => setConfirm(null)}
          footer={
            <>
              <button className="btn btn-secondary" onClick={() => setConfirm(null)} disabled={approve.isPending || reject.isPending}>
                Annuler
              </button>
              {confirm === "approve" ? (
                <button className="btn" onClick={() => approve.mutate(candidate.version)} disabled={approve.isPending}>
                  {approve.isPending ? "Promotion et redéploiement…" : "Approuver et déployer"}
                </button>
              ) : (
                <button className="btn btn-danger" onClick={() => reject.mutate(candidate.version)} disabled={reject.isPending}>
                  Rejeter
                </button>
              )}
            </>
          }
        >
          <table className="data">
            <thead>
              <tr>
                <th />
                <th>Avant (v{cmp?.production?.version ?? "—"})</th>
                <th>Après (v{candidate.version})</th>
              </tr>
            </thead>
            <tbody>
              {METRICS.slice(0, 3).map(({ key, label }) => (
                <tr key={key}>
                  <td>{label}</td>
                  <td>{formatMetric(cmp?.production?.metrics[key])}</td>
                  <td>
                    <strong>{formatMetric(candidate.metrics[key])}</strong>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="dim">
            {confirm === "approve"
              ? "La version passe en Production dans le MLflow Registry, model.pkl est exporté, puis le service de scoring est redémarré pour charger le nouveau modèle."
              : "La version est archivée ; la Production actuelle reste inchangée."}
          </p>
          <ErrorNote error={approve.error ?? reject.error} />
        </Modal>
      )}
    </>
  );
}
