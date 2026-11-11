import { useEffect, useState } from "react";

type Health = { status: string; db: string; llm_provider: string };

/** Временная страница этапа 1: проверка, что стек поднят. */
export function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d: Health) => setHealth(d))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  return (
    <main className="container-page py-16">
      <h1 className="text-3xl">Государственный архив ВКО — прототип</h1>
      <p className="mt-2 text-muted">Этап 1: пустой стек.</p>
      <section className="card mt-6 p-4" aria-live="polite">
        <h2 className="text-lg">Состояние API</h2>
        {health && <pre className="mt-2 text-sm">{JSON.stringify(health, null, 2)}</pre>}
        {error && <p className="mt-2 text-danger">API недоступен: {error}</p>}
        {!health && !error && <p className="mt-2">Загрузка…</p>}
      </section>
    </main>
  );
}
