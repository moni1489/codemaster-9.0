import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Logo } from "../../components/layout/Logo";
import { ApiError } from "../../lib/api";
import { admin, type Me, ROLE_LABEL } from "../api";
import { useAuth } from "../auth";
import { Alert, PageHeader, StatusBadge } from "../ui";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const qc = useQueryClient();
  const state = (location.state ?? {}) as { reason?: string; from?: string };
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  useEffect(() => {
    document.title = "Вход — админ-панель ГА ВКО";
  }, []);
  const login = useMutation({
    mutationFn: () => admin.post<Me>("/auth/login", { email, password }),
    onSuccess: (me) => {
      qc.setQueryData(["admin-me"], me);
      navigate(state.from && state.from !== "/admin/login" ? state.from : "/admin", { replace: true });
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    login.mutate();
  };
  const err = login.error;
  return (
    <main className="flex min-h-screen items-center justify-center bg-bg p-4">
      <form onSubmit={submit} data-form="login" className="card w-full max-w-sm space-y-4 p-6" aria-labelledby="login-h">
        <div className="flex items-center gap-3">
          <Logo className="h-10 w-10" />
          <h1 id="login-h" className="text-xl">Вход для сотрудников</h1>
        </div>
        {state.reason && <Alert kind="info">{state.reason}</Alert>}
        <label className="block text-sm font-medium">
          E-mail
          <input className="input mt-1" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="block text-sm font-medium">
          Пароль
          <input className="input mt-1" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {err && (
          <Alert kind="error">
            {err instanceof ApiError && err.status === 429 ? "Слишком много попыток входа. Подождите минуту." : (err as Error).message}
          </Alert>
        )}
        <button type="submit" className="btn-primary w-full" disabled={login.isPending}>
          {login.isPending ? "Вход…" : "Войти"}
        </button>
        <p className="text-xs text-muted">
          Доступ только для сотрудников архива. Попытки входа ограничены и записываются в журнал. <a href="/ru">На сайт</a>
        </p>
      </form>
    </main>
  );
}

interface Stats {
  documents: number;
  documents_public: number;
  documents_draft: number;
  review_queue: number;
  news_drafts: number;
  feedback_new: number;
}

interface QueueItem {
  entity: string;
  id: string;
  title: string;
  status: string;
  updated_at: string;
}

const ENTITY_ROUTE: Record<string, string> = { news: "/admin/news", page: "/admin/pages", document: "/admin/catalog", faq: "/admin/faq" };
const ENTITY_LABEL: Record<string, string> = { news: "Новость", page: "Страница", document: "Документ", faq: "FAQ", fund: "Фонд", inventory: "Опись", case: "Дело" };

export function Dashboard() {
  const { me, can } = useAuth();
  useEffect(() => {
    document.title = "Сводка — админ-панель ГА ВКО";
  }, []);
  const stats = useQuery({ queryKey: ["admin-stats"], queryFn: () => admin.get<Stats>("/admin/stats") });
  const queue = useQuery({
    queryKey: ["review-queue"],
    queryFn: () => admin.get<QueueItem[]>("/admin/review-queue"),
    enabled: can("content.review"),
  });
  const cards: [string, number | undefined][] = [
    ["Документов в каталоге", stats.data?.documents],
    ["Опубликовано (в индексе)", stats.data?.documents_public],
    ["Черновиков документов", stats.data?.documents_draft],
    ["На проверке", stats.data?.review_queue],
    ["Черновиков новостей", stats.data?.news_drafts],
    ["Новых отзывов", stats.data?.feedback_new],
  ];
  return (
    <>
      <PageHeader title={`Здравствуйте, ${me.full_name}`} />
      <p className="-mt-4 mb-6 text-muted">Роли: {me.roles.map((r) => ROLE_LABEL[r] ?? r).join(", ")}</p>
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map(([label, value]) => (
          <li key={label} className="card p-4">
            <p className="text-sm text-muted">{label}</p>
            <p className="mt-1 text-3xl font-semibold tabular-nums">{value ?? "…"}</p>
          </li>
        ))}
      </ul>
      {can("content.review") && (
        <section className="mt-8" aria-labelledby="queue-h">
          <h2 id="queue-h" className="text-xl">Очередь на проверку</h2>
          {queue.data?.length === 0 && <p className="mt-2 text-muted">Нет материалов, ожидающих проверки.</p>}
          <ul className="mt-3 space-y-2">
            {queue.data?.map((q) => (
              <li key={`${q.entity}-${q.id}`} className="card flex flex-wrap items-center justify-between gap-2 p-3">
                <span>
                  <span className="text-xs text-muted">{ENTITY_LABEL[q.entity] ?? q.entity}</span>
                  <br />
                  {ENTITY_ROUTE[q.entity] ? <Link to={`${ENTITY_ROUTE[q.entity]}/${q.id}`}>{q.title}</Link> : q.title}
                </span>
                <StatusBadge status={q.status} />
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}
