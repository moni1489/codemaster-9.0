import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Loading } from "../../components/ui/States";
import { ACCESS_LABEL, admin, DESC_LABEL, STATUS_LABEL } from "../api";
import { useAuth } from "../auth";
import { Alert, ConfirmButton, LangTabs, PageHeader, StatusBadge, WorkflowPanel } from "../ui";

const CATEGORIES: Record<string, string> = {
  historical: "Исторические документы", photo: "Фотографии", map: "Карты и чертежи", written: "Письменные источники",
  organization: "Документы организаций", personal: "Документы личного происхождения", audiovisual: "Аудио и видео",
};
const DOC_TYPES: Record<string, string> = {
  photo: "Фотография", order: "Приказ", protocol: "Протокол", decision: "Решение", report: "Отчёт", map: "Карта",
  plan: "План/чертёж", newspaper: "Газета", letter: "Письмо", certificate: "Справка/анкета", biography: "Биография",
  poster: "Плакат", audio: "Аудио", video: "Видео", memoir: "Воспоминания/рукопись",
};
const TR_FIELDS: [string, string, boolean][] = [
  ["title", "Название документа", true],
  ["summary", "Краткое содержание", false],
  ["historical_note", "Историческая справка", false],
  ["period_label", "Период (подпись)", false],
  ["author_org", "Автор / организация", false],
  ["place", "Населённый пункт", false],
  ["topic", "Тематика", false],
  ["access_conditions", "Условия доступа (для закрытых)", false],
];

interface ListItem {
  id: string;
  cipher: string;
  title: string;
  description_status: string;
  file_access: string;
  workflow_status: string;
  is_demo: boolean;
  updated_at: string;
}

