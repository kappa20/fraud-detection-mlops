import { useState } from "react";
import { formatAmount, formatDatasetTime, transactionLabel } from "../format";
import { NewTransactionValues, Transaction, TransactionFields, V_KEYS } from "../types";
import { Modal } from "./ui";

type FormValues = Record<string, string>;

const toForm = (row: Partial<Transaction>): FormValues => ({
  time: String(row.time ?? 0),
  amount: String(row.amount ?? 0),
  is_fraud: String(row.is_fraud ?? 0),
  ...Object.fromEntries(V_KEYS.map((k) => [k, String(row[k] ?? 0)])),
});

/** Returns the parsed numeric fields, or an error message for the first invalid one. */
function parseForm(values: FormValues): { fields: Record<string, number> } | { error: string } {
  const fields: Record<string, number> = {};
  for (const key of ["time", "amount", "is_fraud", ...V_KEYS]) {
    const n = Number(values[key]);
    if (values[key] === "" || !Number.isFinite(n)) return { error: `Valeur numérique invalide pour « ${key} ».` };
    fields[key] = n;
  }
  if (fields.time < 0) return { error: "Le temps ne peut pas être négatif." };
  if (fields.amount < 0) return { error: "Le montant ne peut pas être négatif." };
  if (fields.is_fraud !== 0 && fields.is_fraud !== 1) return { error: "Le label doit valoir 0 (légitime) ou 1 (fraude)." };
  return { fields };
}

function FieldsEditor({ values, onChange }: { values: FormValues; onChange: (key: string, value: string) => void }) {
  return (
    <>
      <div className="drawer-grid">
        <label className="field">
          <span>Temps (secondes depuis le début du jeu)</span>
          <input type="number" step="any" min="0" value={values.time} onChange={(e) => onChange("time", e.target.value)} />
        </label>
        <label className="field">
          <span>Montant</span>
          <input type="number" step="any" min="0" value={values.amount} onChange={(e) => onChange("amount", e.target.value)} />
        </label>
        <label className="field">
          <span>Label</span>
          <select value={values.is_fraud} onChange={(e) => onChange("is_fraud", e.target.value)}>
            <option value="0">Légitime</option>
            <option value="1">Fraude</option>
          </select>
        </label>
      </div>
      <details>
        <summary>Composantes PCA anonymisées (V1–V28)</summary>
        <div className="drawer-grid" style={{ marginTop: 10 }}>
          {V_KEYS.map((key) => (
            <label className="field" key={key}>
              <span>{key.toUpperCase()}</span>
              <input type="number" step="any" value={values[key]} onChange={(e) => onChange(key, e.target.value)} />
            </label>
          ))}
        </div>
      </details>
    </>
  );
}

export function TransactionDrawer({
  row,
  initialMode,
  onClose,
  onStageUpdate,
  onStageDelete,
}: {
  row: Transaction;
  initialMode: "view" | "edit";
  onClose: () => void;
  onStageUpdate: (id: number, fields: TransactionFields) => void;
  onStageDelete: (row: Transaction) => void;
}) {
  const [mode, setMode] = useState(initialMode);
  const [values, setValues] = useState<FormValues>(toForm(row));
  const [error, setError] = useState<string | null>(null);

  function stage() {
    const parsed = parseForm(values);
    if ("error" in parsed) return setError(parsed.error);
    // Send only what actually changed, so the commit message counts real edits.
    const changed = Object.fromEntries(Object.entries(parsed.fields).filter(([key, value]) => value !== Number(row[key])));
    if (Object.keys(changed).length === 0) return setError("Aucune modification par rapport à la valeur actuelle.");
    onStageUpdate(row.id, changed as TransactionFields);
    onClose();
  }

  return (
    <Modal
      drawer
      title={`${transactionLabel(row.id)} — ${mode === "edit" ? "Modifier" : "Détail"}`}
      onClose={onClose}
      footer={
        mode === "view" ? (
          <>
            <button className="btn btn-danger-outline" onClick={() => (onStageDelete(row), onClose())}>
              Supprimer
            </button>
            <button className="btn" onClick={() => setMode("edit")}>
              Modifier
            </button>
          </>
        ) : (
          <>
            <button className="btn btn-secondary" onClick={() => setMode("view")}>
              Annuler
            </button>
            <button className="btn" onClick={stage}>
              Mettre en attente
            </button>
          </>
        )
      }
    >
      {mode === "view" ? (
        <>
          <dl className="kv">
            <dt>Identifiant</dt>
            <dd className="mono">{transactionLabel(row.id)} (ligne {row.id})</dd>
            <dt>Temps</dt>
            <dd>
              {formatDatasetTime(row.time)} <span className="dim">({row.time} s)</span>
            </dd>
            <dt>Montant</dt>
            <dd>{formatAmount(row.amount)}</dd>
            <dt>Label</dt>
            <dd>{row.is_fraud ? <span className="badge badge-red">Fraude</span> : <span className="badge badge-green">Légitime</span>}</dd>
            <dt>Chargement dlt</dt>
            <dd className="mono">{row.load_id ?? "— (pas encore ingérée)"}</dd>
          </dl>
          <h3 style={{ fontSize: 13, marginBottom: 8 }}>Composantes PCA anonymisées</h3>
          <div className="v-grid">
            {V_KEYS.map((key) => (
              <span key={key}>
                <b>{key.toUpperCase()}</b> {Number(row[key]).toFixed(6)}
              </span>
            ))}
          </div>
        </>
      ) : (
        <>
          <FieldsEditor values={values} onChange={(key, value) => setValues((v) => ({ ...v, [key]: value }))} />
          {error && <div className="msg err">{error}</div>}
          <div className="msg dim">La modification n'est envoyée qu'à « Enregistrer » (un commit DVC pour tout le lot).</div>
        </>
      )}
    </Modal>
  );
}

export function NewTransactionModal({
  onClose,
  onAdd,
}: {
  onClose: () => void;
  onAdd: (row: NewTransactionValues) => void;
}) {
  const [values, setValues] = useState<FormValues>(toForm({ time: 0, amount: 0, is_fraud: 0 }));
  const [error, setError] = useState<string | null>(null);

  function add() {
    const parsed = parseForm(values);
    if ("error" in parsed) return setError(parsed.error);
    onAdd(parsed.fields as NewTransactionValues);
    onClose();
  }

  return (
    <Modal
      title="Nouvelle transaction"
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-secondary" onClick={onClose}>
            Annuler
          </button>
          <button className="btn" onClick={add}>
            Ajouter au lot
          </button>
        </>
      }
    >
      <p className="dim" style={{ marginTop: 0 }}>
        Ajout manuel (test ou correction). La ligne est créée à « Enregistrer », avec les autres modifications du lot.
      </p>
      <FieldsEditor values={values} onChange={(key, value) => setValues((v) => ({ ...v, [key]: value }))} />
      {error && <div className="msg err">{error}</div>}
    </Modal>
  );
}
