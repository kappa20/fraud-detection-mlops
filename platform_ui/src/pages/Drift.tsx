import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, post } from "../api";
import { ErrorNote, Panel, PsiBadge } from "../components/ui";
import { formatInt, formatPsi } from "../format";
import { useToast } from "../toast";
import type { DistributionBucket, DriftHistoryPoint, DriftSummary } from "../types";

const FEATURE_LABELS: Record<string, string> = { amount: "Montant", log_amount: "Log du montant", hour_of_day: "Heure de la journée" };
const SERIES_COLORS: Record<string, string> = { amount: "#0a1f44", log_amount: "#3f74e6", hour_of_day: "#b7791f" };

export default function DriftPage() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const [feature, setFeature] = useState("amount");

  const current = useQuery({ queryKey: ["drift", "current"], queryFn: () => api<DriftSummary>("/drift/current"), refetchInterval: 15_000 });
  const history = useQuery({ queryKey: ["drift", "history"], queryFn: () => api<DriftHistoryPoint[]>("/drift/history?n=30"), refetchInterval: 15_000 });
  const distribution = useQuery({
    queryKey: ["drift", "distribution", feature],
    queryFn: () => api<DistributionBucket[]>(`/drift/distribution?feature=${feature}`),
  });

  const recompute = useMutation({
    mutationFn: () => post<DriftSummary>("/drift/check"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["drift"] }),
  });
  const retrain = useMutation({
    mutationFn: () => post<{ run_id: string }>("/pipeline/retrain"),
    onSuccess: () => {
      toast("info", "Ré-entraînement lancé", "Suivez l'avancement dans « Pipeline & automatisation ».");
      queryClient.invalidateQueries({ queryKey: ["runs"] });
      navigate("/pipeline");
    },
    onError: (e) => toast("error", "Lancement impossible", e instanceof Error ? e.message : String(e)),
  });

  const summary = current.data;
  const points = (history.data ?? []).map((p) => ({
    label: new Date(p.timestamp).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }),
    ...p.psi,
  }));
  const buckets = (distribution.data ?? []).map((b) => ({ ...b, reference: b.reference * 100, recent: b.recent * 100 }));

  return (
    <>
      {summary?.alert && (
        <div className="banner banner-red" role="alert">
          <div>
            <strong>Dérive significative détectée (PSI max {formatPsi(summary.max_psi)} ≥ seuil {summary.psi_threshold})</strong>
            Une ou plusieurs variables surveillées ont franchi le seuil rouge : le modèle en production risque d'être moins fiable.
          </div>
          <button className="btn btn-danger" onClick={() => retrain.mutate()} disabled={retrain.isPending}>
            {retrain.isPending ? "Lancement…" : "Ré-entraîner maintenant"}
          </button>
        </div>
      )}

      <Panel
        title="PSI courant par variable"
        actions={
          <button className="btn btn-secondary btn-small" onClick={() => recompute.mutate()} disabled={recompute.isPending}>
            Recalculer et consigner
          </button>
        }
      >
        <ErrorNote error={current.error ?? recompute.error} />
        <div className="psi-cards">
          {summary &&
            Object.entries(summary.features).map(([name, f]) => (
              <button key={name} className={`psi-card ${f.level} ${feature === name ? "selected" : ""}`} onClick={() => setFeature(name)} aria-pressed={feature === name}>
                <div className="dim">{FEATURE_LABELS[name] ?? name}</div>
                <div className="psi-value">{formatPsi(f.psi)}</div>
                <PsiBadge level={f.level} /> <span className="dim" style={{ fontSize: 12 }}>{f.interpretation}</span>
              </button>
            ))}
        </div>
        {summary && (
          <p className="dim" style={{ marginBottom: 0 }}>
            Référence : {formatInt(summary.reference_rows)} transactions —{" "}
            {summary.mode === "new_data"
              ? `données récentes : ${formatInt(summary.recent_rows)} nouvelles transactions (arrivées après le dataset d'origine).`
              : `pas assez de nouvelles données : comparaison des deux moitiés temporelles du dataset (${formatInt(summary.recent_rows)} lignes récentes).`}{" "}
            Seuils : vert &lt; 0,10 · orange 0,10–0,25 · rouge ≥ 0,25.
          </p>
        )}
      </Panel>

      <div className="grid-2">
        <Panel title="Évolution du PSI">
          <ErrorNote error={history.error} />
          {points.length < 2 ? (
            <div className="empty">
              {points.length === 0 ? "Aucun point d'historique." : "Un seul point pour l'instant."} Chaque changement du dataset (simulation, ingestion, correction) ajoute une mesure.
            </div>
          ) : (
            <div style={{ height: 300 }}>
              <ResponsiveContainer>
                <LineChart data={points} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
                  <CartesianGrid stroke="#e4e9f3" />
                  <XAxis dataKey="label" fontSize={11} />
                  <YAxis fontSize={11} />
                  <Tooltip formatter={(v: number) => v.toFixed(3)} />
                  <Legend />
                  <ReferenceLine y={0.1} stroke="#d9922a" strokeDasharray="4 4" label={{ value: "0,10", fontSize: 10, fill: "#93590a" }} />
                  <ReferenceLine y={0.25} stroke="#a61b2b" strokeDasharray="4 4" label={{ value: "0,25", fontSize: 10, fill: "#a61b2b" }} />
                  {Object.keys(SERIES_COLORS).map((key) => (
                    <Line key={key} type="monotone" dataKey={key} name={FEATURE_LABELS[key]} stroke={SERIES_COLORS[key]} strokeWidth={2} strokeDasharray={key === "log_amount" ? "6 3" : undefined} dot={{ r: 3 }} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
          <p className="dim" style={{ marginBottom: 0, fontSize: 12.5 }}>
            « Montant » et « Log du montant » se confondent : le logarithme est monotone, donc les mêmes classes et le même PSI.
          </p>
        </Panel>

        <Panel title={`Distribution — ${FEATURE_LABELS[feature] ?? feature}`}>
          <ErrorNote error={distribution.error} />
          <div style={{ height: 300 }}>
            <ResponsiveContainer>
              <BarChart data={buckets} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="#e4e9f3" vertical={false} />
                <XAxis dataKey="bucket" fontSize={10} interval={0} angle={-25} textAnchor="end" height={54} />
                <YAxis fontSize={11} unit=" %" />
                <Tooltip formatter={(v: number) => `${v.toFixed(1)} %`} />
                <Legend verticalAlign="top" />
                <Bar dataKey="reference" name="Référence" fill="#9db0d3" />
                <Bar dataKey="recent" name="Récent" fill="#0a1f44" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="dim" style={{ marginBottom: 0, fontSize: 12.5 }}>
            Part des transactions dans chaque classe (déciles de la référence). Cliquez sur une carte PSI pour changer de variable.
          </p>
        </Panel>
      </div>
    </>
  );
}
