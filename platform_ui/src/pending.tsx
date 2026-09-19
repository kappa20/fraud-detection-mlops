import { createContext, ReactNode, useCallback, useContext, useMemo, useState } from "react";
import type { NewTransaction, NewTransactionValues, Transaction, TransactionFields } from "./types";

/**
 * Corrections staged in the browser until "Enregistrer": nothing is sent to the
 * API (and nothing is versioned) before the user confirms the whole batch.
 * Kept in a context so a staged batch survives navigating between pages.
 */
interface PendingState {
  updates: Record<number, TransactionFields>;
  /** Snapshot of deleted rows so the confirmation list can show them after paging away. */
  deletes: Record<number, Pick<Transaction, "id" | "amount" | "time" | "is_fraud">>;
  creates: NewTransaction[];
  /** Dataset version the batch was started against (server-side optimistic lock). */
  baseVersion: string | null;
  beginBatch: (version: string) => void;
  stageUpdate: (id: number, fields: TransactionFields) => void;
  stageDelete: (rows: Pick<Transaction, "id" | "amount" | "time" | "is_fraud">[]) => void;
  unstageDelete: (id: number) => void;
  unstageUpdate: (id: number) => void;
  stageCreate: (row: NewTransactionValues) => void;
  unstageCreate: (tempId: number) => void;
  clear: () => void;
  count: number;
}

const PendingContext = createContext<PendingState | null>(null);

export function PendingProvider({ children }: { children: ReactNode }) {
  const [updates, setUpdates] = useState<PendingState["updates"]>({});
  const [deletes, setDeletes] = useState<PendingState["deletes"]>({});
  const [creates, setCreates] = useState<NewTransaction[]>([]);
  const [baseVersion, setBaseVersion] = useState<string | null>(null);

  // Row ids are positions: they are only trustworthy against the version seen when
  // the first change was staged, so later page refreshes must not move this.
  const beginBatch = useCallback((version: string) => setBaseVersion((current) => current ?? version), []);

  const stageUpdate = useCallback((id: number, fields: TransactionFields) => {
    setUpdates((current) => ({ ...current, [id]: { ...current[id], ...fields } }));
  }, []);
  const unstageUpdate = useCallback((id: number) => {
    setUpdates((current) => {
      const { [id]: _removed, ...rest } = current;
      return rest;
    });
  }, []);
  const stageDelete = useCallback((rows: PendingState["deletes"][number][]) => {
    setDeletes((current) => ({ ...current, ...Object.fromEntries(rows.map((r) => [r.id, r])) }));
  }, []);
  const unstageDelete = useCallback((id: number) => {
    setDeletes((current) => {
      const { [id]: _removed, ...rest } = current;
      return rest;
    });
  }, []);
  const stageCreate = useCallback((row: NewTransactionValues) => {
    setCreates((current) => [...current, { ...row, tempId: Date.now() + Math.random() }]);
  }, []);
  const unstageCreate = useCallback((tempId: number) => {
    setCreates((current) => current.filter((r) => r.tempId !== tempId));
  }, []);
  const clear = useCallback(() => {
    setUpdates({});
    setDeletes({});
    setCreates([]);
    setBaseVersion(null);
  }, []);

  const value = useMemo<PendingState>(
    () => ({
      updates,
      deletes,
      creates,
      baseVersion,
      beginBatch,
      stageUpdate,
      stageDelete,
      unstageDelete,
      unstageUpdate,
      stageCreate,
      unstageCreate,
      clear,
      // A row that is both edited and deleted only counts once, as a deletion.
      count: Object.keys(updates).filter((id) => !(id in deletes)).length + Object.keys(deletes).length + creates.length,
    }),
    [updates, deletes, creates, baseVersion, beginBatch, stageUpdate, stageDelete, unstageDelete, unstageUpdate, stageCreate, unstageCreate, clear],
  );

  return <PendingContext.Provider value={value}>{children}</PendingContext.Provider>;
}

export function usePending(): PendingState {
  const ctx = useContext(PendingContext);
  if (!ctx) throw new Error("usePending must be used inside PendingProvider");
  return ctx;
}
