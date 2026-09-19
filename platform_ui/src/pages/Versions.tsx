import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, post } from "../api";
import { ErrorNote, Modal, Panel } from "../components/ui";
import { formatInt, formatTimestamp, shortHash, TRIGGER_LABELS } from "../format";
import { useToast } from "../toast";
import type { DatasetVersion } from "../types";

interface RollbackResult {
  commit_sha: string;
  dvc_md5: string | null;
  message: string;
}

export default function VersionsPage() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [target, setTarget] = useState<DatasetVersion | null>(null);

  const versions = useQuery({ queryKey: ["versions"], queryFn: () => api<DatasetVersion[]>("/versions?limit=100") });

  const rollback = useMutation({
    mutationFn: (sha: string) => post<RollbackResult>(`/versions/${sha}/rollback`),
    onSuccess: (result) => {
      toast("success", `Rollback effectué — commit ${shortHash(result.commit_sha)}`, result.message);
      setTarget(null);
      for (const key of ["versions", "transactions", "runs", "status", "drift"]) queryClient.invalidateQueries({ queryKey: [key] });
    },
  });

  const rows = versions.data ?? [];

  return (
    <>
      <div className="banner banner-info">
        <div>
          <strong>Une version = un commit git sur le pointeur DVC du dataset.</strong>
          Le rollback restaure le contenu d'une ancienne version sous la forme d'un <em>nouveau</em> commit : l'historique n'est jamais réécrit
          et rien n'est poussé vers GitHub.
        </div>
      </div>
      <Panel title="Versions du dataset" flush>
        <ErrorNote error={versions.error} />
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Commit</th>
                <th>Horodatage</th>
                <th>Auteur</th>
                <th>Type</th>
                <th className="num">Lignes modifiées</th>
                <th className="num">Total lignes</th>
                <th>Résumé</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((v, index) => (
                <tr key={v.commit_sha}>
                  <td className="mono" title={v.commit_sha}>
                    {shortHash(v.commit_sha)}
                  </td>
                  <td className="nowrap">{formatTimestamp(v.timestamp)}</td>
                  <td>
                    {v.user ? (
                      <>
                        {v.user} <span className="dim">via {v.author}</span>
                      </>
                    ) : (
                      v.author
                    )}
                  </td>
                  <td>{v.kind ? (TRIGGER_LABELS[v.kind] ?? v.kind) : "—"}</td>
                  <td className="num">{v.rows_changed == null ? "—" : formatInt(v.rows_changed)}</td>
                  <td className="num">{v.rows_total == null ? "—" : formatInt(v.rows_total)}</td>
                  <td style={{ maxWidth: 380 }}>{v.summary}</td>
                  <td className="right nowrap">
                    {index === 0 ? <span className="badge badge-blue">Version courante</span> : (
                      <button className="btn btn-secondary btn-small" onClick={() => (rollback.reset(), setTarget(v))}>
                        Revenir à cette version
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!versions.isLoading && rows.length === 0 && <div className="empty">Aucune version du dataset dans l'historique git.</div>}
        </div>
      </Panel>

      {target && (
        <Modal
          title="Confirmer le rollback"
          onClose={() => !rollback.isPending && setTarget(null)}
          footer={
            <>
              <button className="btn btn-secondary" onClick={() => setTarget(null)} disabled={rollback.isPending}>
                Annuler
              </button>
              <button className="btn btn-danger" onClick={() => rollback.mutate(target.commit_sha)} disabled={rollback.isPending}>
                {rollback.isPending ? "Restauration (dvc checkout)…" : "Restaurer cette version"}
              </button>
            </>
          }
        >
          <p style={{ marginTop: 0 }}>
            Le dataset sera restauré à l'état de la version <span className="mono">{shortHash(target.commit_sha)}</span> ({formatTimestamp(target.timestamp)}).
          </p>
          <p className="dim">
            Les lignes en attente non encore versionnées sont d'abord enregistrées dans une version dédiée : rien n'est perdu. Impossible si un job du
            pipeline est en cours.
          </p>
          <ErrorNote error={rollback.error} />
        </Modal>
      )}
    </>
  );
}
