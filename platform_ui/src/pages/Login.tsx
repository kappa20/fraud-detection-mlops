import { FormEvent, useState } from "react";
import { useAuth } from "../auth";
import { ErrorNote } from "../components/ui";

export default function LoginPage() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username.trim(), password);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={submit}>
        <div className="login-head">
          <svg width="34" height="38" viewBox="0 0 30 34" aria-hidden="true">
            <path d="M15 1 28 6v10c0 8.5-5.6 14.6-13 17C7.600 30.600 2 24.500 2 16V6z" fill="#0a1f44" />
            <path d="m9 17 4 4 8-9" fill="none" stroke="#fff" strokeWidth="2.200" />
          </svg>
          <h1>Plateforme d'opérations</h1>
          <div className="dim">Détection de fraude — accès réservé aux collaborateurs</div>
        </div>
        <div className="login-body">
          <label className="field">
            <span>Identifiant</span>
            <input type="text" autoFocus autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required />
          </label>
          <label className="field">
            <span>Mot de passe</span>
            <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </label>
          <button className="btn" style={{ width: "100%" }} disabled={busy}>
            {busy ? "Connexion…" : "Se connecter"}
          </button>
          <ErrorNote error={error} />
          <div className="login-note">Les comptes sont définis par l'administrateur de la plateforme (variable PLATFORM_USERS).</div>
        </div>
      </form>
    </div>
  );
}
