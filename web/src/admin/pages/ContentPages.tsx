import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Loading } from "../../components/ui/States";
import { admin } from "../api";
import { useAuth } from "../auth";
import { Alert, ConfirmButton, LangTabs, PageHeader, StatusBadge, WorkflowPanel } from "../ui";

interface Summary {
  entity: string;
  id: string;
  title: string;
  status: string;
  updated_at: string;
  extra: Record<string, unknown>;
}

type Tr = Record<string, Record<string, string | null>>;

const CATS = { news: "Новости", exhibition: "Выставки", conference: "Конференции", event: "Мероприятия", research: "Исследования", branch: "Филиалы" };

function useDocTitle(t: string) {
  useEffect(() => {
    document.title = `${t} — админ-панель ГА ВКО`;
  }, [t]);
}

function SummaryTable({ rows, base }: { rows: Summary[]; base: string }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-line">
      <table className="w-full min-w-[36rem] text-sm">
        <thead className="bg-surface-2 text-left">
          <tr>
            <th scope="col" className="px-3 py-2">Название</th>
            <th scope="col" className="px-3 py-2">Статус</th>
            <th scope="col" className="px-3 py-2">Изменено</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-t border-line">
              <td className="px-3 py-2">
                <Link to={`${base}/${r.id}`}>{r.title}</Link>
                {r.extra.slug ? <span className="block text-xs text-muted">{String(r.extra.slug)}</span> : null}
              </td>
              <td className="px-3 py-2"><StatusBadge status={r.status} /></td>
              <td className="whitespace-nowrap px-3 py-2 text-muted">{new Date(r.updated_at).toLocaleString("ru-RU")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------- новости ----------------
export function NewsList() {
  const { can } = useAuth();
  const [status, setStatus] = useState("");
  useDocTitle("Новости");
  const q = useQuery({ queryKey: ["admin-news", status], queryFn: () => admin.get<Summary[]>(`/admin/news${status ? `?status=${status}` : ""}`) });
  return (
    <>
      <PageHeader title="Новости">
        {can("content.edit") && <Link to="/admin/news/new" className="btn-primary">Создать новость</Link>}
      </PageHeader>
      <label className="mb-4 block max-w-xs text-sm">
        Статус
        <select className="input mt-1" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Все</option>
          <option value="draft">Черновик</option>
          <option value="review">На проверке</option>
          <option value="needs_rework">Требует доработки</option>
          <option value="published">Опубликовано</option>
          <option value="archived">Архивировано</option>
        </select>
      </label>
      {q.isLoading && <Loading />}
      {q.isError && <Alert kind="error">{(q.error as Error).message}</Alert>}
      {q.data && <SummaryTable rows={q.data} base="/admin/news" />}
    </>
  );
}

interface NewsAdmin {
  id: string;
  slug: string;
  category: string;
  published_at: string | null;
  video_url: string | null;
  workflow_status: string;
  is_demo: boolean;
  translations: Tr;
}

export function NewsEdit() {
  const { id = "new" } = useParams();
  const isNew = id === "new";
  const { can } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [lang, setLang] = useState("ru");
  const [slug, setSlug] = useState("");
  const [category, setCategory] = useState("news");
  const [tr, setTr] = useState<Tr>({ ru: { title: "", lead: "", body: "" } });
  const [saved, setSaved] = useState(false);
  useDocTitle(isNew ? "Новая новость" : "Новость");
  const q = useQuery({ queryKey: ["admin-news-item", id], queryFn: () => admin.get<NewsAdmin>(`/admin/news/${id}`), enabled: !isNew });
  useEffect(() => {
    if (q.data) {
      setSlug(q.data.slug);
      setCategory(q.data.category);
      setTr(q.data.translations);
    }
  }, [q.data]);
  const payloadTr = () =>
    Object.fromEntries(
      Object.entries(tr)
        .filter(([, v]) => (v.title ?? "").trim())
        .map(([l, v]) => [l, { title: v.title, lead: v.lead || null, body: v.body || null }]),
    );
  const save = useMutation({
    mutationFn: () =>
      isNew
        ? admin.post<NewsAdmin>("/admin/news", { slug, category, translations: payloadTr() })
        : admin.patch<NewsAdmin>(`/admin/news/${id}`, { category, translations: payloadTr() }),
    onSuccess: (n) => {
      setSaved(true);
      void qc.invalidateQueries({ queryKey: ["admin-news"] });
      void qc.invalidateQueries({ queryKey: ["versions", "news", n.id] });
      qc.setQueryData(["admin-news-item", n.id], n);
      if (isNew) navigate(`/admin/news/${n.id}`, { replace: true });
    },
  });
  const del = useMutation({ mutationFn: () => admin.del(`/admin/news/${id}`), onSuccess: () => navigate("/admin/news") });
  const cur = tr[lang] ?? { title: "", lead: "", body: "" };
  const set = (field: string, value: string) => {
    setSaved(false);
    setTr((t) => ({ ...t, [lang]: { ...(t[lang] ?? {}), [field]: value } }));
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate();
  };
  if (!isNew && q.isLoading) return <Loading />;
  const editable = can("content.edit");
  return (
    <>
      <PageHeader title={isNew ? "Новая новость" : (q.data?.translations.ru?.title ?? "Новость")}>
        {!isNew && q.data?.workflow_status === "published" && (
          <a className="btn-ghost" href={`/ru/news/${q.data.slug}`} target="_blank" rel="noopener">Открыть на сайте</a>
        )}
      </PageHeader>
      <div className="grid gap-6 xl:grid-cols-[1fr_22rem]">
        <form onSubmit={submit} data-form="admin" className="card space-y-4 p-5">
          {!isNew && q.data && q.data.workflow_status !== "draft" && !can("content.publish") && (
            <Alert kind="warn">Изменение материала в статусе «{q.data.workflow_status}» вернёт его на проверку.</Alert>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm font-medium">
              Адрес (slug) *
              <input className="input mt-1 font-mono" required pattern="[a-z0-9][a-z0-9-]{2,120}" value={slug} disabled={!isNew} onChange={(e) => setSlug(e.target.value)} />
              <span className="text-xs font-normal text-muted">латиница, цифры, дефисы</span>
            </label>
            <label className="block text-sm font-medium">
              Категория
              <select className="input mt-1" value={category} onChange={(e) => setCategory(e.target.value)}>
                {Object.entries(CATS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </label>
          </div>
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-medium">Языковая версия</span>
            <LangTabs value={lang} onChange={setLang} />
          </div>
          {lang !== "ru" && <p className="text-xs text-muted">Перевод необязателен. Без перевода посетитель увидит оригинал с уведомлением.</p>}
          <label className="block text-sm font-medium">
            Заголовок {lang === "ru" && "*"}
            <input className="input mt-1" required={lang === "ru"} minLength={3} maxLength={300} value={cur.title ?? ""} onChange={(e) => set("title", e.target.value)} />
          </label>
          <label className="block text-sm font-medium">
            Анонс
            <textarea className="input mt-1 min-h-16" maxLength={1000} value={cur.lead ?? ""} onChange={(e) => set("lead", e.target.value)} />
          </label>
          <label className="block text-sm font-medium">
            Текст (HTML: p, h2, ul, a, strong…; опасные теги удаляются автоматически)
            <textarea className="input mt-1 min-h-48 font-mono text-xs" maxLength={50_000} value={cur.body ?? ""} onChange={(e) => set("body", e.target.value)} />
          </label>
          {save.isError && <Alert kind="error">{(save.error as Error).message}</Alert>}
          {saved && <Alert kind="ok">Сохранено. Создана новая версия.</Alert>}
          <div className="flex flex-wrap gap-2">
            <button type="submit" className="btn-primary" disabled={!editable || save.isPending}>
              {save.isPending ? "Сохранение…" : "Сохранить"}
            </button>
            {!isNew && can("content.delete") && (
              <ConfirmButton danger title="Удалить новость?" message="Новость будет удалена безвозвратно (последний снимок сохранится в истории версий)." onConfirm={() => del.mutate()}>
                Удалить
              </ConfirmButton>
            )}
          </div>
        </form>
        {!isNew && q.data && (
          <WorkflowPanel entity="news" id={q.data.id} status={q.data.workflow_status} invalidate={[["admin-news-item", id], ["admin-news"], ["review-queue"]]} />
        )}
      </div>
    </>
  );
}

// ---------------- справочные страницы ----------------
export function PagesList() {
  useDocTitle("Страницы");
  const q = useQuery({ queryKey: ["admin-pages"], queryFn: () => admin.get<Summary[]>("/admin/pages") });
  return (
    <>
      <PageHeader title="Справочные страницы" />
      {q.isLoading && <Loading />}
      {q.data && <SummaryTable rows={q.data} base="/admin/pages" />}
    </>
  );
}

interface PageAdmin {
  id: string;
  slug: string;
  section: string;
  workflow_status: string;
  actualized_at: string | null;
  is_demo: boolean;
  translations: Tr;
}

export function PageEdit() {
  const { id = "" } = useParams();
  const { can } = useAuth();
  const qc = useQueryClient();
  const [lang, setLang] = useState("ru");
  const [tr, setTr] = useState<Tr>({});
  const [actualize, setActualize] = useState(true);
  const q = useQuery({ queryKey: ["admin-page", id], queryFn: () => admin.get<PageAdmin>(`/admin/pages/${id}`) });
  useDocTitle(q.data?.translations.ru?.title ?? "Страница");
  useEffect(() => {
    if (q.data) setTr(q.data.translations);
  }, [q.data]);
  const save = useMutation({
    mutationFn: () =>
      admin.patch<PageAdmin>(`/admin/pages/${id}`, {
        actualized_at: actualize ? new Date().toISOString() : undefined,
        translations: Object.fromEntries(
          Object.entries(tr)
            .filter(([, v]) => (v.title ?? "").trim())
            .map(([l, v]) => [l, { title: v.title, body: v.body || null, meta_description: v.meta_description || null }]),
        ),
      }),
    onSuccess: (p) => {
      qc.setQueryData(["admin-page", id], p);
      void qc.invalidateQueries({ queryKey: ["versions", "page", id] });
    },
  });
  if (q.isLoading || !q.data) return <Loading />;
  const cur = tr[lang] ?? { title: "", body: "", meta_description: "" };
  const set = (f: string, v: string) => setTr((t) => ({ ...t, [lang]: { ...(t[lang] ?? {}), [f]: v } }));
  return (
    <>
      <PageHeader title={q.data.translations.ru?.title ?? q.data.slug}>
        <a className="btn-ghost" href={`/ru/${q.data.slug.replace(/^(about|services|visitors)-/, "$1/")}`} target="_blank" rel="noopener">Открыть на сайте</a>
      </PageHeader>
      <div className="grid gap-6 xl:grid-cols-[1fr_22rem]">
        <form
          data-form="admin"
          className="card space-y-4 p-5"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          {q.data.is_demo && <Alert kind="warn">Демонстрационный текст — требует утверждения заказчиком.</Alert>}
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Языковая версия</span>
            <LangTabs value={lang} onChange={setLang} />
          </div>
          <label className="block text-sm font-medium">
            Заголовок
            <input className="input mt-1" value={cur.title ?? ""} onChange={(e) => set("title", e.target.value)} maxLength={300} />
          </label>
          <label className="block text-sm font-medium">
            Описание для поисковиков (meta description)
            <input className="input mt-1" value={cur.meta_description ?? ""} onChange={(e) => set("meta_description", e.target.value)} maxLength={300} />
          </label>
          <label className="block text-sm font-medium">
            Текст (HTML)
            <textarea className="input mt-1 min-h-72 font-mono text-xs" value={cur.body ?? ""} onChange={(e) => set("body", e.target.value)} />
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={actualize} onChange={(e) => setActualize(e.target.checked)} /> Обновить дату актуализации
          </label>
          {save.isError && <Alert kind="error">{(save.error as Error).message}</Alert>}
          {save.isSuccess && <Alert kind="ok">Сохранено, создана новая версия.</Alert>}
          <button type="submit" className="btn-primary" disabled={!can("content.edit") || save.isPending}>Сохранить</button>
        </form>
        <WorkflowPanel entity="page" id={q.data.id} status={q.data.workflow_status} invalidate={[["admin-page", id], ["admin-pages"]]} />
      </div>
    </>
  );
}

// ---------------- FAQ ----------------
interface FaqAdmin {
  id: string;
  group_id: string;
  group: string;
  sort_order: number;
  workflow_status: string;
  translations: Tr;
}

export function FaqAdminPage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  useDocTitle("FAQ");
  const q = useQuery({ queryKey: ["admin-faq"], queryFn: () => admin.get<FaqAdmin[]>("/admin/faq") });
  const groups = Array.from(new Map((q.data ?? []).map((f) => [f.group_id, f.group])).entries());
  const [groupId, setGroupId] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const create = useMutation({
    mutationFn: () => admin.post<FaqAdmin>("/admin/faq", { group_id: groupId || groups[0]?.[0], translations: { ru: { question, answer } } }),
    onSuccess: () => {
      setQuestion("");
      setAnswer("");
      void qc.invalidateQueries({ queryKey: ["admin-faq"] });
    },
  });
  const del = useMutation({ mutationFn: (id: string) => admin.del(`/admin/faq/${id}`), onSuccess: () => void qc.invalidateQueries({ queryKey: ["admin-faq"] }) });
  return (
    <>
      <PageHeader title="Вопросы и ответы" />
      {can("content.edit") && (
        <form
          data-form="admin"
          className="card mb-6 grid gap-3 p-4 md:grid-cols-[12rem_1fr]"
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          <label className="text-sm font-medium">
            Группа
            <select className="input mt-1" value={groupId} onChange={(e) => setGroupId(e.target.value)}>
              {groups.map(([gid, slug]) => (
                <option key={gid} value={gid}>{slug}</option>
              ))}
            </select>
          </label>
          <div className="space-y-2">
            <label className="block text-sm font-medium">
              Вопрос (рус.)
              <input className="input mt-1" required minLength={5} value={question} onChange={(e) => setQuestion(e.target.value)} />
            </label>
            <label className="block text-sm font-medium">
              Ответ (рус.)
              <textarea className="input mt-1" required minLength={2} value={answer} onChange={(e) => setAnswer(e.target.value)} />
            </label>
            <button type="submit" className="btn-primary" disabled={create.isPending}>Добавить (черновик)</button>
            {create.isError && <Alert kind="error">{(create.error as Error).message}</Alert>}
          </div>
        </form>
      )}
      {q.isLoading && <Loading />}
      <ul className="space-y-3">
        {q.data?.map((f) => (
          <li key={f.id} className="card p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="text-xs text-muted">{f.group}</p>
                <p className="font-medium">{f.translations.ru?.question}</p>
                <p className="mt-1 text-sm text-muted">{f.translations.ru?.answer}</p>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge status={f.workflow_status} />
                {can("content.delete") && (
                  <ConfirmButton danger title="Удалить вопрос?" message="Вопрос будет удалён." onConfirm={() => del.mutate(f.id)}>
                    Удалить
                  </ConfirmButton>
                )}
              </div>
            </div>
            {f.workflow_status !== "published" && (
              <details className="mt-2">
                <summary className="cursor-pointer text-sm">Согласование</summary>
                <div className="mt-2">
                  <WorkflowPanel entity="faq" id={f.id} status={f.workflow_status} invalidate={[["admin-faq"]]} />
                </div>
              </details>
            )}
          </li>
        ))}
      </ul>
    </>
  );
}

// ---------------- отзывы ----------------
export function FeedbackAdmin() {
  useDocTitle("Отзывы");
  const q = useQuery({
    queryKey: ["admin-feedback"],
    queryFn: () => admin.get<{ id: string; message: string; page: string | null; email: string | null; created_at: string }[]>("/admin/feedback"),
  });
  return (
    <>
      <PageHeader title="Отзывы о работе сайта" />
      <Alert kind="info">Отзывы не являются официальными обращениями; e-mail хранится только при согласии автора.</Alert>
      {q.isLoading && <Loading />}
      <ul className="space-y-2">
        {q.data?.map((f) => (
          <li key={f.id} className="card p-3 text-sm">
            <p className="text-xs text-muted">
              {new Date(f.created_at).toLocaleString("ru-RU")} · {f.page ?? "—"} {f.email ? `· ${f.email}` : ""}
            </p>
            <p className="mt-1 whitespace-pre-wrap">{f.message}</p>
          </li>
        ))}
      </ul>
    </>
  );
}
