import { useEffect, useState } from "react";
import { fetchHealth } from "./services/api";
import type { HealthResponse } from "./types/api";

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchHealth().then(setHealth).catch((e: Error) => setError(e.message));
  }, []);

  return (
    <main className="mx-auto max-w-3xl p-6">
      <h1 className="text-2xl font-bold">Crypto Radar AI</h1>
      <p className="mt-4 text-sm">
        Backend bağlantısı:{" "}
        {error ? <span className="text-red-400">BAĞLANTI YOK — {error}</span>
          : health ? <span className="text-emerald-400">{health.status} (v{health.version}, {health.run_mode})</span>
          : "kontrol ediliyor..."}
      </p>
    </main>
  );
}
