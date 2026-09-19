import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./auth";
import { PendingProvider } from "./pending";
import "./styles.css";
import { ToastProvider } from "./toast";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false, staleTime: 5_000 } },
});

// HashRouter: FastAPI serves a single index.html, so client-side routes must not
// depend on server-side fallbacks (a refresh on /#/drift just works).
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AuthProvider>
          <PendingProvider>
            <HashRouter>
              <App />
            </HashRouter>
          </PendingProvider>
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
