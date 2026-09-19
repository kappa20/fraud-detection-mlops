import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { ErrorNote, Panel } from "../components/ui";
import type { ServiceHealth } from "../types";

const DESCRIPTIONS: Record<string, string> = {
  mlflow: "Suivi des expériences et Model Registry",
  grafana: "Tableaux de bord de supervision de l'API",
  prometheus: "Métriques du service de scoring",
  scoring: "Documentation Swagger de l'API de scoring",
  minio: "Stockage objet du remote DVC",
};

function Dot({ state }: { state: "up" | "down" | "loading" }) {
  const label = state === "up" ? "Service disponible" : state === "down" ? "Service injoignable" : "Vérification…";
  return <span className={`status-dot ${state}`} role="img" aria-label={label} title={label} />;
}

export default function EcosystemPage() {
  const health = useQuery({
    queryKey: ["services"],
    queryFn: () => api<ServiceHealth[]>("/services/health"),
    refetchInterval: 30_000,
  });

  return (
    <Panel
      title="Écosystème"
      actions={
        <button className="btn btn-secondary btn-small" onClick={() => health.refetch()} disabled={health.isFetching}>
          {health.isFetching ? "Vérification…" : "Vérifier maintenant"}
        </button>
      }
    >
      <ErrorNote error={health.error} />
      <div className="eco-grid">
        {(health.data ?? []).map((service) => (
          <a key={service.key} className="eco-card" href={service.url} target="_blank" rel="noreferrer">
            <h3>
              <Dot state={service.up ? "up" : "down"} />
              {service.label}
            </h3>
            <div className="dim" style={{ margin: "6px 0 8px" }}>
              {DESCRIPTIONS[service.key]}
            </div>
            <div className="mono dim">
              {service.up ? `disponible${service.latency_ms != null ? ` · ${service.latency_ms} ms` : ""}` : "injoignable depuis le serveur"}
            </div>
          </a>
        ))}
        <a className="eco-card" href="/docs" target="_blank" rel="noreferrer">
          <h3>
            <Dot state="up" />
            API de la plateforme (Swagger)
          </h3>
          <div className="dim" style={{ margin: "6px 0 8px" }}>
            Cette application — endpoints documentés
          </div>
          <div className="mono dim">/docs</div>
        </a>
        {health.isLoading &&
          ["MLflow Registry", "Grafana", "Prometheus", "API de scoring"].map((label) => (
            <div className="eco-card" key={label}>
              <h3>
                <Dot state="loading" />
                {label}
              </h3>
            </div>
          ))}
      </div>
      <p className="dim" style={{ marginBottom: 0 }}>
        Les vérifications partent du serveur de la plateforme (réseau interne Docker), actualisées toutes les 30 secondes.
      </p>
    </Panel>
  );
}