export function CatalogList() {
  const { can } = useAuth();
  const [sp, setSp] = useSearchParams();
  const [q, setQ] = useState(sp.get("q") ?? "");
  useEffect(() => {
    document.title = "Каталог — админ-панель ГА ВКО";
  }, []);
  const key = sp.toString();
  const res = useQuery({
    queryKey: ["admin-docs", key],
    queryFn: () => admin.get<{ items: ListItem[]; total: number }>(`/admin/catalog/documents?${key}`),
    placeholderData: keepPreviousData,
  });
  const set = (k: string, v: string) => {
    const n = new URLSearchParams(sp);
    if (v) n.set(k, v);
    else n.delete(k);
    n.delete("page");
    setSp(n);
  };
  const page = Number(sp.get("page") ?? "1");
  return (
    <>
      <PageHeader title="Электронный каталог">
        {can("catalog.edit") && <Link to="/admin/catalog/new" className="btn-primary">Добавить документ</Link>}
      </PageHeader>
      <div className="mb-4 grid gap-3 md:grid-cols-4">
        <form
          role="search"
          className="flex gap-2 md:col-span-1"
          onSubmit={(e) => {
            e.preventDefault();
            set("q", q.trim());
          }}
        >
          <label className="sr-only" htmlFor="adm-q">Поиск по шифру или названию</label>
          <input id="adm-q" className="input" placeholder="Шифр или название" value={q} onChange={(e) => setQ(e.target.value)} />
        </form>
        {(
          [
            ["workflow", "Редакционный статус", STATUS_LABEL],
            ["description_status", "Публикация описания", DESC_LABEL],
            ["file_access", "Доступ к копии", ACCESS_LABEL],
          ] as const
        ).map(([k, label, opts]) => (
          <label key={k} className="text-sm">
            <span className="sr-only">{label}</span>
            <select className="input" value={sp.get(k) ?? ""} onChange={(e) => set(k, e.target.value)} aria-label={label}>
              <option value="">{label}: все</option>
              {Object.entries(opts).map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
          </label>
        ))}
      </div>
      {res.isLoading && <Loading />}
      {res.isError && <Alert kind="error">{(res.error as Error).message}</Alert>}
      {res.data && (
        <>
          <p className="mb-2 text-sm text-muted">Найдено: {res.data.total}</p>
          <div className="overflow-x-auto rounded-xl border border-line">
            <table className="w-full min-w-[48rem] text-sm">
              <thead className="bg-surface-2 text-left">
                <tr>
                  <th scope="col" className="px-3 py-2">Документ</th>
                  <th scope="col" className="px-3 py-2">Статус</th>
                  <th scope="col" className="px-3 py-2">Описание</th>
                  <th scope="col" className="px-3 py-2">Копия</th>
                </tr>
              </thead>
              <tbody>
                {res.data.items.map((d) => (
                  <tr key={d.id} className="border-t border-line">
                    <td className="px-3 py-2">
                      <Link to={`/admin/catalog/${d.id}`}>{d.title}</Link>
                      <span className="cipher block text-xs text-muted">{d.cipher}</span>
                    </td>
                    <td className="px-3 py-2"><StatusBadge status={d.workflow_status} /></td>
                    <td className="px-3 py-2">{DESC_LABEL[d.description_status] ?? d.description_status}</td>
                    <td className="px-3 py-2">{ACCESS_LABEL[d.file_access] ?? d.file_access}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-4 flex gap-2">
            <button type="button" className="btn-ghost" disabled={page <= 1} onClick={() => set("page", String(page - 1))}>Назад</button>
            <button type="button" className="btn-ghost" disabled={page * 25 >= res.data.total} onClick={() => set("page", String(page + 1))}>Далее</button>
          </div>
        </>
      )}
    </>
  );
}

interface FileRow {
  id: string;
  kind: string;
  page_no: number;
  mime: string;
  size: number;
  sha256: string;
  original_filename: string | null;
  provenance: string | null;
  rights_note: string | null;
  url: string;
}

interface DocAdmin {
  id: string;
  cipher: string;
  case_id: string;
  sheets: string | null;
  date_from: string | null;
  date_to: string | null;
  date_verified: boolean;
  category: string;
  doc_type: string;
  language: string;
  sheets_count: number | null;
  storage_location: string | null;
  tags: string[];
  description_status: string;
  file_access: string;
  workflow_status: string;
  is_demo: boolean;
  in_public_index: boolean;
  translations: Record<string, Record<string, string | null>>;
  files: FileRow[];
}

interface TreeFund {
  id: string;
  number: string;
  title: string;
  inventories: { id: string; number: string; title: string; cases: { id: string; number: string; cipher: string; title: string }[] }[];
}

function CasePicker({ value, onChange }: { value: string; onChange: (id: string) => void }) {
  const tree = useQuery({ queryKey: ["admin-tree"], queryFn: () => admin.get<TreeFund[]>("/admin/catalog/tree") });
  return (
    <label className="block text-sm font-medium">
      Дело (фонд → опись → дело) *
      <select className="input mt-1" required value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">— выберите дело —</option>
        {tree.data?.map((f) =>
          f.inventories.map((i) => (
            <optgroup key={i.id} label={`Ф. ${f.number} «${f.title.slice(0, 60)}» · Оп. ${i.number}`}>
              {i.cases.map((c) => (
                <option key={c.id} value={c.id}>
                  Д. {c.number} — {c.title.slice(0, 80)}
                </option>
              ))}
            </optgroup>
          )),
        )}
      </select>
    </label>
  );
}

function AccessPanel({ doc }: { doc: DocAdmin }) {
  const qc = useQueryClient();
  const [desc, setDesc] = useState(doc.description_status);
  const [access, setAccess] = useState(doc.file_access);
  const [reason, setReason] = useState("");
  useEffect(() => {
    setDesc(doc.description_status);
    setAccess(doc.file_access);
  }, [doc.description_status, doc.file_access]);
  const save = useMutation({
    mutationFn: () => admin.patch<DocAdmin>(`/admin/catalog/documents/${doc.id}/access`, { description_status: desc, file_access: access, reason }),
    onSuccess: (d) => {
      setReason("");
      qc.setQueryData(["admin-doc", doc.id], d);
    },
  });
  const opening = access === "open" && doc.file_access !== "open";
  return (
    <section className="card space-y-3 p-4" aria-labelledby="acc-h">
      <h2 id="acc-h" className="text-lg">Статусы доступа</h2>
      <p className="text-xs text-muted">Публикация описания и доступ к цифровой копии — независимые статусы. Изменение фиксируется в журнале с основанием.</p>
      <label className="block text-sm">
        Публикация описания
        <select className="input mt-1" value={desc} onChange={(e) => setDesc(e.target.value)}>
          {Object.entries(DESC_LABEL).map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
      </label>
      <label className="block text-sm">
        Доступ к цифровой копии
        <select className="input mt-1" value={access} onChange={(e) => setAccess(e.target.value)}>
          {Object.entries(ACCESS_LABEL).map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
      </label>
      <label className="block text-sm">
        Основание (обязательно)
        <input className="input mt-1" value={reason} minLength={5} onChange={(e) => setReason(e.target.value)} placeholder="Например: персональных данных нет, решение ЭПК" />
      </label>
      {opening ? (
        <ConfirmButton title="Открыть доступ к копии?" message="Облегчённая копия станет доступна всем посетителям сайта (если описание опубликовано). Убедитесь, что документ не содержит персональных данных и сведений ограниченного доступа." onConfirm={() => save.mutate()} disabled={reason.trim().length < 5 || save.isPending}>
          Сохранить статусы
        </ConfirmButton>
      ) : (
        <button type="button" className="btn-primary" disabled={reason.trim().length < 5 || save.isPending} onClick={() => save.mutate()}>
          Сохранить статусы
        </button>
      )}
      {save.isError && <Alert kind="error">{(save.error as Error).message}</Alert>}
    </section>
  );
}

function FilesPanel({ doc }: { doc: DocAdmin }) {
  const { can } = useAuth();
  const qc = useQueryClient();
  const [files, setFiles] = useState<FileList | null>(null);
  const [provenance, setProvenance] = useState("");
  const [rights, setRights] = useState("");
  const upload = useMutation({
    mutationFn: () => {
      const fd = new FormData();
      Array.from(files ?? []).forEach((f) => fd.append("files", f));
      fd.append("provenance", provenance);
      fd.append("rights_note", rights);
      return admin.upload<DocAdmin>(`/admin/catalog/documents/${doc.id}/files`, fd);
    },
    onSuccess: (d) => {
      setFiles(null);
      qc.setQueryData(["admin-doc", doc.id], d);
    },
  });
  const masters = doc.files.filter((f) => f.kind === "master");
  return (
    <section className="card space-y-3 p-4" aria-labelledby="files-h">
      <h2 id="files-h" className="text-lg">Цифровые файлы</h2>
      {masters.length === 0 && <p className="text-sm text-muted">Файлов нет.</p>}
      <ul className="space-y-2 text-sm">
        {masters.map((m) => (
          <li key={m.id} className="rounded-lg border border-line p-2">
            <a href={m.url} target="_blank" rel="noopener">{m.original_filename ?? m.mime}</a>
            <span className="block text-xs text-muted">
              {m.mime} · {(m.size / 1024).toFixed(0)} КБ · лист {m.page_no} · sha256 {m.sha256.slice(0, 12)}…
            </span>
            <span className="block text-xs text-muted">Происхождение: {m.provenance} · Права: {m.rights_note}</span>
            <span className="block text-xs text-muted">Облегчённых копий: {doc.files.filter((f) => f.kind === "view").length}</span>
          </li>
        ))}
      </ul>
      {can("files.upload") && (
        <form
          data-form="admin"
          className="space-y-2 border-t border-line pt-3"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            upload.mutate();
          }}
        >
          <label className="block text-sm">
            Файлы (PDF, JPG, PNG, TIFF, WebP; до 50 МБ)
            <input className="mt-1 block w-full text-sm" type="file" multiple required accept=".pdf,.jpg,.jpeg,.png,.tif,.tiff,.webp" onChange={(e) => setFiles(e.target.files)} />
          </label>
          <label className="block text-sm">
            Происхождение *
            <input className="input mt-1" required minLength={3} value={provenance} onChange={(e) => setProvenance(e.target.value)} placeholder="Сканирование в архиве, 2026" />
          </label>
          <label className="block text-sm">
            Права на публикацию *
            <input className="input mt-1" required minLength={2} value={rights} onChange={(e) => setRights(e.target.value)} placeholder="Документ НАФ, ограничений нет" />
          </label>
          <button type="submit" className="btn-primary" disabled={upload.isPending || !files?.length}>
            {upload.isPending ? "Загрузка и обработка…" : "Загрузить"}
          </button>
          <p className="text-xs text-muted">Тип файла проверяется по содержимому; для просмотра создаются облегчённые WebP-копии, мастер-копия не публикуется.</p>
          {upload.isError && <Alert kind="error">{(upload.error as Error).message}</Alert>}
        </form>
      )}
    </section>
  );
}

export function DocumentEdit() {
  const { id = "new" } = useParams();
  const isNew = id === "new";
  const { can } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [lang, setLang] = useState("ru");
  const [form, setForm] = useState<Record<string, string | boolean>>({ category: "historical", doc_type: "decision", date_verified: true });
  const [tr, setTr] = useState<Record<string, Record<string, string | null>>>({ ru: {} });
  const q = useQuery({ queryKey: ["admin-doc", id], queryFn: () => admin.get<DocAdmin>(`/admin/catalog/documents/${id}`), enabled: !isNew });
  useEffect(() => {
    document.title = `${isNew ? "Новый документ" : (q.data?.cipher ?? "Документ")} — админ-панель ГА ВКО`;
  }, [isNew, q.data?.cipher]);
  useEffect(() => {
    if (!q.data) return;
    const d = q.data;
    setForm({
      category: d.category, doc_type: d.doc_type, date_from: d.date_from ?? "", date_to: d.date_to ?? "",
      date_verified: d.date_verified, language: d.language, sheets_count: d.sheets_count ? String(d.sheets_count) : "",
      storage_location: d.storage_location ?? "", tags: d.tags.join(", "), sheets: d.sheets ?? "",
    });
    setTr(d.translations);
  }, [q.data]);
  const payload = () => ({
    category: form.category, doc_type: form.doc_type,
    date_from: form.date_from || null, date_to: form.date_to || null, date_verified: !!form.date_verified,
    language: form.language || null, sheets_count: form.sheets_count ? Number(form.sheets_count) : null,
    storage_location: form.storage_location || null,
    tags: String(form.tags ?? "").split(",").map((s) => s.trim()).filter(Boolean),
    translations: Object.fromEntries(
      Object.entries(tr)
        .filter(([, v]) => (v.title ?? "").trim())
        .map(([l, v]) => [l, Object.fromEntries(TR_FIELDS.map(([f]) => [f, v[f] || null]))]),
    ),
  });
  const save = useMutation({
    mutationFn: () =>
      isNew
        ? admin.post<DocAdmin>("/admin/catalog/documents", { ...payload(), case_id: form.case_id, sheets: form.sheets })
        : admin.patch<DocAdmin>(`/admin/catalog/documents/${id}`, payload()),
    onSuccess: (d) => {
      qc.setQueryData(["admin-doc", d.id], d);
      void qc.invalidateQueries({ queryKey: ["admin-docs"] });
      void qc.invalidateQueries({ queryKey: ["versions", "document", d.id] });
      if (isNew) navigate(`/admin/catalog/${d.id}`, { replace: true });
    },
  });
  const del = useMutation({
    mutationFn: () => admin.del(`/admin/catalog/documents/${id}?confirm=${encodeURIComponent(q.data?.cipher ?? "")}`),
    onSuccess: () => navigate("/admin/catalog"),
  });
  if (!isNew && (q.isLoading || !q.data)) return q.isError ? <Alert kind="error">{(q.error as Error).message}</Alert> : <Loading />;
  const doc = q.data;
  const cur = tr[lang] ?? {};
  const setF = (k: string, v: string | boolean) => setForm((f) => ({ ...f, [k]: v }));
  const setT = (k: string, v: string) => setTr((t) => ({ ...t, [lang]: { ...(t[lang] ?? {}), [k]: v } }));
  const editable = can("catalog.edit");

  return (
    <>
      <PageHeader title={isNew ? "Новый документ" : (doc?.translations.ru?.title ?? doc?.cipher ?? "")}>
        {doc?.in_public_index && <a className="btn-ghost" href={`/ru/catalog/documents/${doc.id}`} target="_blank" rel="noopener">Открыть на сайте</a>}
      </PageHeader>
      {doc && (
        <p className="-mt-4 mb-4 flex flex-wrap items-center gap-2 text-sm">
          <code className="cipher rounded bg-surface-2 px-2 py-1">{doc.cipher}</code>
          <StatusBadge status={doc.workflow_status} />
          <span className="badge border-line">Описание: {DESC_LABEL[doc.description_status]}</span>
          <span className="badge border-line">Копия: {ACCESS_LABEL[doc.file_access]}</span>
          <span className={`badge ${doc.in_public_index ? "border-ok/60 text-ok" : "border-line text-muted"}`}>
            {doc.in_public_index ? "Виден на сайте" : "Не виден на сайте"}
          </span>
          {doc.is_demo && <span className="badge border-warn/60 text-warn">Демо</span>}
        </p>
      )}
      <div className="grid gap-6 xl:grid-cols-[1fr_24rem]">
        <form
          data-form="admin"
          className="card space-y-4 p-5"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          {isNew && (
            <>
              <CasePicker value={String(form.case_id ?? "")} onChange={(v) => setF("case_id", v)} />
              <label className="block text-sm font-medium">
                Листы *
                <input className="input mt-1" required maxLength={32} placeholder="л. 3–7" value={String(form.sheets ?? "")} onChange={(e) => setF("sheets", e.target.value)} />
                <span className="text-xs font-normal text-muted">Шифр сформируется автоматически: шифр дела + листы.</span>
              </label>
              <Alert kind="info">Новая запись создаётся черновиком: описание «Требует проверки», доступ к копии «Закрыт». Публикует модератор.</Alert>
            </>
          )}
          {!isNew && doc && doc.workflow_status !== "draft" && !can("content.publish") && (
            <Alert kind="warn">Правка записи в статусе «{STATUS_LABEL[doc.workflow_status]}» вернёт её на проверку и уберёт с сайта до согласования.</Alert>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm font-medium">
              Категория *
              <select className="input mt-1" value={String(form.category)} onChange={(e) => setF("category", e.target.value)}>
                {Object.entries(CATEGORIES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </label>
            <label className="block text-sm font-medium">
              Тип документа *
              <select className="input mt-1" value={String(form.doc_type)} onChange={(e) => setF("doc_type", e.target.value)}>
                {Object.entries(DOC_TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </label>
            <label className="block text-sm font-medium">
              Дата с
              <input type="date" className="input mt-1" value={String(form.date_from ?? "")} onChange={(e) => setF("date_from", e.target.value)} />
            </label>
            <label className="block text-sm font-medium">
              Дата по
              <input type="date" className="input mt-1" value={String(form.date_to ?? "")} onChange={(e) => setF("date_to", e.target.value)} />
            </label>
            <label className="flex items-center gap-2 text-sm sm:col-span-2">
              <input type="checkbox" checked={!!form.date_verified} onChange={(e) => setF("date_verified", e.target.checked)} /> Датировка подтверждена (иначе на сайте пометка «Датировка не подтверждена»)
            </label>
            <label className="block text-sm font-medium">
              Язык документа
              <input className="input mt-1" value={String(form.language ?? "")} onChange={(e) => setF("language", e.target.value)} placeholder="русский" />
            </label>
            <label className="block text-sm font-medium">
              Количество листов
              <input className="input mt-1" inputMode="numeric" value={String(form.sheets_count ?? "")} onChange={(e) => setF("sheets_count", e.target.value.replace(/\D/g, ""))} />
            </label>
            <label className="block text-sm font-medium sm:col-span-2">
              Место хранения
              <input className="input mt-1" value={String(form.storage_location ?? "")} onChange={(e) => setF("storage_location", e.target.value)} />
            </label>
            <label className="block text-sm font-medium sm:col-span-2">
              Ключевые слова (через запятую)
              <input className="input mt-1" value={String(form.tags ?? "")} onChange={(e) => setF("tags", e.target.value)} />
            </label>
          </div>
          <div className="flex items-center justify-between border-t border-line pt-4">
            <span className="text-sm font-medium">Описание на языке</span>
            <LangTabs value={lang} onChange={setLang} />
          </div>
          {TR_FIELDS.map(([f, label, required]) => (
            <label key={f} className="block text-sm font-medium">
              {label} {required && lang === "ru" && "*"}
              {f === "title" || f === "period_label" || f === "place" || f === "topic" ? (
                <input className="input mt-1" required={required && lang === "ru"} minLength={required ? 3 : undefined} value={cur[f] ?? ""} onChange={(e) => setT(f, e.target.value)} />
              ) : (
                <textarea className="input mt-1 min-h-16" value={cur[f] ?? ""} onChange={(e) => setT(f, e.target.value)} />
              )}
            </label>
          ))}
          {save.isError && <Alert kind="error">{(save.error as Error).message}</Alert>}
          {save.isSuccess && <Alert kind="ok">Сохранено, создана новая версия.</Alert>}
          <div className="flex flex-wrap gap-2">
            <button type="submit" className="btn-primary" disabled={!editable || save.isPending}>
              {isNew ? "Создать черновик" : "Сохранить"}
            </button>
            {!isNew && doc && can("catalog.delete") && (
              <ConfirmButton danger title="Удалить документ?" requireText={doc.cipher} message="Запись и все её цифровые файлы будут удалены безвозвратно. Ошибочные записи лучше снимать с публикации." onConfirm={() => del.mutate()}>
                Удалить
              </ConfirmButton>
            )}
          </div>
          {del.isError && <Alert kind="error">{(del.error as Error).message}</Alert>}
        </form>
        {doc && (
          <div className="space-y-4">
            <WorkflowPanel entity="document" id={doc.id} status={doc.workflow_status} invalidate={[["admin-doc", doc.id], ["admin-docs"], ["review-queue"]]} />
            {can("catalog.set_access") ? (
              <AccessPanel doc={doc} />
            ) : (
              <Alert kind="info">Статусы доступа меняет модератор (право «catalog.set_access»).</Alert>
            )}
            <FilesPanel doc={doc} />
          </div>
        )}
      </div>
    </>
  );
}
