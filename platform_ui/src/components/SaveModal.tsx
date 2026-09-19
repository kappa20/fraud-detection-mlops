import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, post } from "../api";
import { formatAmount, shortHash, transactionLabel } from "../format";
import { usePending } from "../pending";
import { useToast } from "../toast";
import type { ChangeResult } from "../types";
import { ErrorNote, Modal } from "./ui";

export default function SaveModal({ onClose }: { onClose: () => void }) {
  const pending = usePending();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const deletedIds = Object.keys(pending.deletes).map(Number);
  const updatedIds = Object.keys(pending.updates).map(Number).filter((id) => !deletedIds.includes(id));

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const result = await post<ChangeResult>("/transactions/changes", {
        base_version: pending.baseVersion,
        creates: pending.creates.map(({ tempId: _tempId, ...row }) => row),
        updates: updatedIds.map((id) => ({ id, fields: pending.updates[id] })),
        deletes: deletedIds,
      });
      toast(
        "success",
        `Version DVC créée — commit ${shortHash(result.commit_sha)}`,
        `${result.rows_created} créée(s), ${result.rows_updated} modifiée(s), ${result.rows_deleted} supprimée(s). Consignée dans l'historique des runs.`,
      );
      pending.clear();
      for (const key of ["transactions", "versions", "runs", "status", "drift"]) {
        queryClient.invalidateQueries({ queryKey: [key] });
      }
      onClose();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        // Positions may have shifted: keeping the staged batch would edit the wrong rows.
        pending.clear();
        queryClient.invalidateQueries({ queryKey: ["transactions"] });
        toast("error", "Lot abandonné", `${e.message} Vos modifications en attente ont été annulées pour éviter d'éditer de mauvaises lignes.`);
        onClose();
      } else {
        setError(e);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title="Enregistrer les modifications"
      onClose={busy ? () => {} : onClose}
      footer={
        <>
          <button className="btn btn-secondary" onClick={onClose} disabled={busy}>
            Retour
          </button>
          <button className={`btn ${deletedIds.length ? "btn-danger" : ""}`} onClick={save} disabled={busy}>
            {busy ? "Versionnement en cours (dvc add + push + commit)…" : "Enregistrer et versionner"}
          </button>
        </>
      }
    >
      <p style={{ marginTop: 0 }}>
        Ce lot sera appliqué au dataset, puis versionné avec <strong>dvc add</strong> et un <strong>commit git</strong>. Le hash du commit sera
        affiché et journalisé.
      </p>
      <dl className="kv">
        <dt>Créations</dt>
        <dd>{pending.creates.length}</dd>
        <dt>Modifications</dt>
        <dd>{updatedIds.length}</dd>
        <dt>Suppressions</dt>
        <dd>{deletedIds.length}</dd>
      </dl>

      {deletedIds.length > 0 && (
        <>
          <h3 style={{ fontSize: 13, marginBottom: 6, color: "var(--red)" }}>
            {deletedIds.length} ligne{deletedIds.length > 1 ? "s" : ""} en attente de suppression
          </h3>
          <div className="list-scroll">
            <table className="data">
              <tbody>
                {Object.values(pending.deletes).map((row) => (
                  <tr key={row.id}>
                    <td className="mono">{transactionLabel(row.id)}</td>
                    <td className="num">{Number.isNaN(row.amount) ? "—" : formatAmount(row.amount)}</td>
                    <td>{Number.isNaN(row.amount) ? "" : row.is_fraud ? "Fraude" : "Légitime"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="dim" style={{ fontSize: 12.5 }}>
            La suppression est réversible : chaque version est conservée et restaurable depuis « Versions du dataset ».
          </p>
        </>
      )}
      <ErrorNote error={error} />
    </Modal>
  );
}
