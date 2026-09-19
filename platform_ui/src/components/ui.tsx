import { ReactNode, useEffect } from "react";
import { STATUS_LABELS } from "../format";
import type { PsiLevel, Stage } from "../types";

export function Modal({
  title,
  onClose,
  children,
  footer,
  drawer = false,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  drawer?: boolean;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className={`overlay ${drawer ? "drawer-overlay" : ""}`} onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={drawer ? "drawer" : "modal"} role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-head">
          <h2>{title}</h2>
          <button className="close-x" onClick={onClose} aria-label="Fermer">
            ×
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  );
}

export function Panel({
  title,
  actions,
  children,
  flush = false,
}: {
  title: string;
  actions?: ReactNode;
  children: ReactNode;
  flush?: boolean;
}) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{title}</h2>
        {actions}
      </div>
      {flush ? children : <div className="panel-body">{children}</div>}
    </section>
  );
}

export function Switch({
  checked,
  onChange,
  children,
  disabled,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  children: ReactNode;
  disabled?: boolean;
}) {
  return (
    <label className="switch">
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      <span className="track" />
      <span>{children}</span>
    </label>
  );
}

export function StatusBadge({ status }: { status: string }) {
  return <span className={`badge badge-${status}`}>{STATUS_LABELS[status] ?? status}</span>;
}

const LEVEL_LABEL: Record<PsiLevel, string> = { green: "Stable", orange: "À surveiller", red: "Dérive" };
export function PsiBadge({ level }: { level: PsiLevel }) {
  return <span className={`badge badge-${level}`}>{LEVEL_LABEL[level]}</span>;
}

const STAGE_LABEL: Record<Stage["status"], string> = {
  pending: "en attente",
  running: "en cours",
  completed: "terminé",
  failed: "échec",
};
export function StageStepper({ stages }: { stages: Stage[] }) {
  if (!stages.length) return <div className="dim">Aucun détail d'étape pour cette entrée.</div>;
  return (
    <div className="stepper">
      {stages.map((stage) => (
        <div key={stage.name} className={`step ${stage.status}`} title={STAGE_LABEL[stage.status]}>
          <span className="dot" />
          {stage.name}
        </div>
      ))}
    </div>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null;
  return <div className="msg err">Erreur : {error instanceof Error ? error.message : String(error)}</div>;
}
