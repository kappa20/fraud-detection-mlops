import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Fragment, useMemo, useState } from "react";
import { api, download } from "../api";
import { TransactionDrawer, NewTransactionModal } from "../components/TransactionForms";
import SaveModal from "../components/SaveModal";
import { ErrorNote, Panel } from "../components/ui";
import { formatAmount, formatDatasetTime, formatInt, shortHash, transactionLabel } from "../format";
import { usePending } from "../pending";
import { useToast } from "../toast";
import { Status, Transaction, TransactionPage, V_KEYS } from "../types";

interface Filters {
  amountMin: string;
  amountMax: string;
  fraud: "all" | "1" | "0";
  dayFrom: string;
  dayTo: string;
}
const NO_FILTERS: Filters = { amountMin: "", amountMax: "", fraud: "all", dayFrom: "", dayTo: "" };
const DAY = 86400;

const COLUMNS: { key: string; label: string; num?: boolean }[] = [
  { key: "id", label: "Transaction" },
  { key: "time", label: "Temps" },
  { key: "amount", label: "Montant", num: true },
  { key: "is_fraud", label: "Label" },
];

function buildQuery(filters: Filters, page: number, pageSize: number, sort: string, order: string): string {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize), sort, order });
  if (filters.amountMin !== "") params.set("amount_min", filters.amountMin);
  if (filters.amountMax !== "") params.set("amount_max", filters.amountMax);
  if (filters.fraud !== "all") params.set("is_fraud", filters.fraud);
  // The dataset has no calendar date: the range is expressed in "days since the first transaction".
  if (filters.dayFrom !== "") params.set("time_min", String((Number(filters.dayFrom) - 1) * DAY));
  if (filters.dayTo !== "") params.set("time_max", String(Number(filters.dayTo) * DAY - 1));
  return params.toString();
}

