import { useEffect, useState } from "react";

type Health = { status: string; database: string };

// Page minimale de la tâche 0.1 : vérifie la chaîne navigateur → proxy Vite → Django → PostgreSQL.
// Le squelette réel (PWA, Tailwind, shadcn/ui, i18next, coquille) arrive avec la tâche 1.6.
export function App() {
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => {
    fetch("/api/health/")
      .then((response) => response.json() as Promise<Health>)
      .then(setHealth)
      .catch(() => setHealth({ status: "error", database: "error" }));
  }, []);

  return (
    <main>
      <h1>Mwangaza</h1>
      <p data-testid="api-status">{health ? `${health.status} · ${health.database}` : "…"}</p>
    </main>
  );
}
