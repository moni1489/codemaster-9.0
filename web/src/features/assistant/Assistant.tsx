import { useMutation, useQuery } from "@tanstack/react-query";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useLang, useLocalePath } from "../../app/lang";
import { useT } from "../../app/useT";
import { Icon } from "../../components/ui/Icon";

interface Source {
  id: string;
  cipher: string;
  title: string;
  period: string;
  file_access: string;
  url: string;
}

interface AskResponse {
  status: "found" | "not_found" | "restricted";
  text: string;
  sources: Source[];
  suggestions: string[];
  provider: string;
  is_llm: boolean;
  degraded: boolean;
  disclaimer: string;
}

interface Turn {
  q: string;
  a?: AskResponse;
  error?: string;
}

/** Чат помощника: ответ всегда с источниками-ссылками и пометкой «сформировано автоматически». */
export function AssistantChat({ compact = false }: { compact?: boolean }) {
  const { t } = useT();
  const lang = useLang();
  const [q, setQ] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const endRef = useRef<HTMLDivElement>(null);
  const mode = useQuery({
    queryKey: ["assistant-mode"],
    queryFn: async () => (await (await fetch("/api/assistant/mode")).json()) as { is_llm: boolean },
    staleTime: 10 * 60_000,
  });
  const ask = useMutation({
    mutationFn: async (query: string) => {
      const res = await fetch("/api/assistant/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, lang }),
      });
      if (res.status === 429) throw new Error(t("assistant.tooMany"));
      if (!res.ok) throw new Error(t("assistant.error"));
      return (await res.json()) as AskResponse;
    },
    onSuccess: (a, query) => setTurns((ts) => ts.map((x) => (x.q === query && !x.a ? { ...x, a } : x))),
    onError: (e, query) => setTurns((ts) => ts.map((x) => (x.q === query && !x.a ? { ...x, error: (e as Error).message } : x))),
  });
  useEffect(() => endRef.current?.scrollIntoView({ block: "nearest" }), [turns]);

  const send = (query: string) => {
    const v = query.trim();
    if (v.length < 2 || ask.isPending) return;
    setTurns((ts) => [...ts, { q: v }]);
    setQ("");
    ask.mutate(v);
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    send(q);
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      {mode.data && !mode.data.is_llm && (
        <p className="mb-2 rounded-md border border-warn/50 bg-warn/10 px-2 py-1 text-xs" role="note">
          {t("assistant.demoMode")}
        </p>
      )}
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto pr-1" aria-live="polite">
        {turns.length === 0 && (
          <div className="space-y-2 text-sm">
            <p className="text-muted">{t("assistant.lead")}</p>
            <p className="font-medium">{t("assistant.examples")}</p>
            <ul className="space-y-1">
              {(["ex1", "ex2", "ex3"] as const).map((k) => (
                <li key={k}>
                  <button type="button" className="text-left text-primary underline" onClick={() => send(t(`assistant.${k}`))}>
                    {t(`assistant.${k}`)}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {turns.map((turn, i) => (
          <div key={i} className="space-y-2">
            <p className="ml-auto max-w-[85%] rounded-lg bg-primary px-3 py-2 text-sm text-primary-ink">{turn.q}</p>
            {!turn.a && !turn.error && <p className="text-sm text-muted">{t("assistant.thinking")}</p>}
            {turn.error && <p className="text-sm text-danger" role="alert">{turn.error}</p>}
            {turn.a && (
              <div className="max-w-[95%] rounded-lg border border-line bg-surface-2 p-3 text-sm">
                <p className="whitespace-pre-line">{turn.a.text}</p>
                {turn.a.degraded && <p className="mt-2 text-xs text-warn">{t("assistant.degraded")}</p>}
                {turn.a.sources.length > 0 && (
                  <div className="mt-3">
                    <p className="text-xs font-semibold uppercase text-muted">{t("assistant.sources")}</p>
                    <ul className="mt-1 space-y-1">
                      {turn.a.sources.map((s) => (
                        <li key={s.id}>
                          <Link to={s.url} className="block rounded border border-line bg-surface px-2 py-1 no-underline hover:border-primary">
                            <span className="text-ink">{s.title}</span>
                            <span className="cipher block text-xs text-muted">
                              {s.cipher}
                              {s.period ? ` · ${s.period}` : ""}
                              {s.file_access !== "open" ? ` · 🔒 ${t("assistant.closed")}` : ""}
                            </span>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {turn.a.suggestions.length > 0 && (
                  <div className="mt-3">
                    <p className="text-xs font-semibold uppercase text-muted">{t("assistant.suggestions")}</p>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {turn.a.suggestions.map((s) => (
                        <button key={s} type="button" className="badge border-line bg-surface hover:border-primary" onClick={() => send(s)}>
                          {s}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                <p className="mt-3 border-t border-line pt-2 text-xs text-muted">ⓘ {turn.a.disclaimer}</p>
              </div>
            )}
          </div>
        ))}
        <div ref={endRef} />
      </div>
      <form role="search" onSubmit={submit} className="mt-3 flex gap-2">
        <label htmlFor={compact ? "ai-q-w" : "ai-q"} className="sr-only">{t("assistant.placeholder")}</label>
        <input
          id={compact ? "ai-q-w" : "ai-q"}
          className="input"
          value={q}
          maxLength={500}
          placeholder={t("assistant.placeholder")}
          onChange={(e) => setQ(e.target.value)}
        />
        <button type="submit" className="btn-primary" disabled={ask.isPending} aria-label={t("assistant.send")}>
          <Icon name="search" size={18} />
        </button>
      </form>
      <p className="mt-1 text-xs text-muted">{t("assistant.privacy")}</p>
    </div>
  );
}

export function AssistantWidget() {
  const { t } = useT();
  const lp = useLocalePath();
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  if (pathname.endsWith("/assistant")) return null;
  return (
    <div className="fixed bottom-4 right-4 z-40">
      {open && (
        <section
          aria-label={t("assistant.title")}
          className="card mb-3 flex h-[min(36rem,80vh)] w-[min(24rem,calc(100vw-2rem))] flex-col p-4 shadow-xl"
        >
          <div className="mb-2 flex items-center justify-between gap-2">
            <h2 className="whitespace-nowrap text-base font-semibold">{t("assistant.title")}</h2>
            <div className="flex gap-1">
              <Link to={lp("/assistant")} className="btn-ghost px-2 py-1 text-xs" onClick={() => setOpen(false)}>
                {t("assistant.fullPage")}
              </Link>
              <button type="button" className="btn-ghost px-2 py-1" aria-label={t("assistant.close")} onClick={() => setOpen(false)}>
                <Icon name="close" size={16} />
              </button>
            </div>
          </div>
          <AssistantChat compact />
        </section>
      )}
      {!open && (
        <button type="button" className="btn-primary rounded-full px-4 py-3 shadow-lg" onClick={() => setOpen(true)} aria-label={t("assistant.open")}>
          <Icon name="info" /> <span className="hidden sm:inline">{t("assistant.title")}</span>
        </button>
      )}
    </div>
  );
}

export function AssistantPage() {
  const { t } = useT();
  useEffect(() => {
    document.title = t("assistant.title");
  }, [t]);
  return (
    <div className="container-page py-6">
      <h1 className="text-3xl">{t("assistant.title")}</h1>
      <div className="card mt-4 flex h-[70vh] flex-col p-4">
        <AssistantChat />
      </div>
    </div>
  );
}
