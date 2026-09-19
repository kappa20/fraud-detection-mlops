import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { post, setUnauthorizedHandler, tokenStore } from "./api";

interface AuthState {
  user: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<string | null>(tokenStore.get() ? tokenStore.user() : null);

  const logout = useCallback(() => {
    tokenStore.clear();
    setUser(null);
  }, []);

  useEffect(() => setUnauthorizedHandler(logout), [logout]);

  const login = useCallback(async (username: string, password: string) => {
    const result = await post<{ token: string; username: string }>("/auth/login", { username, password });
    tokenStore.set(result.token, result.username);
    setUser(result.username);
  }, []);

  return <AuthContext.Provider value={{ user, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
