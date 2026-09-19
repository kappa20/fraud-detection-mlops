import { useQuery } from "@tanstack/react-query";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./api";
import { useAuth } from "./auth";
import DriftPage from "./pages/Drift";
import EcosystemPage from "./pages/Ecosystem";
import LoginPage from "./pages/Login";
import PipelinePage from "./pages/Pipeline";
import RunsPage from "./pages/Runs";
import TransactionsPage from "./pages/Transactions";
import VersionsPage from "./pages/Versions";
import type { DriftSummary } from "./types";
import { usePending } from "./pending";

const PAGES = [
  { path: "/", title: "Transactions", label: "Transactions", icon: "▤" },
  { path: "/versions", title: "Versions du dataset", label: "Versions du dataset", icon: "⎇" },
  { path: "/pipeline", title: "Pipeline & automatisation", label: "Pipeline & automatisation", icon: "⚙" },
  { path: "/drift", title: "Dérive des données", label: "Dérive des données", icon: "∿" },
  { path: "/runs", title: "Historique des runs", label: "Historique des runs", icon: "☰" },
  { path: "/ecosystem", title: "Écosystème", label: "Écosystème", icon: "◇" },
];

function Shield() {
  return (
    <svg width="30" height="34" viewBox="0 0 30 34" aria-hidden="true">
      <path d="M15 1 28 6v10c0 8.5-5.6 14.6-13 17C7.600 30.600 2 24.500 2 16V6z" fill="#6f9bff" opacity="0.25" stroke="#9db9ff" strokeWidth="1.500" />
      <path d="m9 17 4 4 8-9" fill="none" stroke="#fff" strokeWidth="2.200" />
    </svg>
  );
}

export default function App() {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();
  const { count: pendingCount } = usePending();

  // The red badge next to "Dérive des données" mirrors the drift alert banner.
  const drift = useQuery({
    queryKey: ["drift", "current"],
    queryFn: () => api<DriftSummary>("/drift/current"),
    enabled: !!user,
    refetchInterval: 15_000,
  });

  if (!user) return <LoginPage />;

  const current = PAGES.find((p) => (p.path === "/" ? pathname === "/" : pathname.startsWith(p.path))) ?? PAGES[0];

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <Shield />
          <div>
            <div className="brand-title">Détection de fraude</div>
            <div className="brand-sub">Plateforme d'opérations</div>
          </div>
        </div>
        <nav className="nav">
          {PAGES.map((page) => (
            <NavLink key={page.path} to={page.path} end={page.path === "/"}>
              <span aria-hidden="true">{page.icon}</span>
              {page.label}
              {page.path === "/drift" && drift.data?.alert && <span className="nav-badge">!</span>}
              {page.path === "/" && pendingCount > 0 && <span className="nav-badge">{pendingCount}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">Usage interne — équipes Data &amp; Risque</div>
      </aside>
      <div className="main">
        <header className="topbar">
          <h1>{current.title}</h1>
          <div className="topbar-user">
            <span>
              Connecté : <strong>{user}</strong>
            </span>
            <button className="btn btn-secondary btn-small" onClick={logout}>
              Déconnexion
            </button>
          </div>
        </header>
        <main className="content">
          <Routes>
            <Route path="/" element={<TransactionsPage />} />
            <Route path="/versions" element={<VersionsPage />} />
            <Route path="/pipeline" element={<PipelinePage />} />
            <Route path="/drift" element={<DriftPage />} />
            <Route path="/runs" element={<RunsPage />} />
            <Route path="/ecosystem" element={<EcosystemPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