export default function TransactionsPage() {
  const pending = usePending();
  const toast = useToast();

  const [draft, setDraft] = useState<Filters>(NO_FILTERS);
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [sort, setSort] = useState("id");
  const [order, setOrder] = useState<"asc" | "desc">("asc");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [drawer, setDrawer] = useState<{ row: Transaction; mode: "view" | "edit" } | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [showSave, setShowSave] = useState(false);

  const query = buildQuery(filters, page, pageSize, sort, order);
  const list = useQuery({
    queryKey: ["transactions", query],
    queryFn: () => api<TransactionPage>(`/transactions?${query}`),
    placeholderData: keepPreviousData,
  });
  const status = useQuery({ queryKey: ["status"], queryFn: () => api<Status>("/status"), refetchInterval: 5000 });

  const rows = list.data?.items ?? [];
  const total = list.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const baseVersion = list.data?.base_version;

  // Staging always records the dataset version the row ids were read from.
  function withBatch<T extends unknown[]>(action: (...args: T) => void) {
    return (...args: T) => {
      if (baseVersion) pending.beginBatch(baseVersion);
      action(...args);
    };
  }
  const stageDelete = withBatch((deleted: Pick<Transaction, "id" | "amount" | "time" | "is_fraud">[]) => pending.stageDelete(deleted));
  const stageUpdate = withBatch(pending.stageUpdate);
  const stageCreate = withBatch(pending.stageCreate);

  function toggleSort(key: string) {
    if (sort === key) setOrder(order === "asc" ? "desc" : "asc");
    else {
      setSort(key);
      setOrder("asc");
    }
    setPage(1);
  }

  const toggle = (set: Set<number>, id: number) => {
    const next = new Set(set);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  };

  const allOnPageSelected = rows.length > 0 && rows.every((r) => selected.has(r.id));
  const kpis = useMemo(
    () => [
      { label: "Transactions", value: status.data ? formatInt(status.data.dataset_rows) : "—", sub: "dans le dataset versionné" },
      {
        label: "En attente du pipeline",
        value: status.data ? `${status.data.pending_count} / ${status.data.threshold}` : "—",
        sub: "lignes ajoutées depuis le dernier run",
      },
      { label: "Filtrées", value: formatInt(total), sub: "correspondent aux critères" },
      { label: "Corrections en attente", value: String(pending.count), sub: "non enregistrées" },
    ],
    [status.data, total, pending.count],
  );

  async function exportSelection() {
    try {
      await download(`/transactions/export?ids=${[...selected].sort((a, b) => a - b).join(",")}`, "transactions_selection.csv");
    } catch (e) {
      toast("error", "Export impossible", e instanceof Error ? e.message : String(e));
    }
  }

  function deleteSelected() {
    const byId = new Map(rows.map((r) => [r.id, r]));
    // Only rows currently loaded have their details; ids selected on other pages are kept as bare ids.
    stageDelete(
      [...selected].map((id) => {
        const r = byId.get(id);
        return { id, amount: r?.amount ?? NaN, time: r?.time ?? NaN, is_fraud: r?.is_fraud ?? 0 };
      }),
    );
    setSelected(new Set());
  }

  const first = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, total);

  return (
    <>
      <div className="kpis">
        {kpis.map((k) => (
          <div className="kpi" key={k.label}>
            <div className="kpi-label">{k.label}</div>
            <div className="kpi-value">{k.value}</div>
            <div className="kpi-sub">{k.sub}</div>
          </div>
        ))}
      </div>

      <Panel
        title="Filtres"
        actions={
          <div className="actions">
            <button className="btn btn-secondary btn-small" onClick={() => (setDraft(NO_FILTERS), setFilters(NO_FILTERS), setPage(1))}>
              Réinitialiser
            </button>
            <button className="btn btn-small" onClick={() => (setFilters(draft), setPage(1))}>
              Appliquer
            </button>
          </div>
        }
      >
        <form
          className="filters"
          onSubmit={(e) => {
            e.preventDefault();
            setFilters(draft);
            setPage(1);
          }}
        >
          <label className="field">
            <span>Montant min</span>
            <input type="number" min="0" step="any" value={draft.amountMin} onChange={(e) => setDraft({ ...draft, amountMin: e.target.value })} />
          </label>
          <label className="field">
            <span>Montant max</span>
            <input type="number" min="0" step="any" value={draft.amountMax} onChange={(e) => setDraft({ ...draft, amountMax: e.target.value })} />
          </label>
          <label className="field">
            <span>Label</span>
            <select value={draft.fraud} onChange={(e) => setDraft({ ...draft, fraud: e.target.value as Filters["fraud"] })}>
              <option value="all">Tous</option>
              <option value="1">Fraude</option>
              <option value="0">Légitime</option>
            </select>
          </label>
          <label className="field">
            <span>Du jour n° (J1 = début du jeu)</span>
            <input type="number" min="1" step="1" value={draft.dayFrom} onChange={(e) => setDraft({ ...draft, dayFrom: e.target.value })} />
          </label>
          <label className="field">
            <span>Au jour n°</span>
            <input type="number" min="1" step="1" value={draft.dayTo} onChange={(e) => setDraft({ ...draft, dayTo: e.target.value })} />
          </label>
          <button type="submit" hidden />
        </form>
      </Panel>

      {pending.creates.length > 0 && (
        <Panel title={`${pending.creates.length} transaction(s) à créer`} flush>
          <table className="data">
            <tbody>
              {pending.creates.map((row) => (
                <tr key={row.tempId} className="created">
                  <td>Nouvelle</td>
                  <td>{formatDatasetTime(row.time)}</td>
                  <td className="num">{formatAmount(row.amount)}</td>
                  <td>{row.is_fraud ? "Fraude" : "Légitime"}</td>
                  <td className="right">
                    <button className="btn-link" onClick={() => pending.unstageCreate(row.tempId)}>
                      Retirer
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}

      <Panel
        title="Transactions"
        flush
        actions={
          <div className="actions">
            {selected.size > 0 && (
              <>
                <span className="dim" style={{ alignSelf: "center" }}>
                  {selected.size} sélectionnée(s)
                </span>
                <button className="btn btn-secondary btn-small" onClick={exportSelection}>
                  Exporter en CSV
                </button>
                <button className="btn btn-danger-outline btn-small" onClick={deleteSelected}>
                  Supprimer
                </button>
                <button className="btn-link" onClick={() => setSelected(new Set())}>
                  Désélectionner
                </button>
              </>
            )}
            <button className="btn btn-small" onClick={() => setShowNew(true)}>
              + Nouvelle transaction
            </button>
          </div>
        }
      >
        <ErrorNote error={list.error} />
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th style={{ width: 30 }}>
                  <input
                    type="checkbox"
                    aria-label="Sélectionner la page"
                    checked={allOnPageSelected}
                    onChange={(e) => {
                      const next = new Set(selected);
                      rows.forEach((r) => (e.target.checked ? next.add(r.id) : next.delete(r.id)));
                      setSelected(next);
                    }}
                  />
                </th>
                <th style={{ width: 30 }} title="Afficher V1–V28" />
                {COLUMNS.map((c) => (
                  <th key={c.key} className={`sortable ${c.num ? "num" : ""}`} onClick={() => toggleSort(c.key)} aria-sort={sort === c.key ? (order === "asc" ? "ascending" : "descending") : "none"}>
                    {c.label} {sort === c.key ? (order === "asc" ? "▲" : "▼") : ""}
                  </th>
                ))}
                <th>Chargement</th>
                <th className="right">Actions</th>
              </tr>
            </thead>
            <tbody style={{ opacity: list.isPlaceholderData ? 0.55 : 1 }}>
              {rows.map((original) => {
                const edits = pending.updates[original.id];
                const row = { ...original, ...edits } as Transaction;
                const deleted = original.id in pending.deletes;
                const isExpanded = expanded.has(original.id);
                return (
                  <Fragment key={original.id}>
                    <tr className={`${deleted ? "deleted" : edits ? "edited" : ""} ${selected.has(original.id) ? "selected" : ""}`}>
                      <td>
                        <input type="checkbox" aria-label={`Sélectionner ${transactionLabel(original.id)}`} checked={selected.has(original.id)} onChange={() => setSelected(toggle(selected, original.id))} />
                      </td>
                      <td>
                        <button className="expander" aria-expanded={isExpanded} aria-label="Afficher V1–V28" onClick={() => setExpanded(toggle(expanded, original.id))}>
                          {isExpanded ? "▾" : "▸"}
                        </button>
                      </td>
                      <td className="mono nowrap">{transactionLabel(original.id)}</td>
                      <td className="nowrap">{formatDatasetTime(row.time)}</td>
                      <td className="num">{formatAmount(row.amount)}</td>
                      <td>{row.is_fraud ? <span className="badge badge-red">Fraude</span> : <span className="badge badge-green">Légitime</span>}</td>
                      <td className="mono" title={original.load_id ?? "pas encore ingérée"}>
                        {original.load_id ? shortHash(original.load_id) : "—"}
                      </td>
                      <td className="right nowrap actions-cell">
                        {deleted ? (
                          <button className="btn-link" onClick={() => pending.unstageDelete(original.id)}>
                            Annuler la suppression
                          </button>
                        ) : (
                          <>
                            <button className="btn btn-secondary btn-small" onClick={() => setDrawer({ row, mode: "view" })}>
                              Voir
                            </button>{" "}
                            <button className="btn btn-secondary btn-small" onClick={() => setDrawer({ row: original, mode: "edit" })}>
                              Modifier
                            </button>{" "}
                            <button className="btn btn-danger-outline btn-small" onClick={() => stageDelete([original])}>
                              Supprimer
                            </button>
                          </>
                        )}
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr className="subrow">
                        <td colSpan={8}>
                          <div className="v-grid">
                            {V_KEYS.map((k) => (
                              <span key={k}>
                                <b>{k.toUpperCase()}</b> {Number(original[k]).toFixed(5)}
                              </span>
                            ))}
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
          {!list.isLoading && rows.length === 0 && <div className="empty">Aucune transaction ne correspond aux filtres.</div>}
          {list.isLoading && <div className="empty">Chargement…</div>}
        </div>
        <div className="pager">
          <span className="dim">
            {formatInt(first)}–{formatInt(last)} sur {formatInt(total)}
          </span>
          <div className="actions">
            <label className="dim">
              Lignes par page{" "}
              <select style={{ width: "auto" }} value={pageSize} onChange={(e) => (setPageSize(Number(e.target.value)), setPage(1))}>
                {[25, 50, 100].map((n) => (
                  <option key={n}>{n}</option>
                ))}
              </select>
            </label>
            <button className="btn btn-secondary btn-small" disabled={page <= 1} onClick={() => setPage(1)}>
              «
            </button>
            <button className="btn btn-secondary btn-small" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              ‹
            </button>
            <span>
              Page {formatInt(page)} / {formatInt(pageCount)}
            </span>
            <button className="btn btn-secondary btn-small" disabled={page >= pageCount} onClick={() => setPage(page + 1)}>
              ›
            </button>
            <button className="btn btn-secondary btn-small" disabled={page >= pageCount} onClick={() => setPage(pageCount)}>
              »
            </button>
          </div>
        </div>
      </Panel>

      {pending.count > 0 && (
        <div className="pending-bar">
          <span>
            <strong>{pending.count}</strong> modification(s) en attente — {pending.creates.length} création(s),{" "}
            {Object.keys(pending.updates).filter((id) => !(id in pending.deletes)).length} mise(s) à jour, {Object.keys(pending.deletes).length} suppression(s)
          </span>
          <div className="actions">
            <button className="btn btn-secondary" onClick={pending.clear}>
              Tout annuler
            </button>
            <button className="btn" style={{ background: "#3f74e6", borderColor: "#3f74e6" }} onClick={() => setShowSave(true)}>
              Enregistrer…
            </button>
          </div>
        </div>
      )}

      {drawer && <TransactionDrawer row={drawer.row} initialMode={drawer.mode} onClose={() => setDrawer(null)} onStageUpdate={stageUpdate} onStageDelete={(r) => stageDelete([r])} />}
      {showNew && <NewTransactionModal onClose={() => setShowNew(false)} onAdd={stageCreate} />}
      {showSave && <SaveModal onClose={() => setShowSave(false)} />}
    </>
  );
}
