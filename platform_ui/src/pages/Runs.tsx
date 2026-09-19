import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Fragment, useState } from "react";
import { api, post } from "../api";
import { ErrorNote, Panel, StageStepper, StatusBadge } from "../components/ui";
import { formatInt, formatTimestamp, shortHash, TRIGGER_LABELS } from "../format";
import { useToast } from "../toast";
import type { Run } from "../types";

const NOT_RERUNNABLE = new Set(["dashboard_edit", "rollback"]);

export function RunDetail({ run }: { run: Run }) {
  return (
    <div>
      <div className="dim" style={{ marginBottom: 6 }}>
        Étapes du pipeline{run.job_kind === "pipeline" ? " (ingestion → tests)" : run.job_kind === "continuous" ? " (ingestion → registry)" : ""}
      </div>
      {NOT_RERUNNABLE.has(run.trigger) ? (
        <div className="dim">Entrée de versionnement du dataset — aucune étape de pipeline.</div>
      ) : (
        <StageStepper stages={run.stages} />
      )}
      <dl className="kv" style={{ marginTop: 8 }}>
        <dt>Utilisateur</dt>
        <dd>{run.user ?? "—"}</dd>
        <dt>Commit dataset</dt>
        <dd className="mono">{run.commit_sha ?? "—"}</dd>
        <dt>Empreinte DVC (md5)</dt>
        <dd className="mono">{run.dvc_md5 ?? "—"}</dd>
        <dt>Note</dt>
        <dd style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{run.note ?? "—"}</dd>
      </dl>
      {run.log_tail ? <pre className="log">{run.log_tail}</pre> : <div className="dim">Pas de journal d'exécution conservé pour cette entrée.</div>}
    </div>
  );
}

export default function RunsPage() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [statusFilter, setStatusFilter] = useState("");
  const [open, setOpen] = useState<string | null>(null);

  const runs = useQuery({
    queryKey: ["runs", statusFilter],
    queryFn: () => api<Run[]>(`/runs?limit=100${statusFilter ? `&status=${statusFilter}` : ""}`),
    refetchInterval: 4000,
  });

  const rerun = useMutation({
    mutationFn: (runId: string) => post<{ run_id: string }>(`/runs/${runId}/rerun`),
    onSuccess: () => {
      toast("info", "Run relancé", "Le pipeline a redémarré ; suivez son avancement dans cette liste.");
      queryClient.invalidateQueries({ queryKey: ["runs"] });
    },
    onError: (e) => toast("error", "Relance impossible", e instanceof Error ? e.message : String(e)),
  });

  const rows = (runs.data ?? []).slice().reverse();

  return (
    <Panel
      title="Historique des runs"
      flush
      actions={
        <label className="dim">
          Statut{" "}
          <select style={{ width: "auto" }} value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">Tous</option>
            <option value="completed">Terminé</option>
            <option value="running">En cours</option>
            <option value="failed">Échec</option>
          </select>
        </label>
      }
    >
      <ErrorNote error={runs.error} />
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th />
              <th>Horodatage</th>
              <th>Déclencheur</th>
              <th className="num">Lignes</th>
              <th>Statut</th>
              <th>Dataset (.dvc)</th>
              <th>Commit</th>
              <th>Note</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((run) => {
              const id = run.run_id ?? run.timestamp;
              const isOpen = open === id;
              return (
                <Fragment key={id}>
                  <tr style={{ cursor: "pointer" }} onClick={() => setOpen(isOpen ? null : id)}>
                    <td>{isOpen ? "▾" : "▸"}</td>
                    <td className="nowrap">{formatTimestamp(run.timestamp)}</td>
                    <td>{TRIGGER_LABELS[run.trigger] ?? run.trigger}</td>
                    <td className="num">{formatInt(run.rows_added)}</td>
                    <td>
                      <StatusBadge status={run.status} />
                    </td>
                    <td className="mono dim">{shortHash(run.dvc_md5)}</td>
                    <td className="mono dim">{shortHash(run.commit_sha)}</td>
                    <td style={{ maxWidth: 340, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={run.note ?? ""}>
                      {run.note}
                    </td>
                    <td className="right">
                      {run.run_id && !NOT_RERUNNABLE.has(run.trigger) && (
                        <button
                          className="btn btn-secondary btn-small"
                          disabled={rerun.isPending || run.status === "running"}
                          onClick={(e) => (e.stopPropagation(), rerun.mutate(run.run_id!))}
                        >
                          Relancer
                        </button>
                      )}
                    </td>
                  </tr>
                  {isOpen && (
                    <tr className="subrow">
                      <td colSpan={9}>
                        <RunDetail run={run} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
        {!runs.isLoading && rows.length === 0 && <div className="empty">Aucun run pour ce filtre.</div>}
      </div>
    </Panel>
  );
}
