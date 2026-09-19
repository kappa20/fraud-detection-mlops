import { createContext, ReactNode, useCallback, useContext, useState } from "react";

type ToastKind = "success" | "error" | "info";
interface ToastItem {
  id: number;
  kind: ToastKind;
  title: string;
  detail?: string;
}

const ToastContext = createContext<(kind: ToastKind, title: string, detail?: string) => void>(() => {});
export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const push = useCallback((kind: ToastKind, title: string, detail?: string) => {
    const id = Date.now() + Math.random();
    setItems((current) => [...current, { id, kind, title, detail }]);
    window.setTimeout(() => setItems((current) => current.filter((t) => t.id !== id)), kind === "error" ? 9000 : 6000);
  }, []);

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toast-stack" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`toast toast-${t.kind}`}>
            <strong>{t.title}</strong>
            {t.detail && <div className="toast-detail">{t.detail}</div>}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
