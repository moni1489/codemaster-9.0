import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { Loading } from "../../components/ui/States";
import { admin, ROLE_LABEL } from "../api";
import { useAuth } from "../auth";
import { Alert, ConfirmButton, LangTabs, PageHeader } from "../ui";

function useDocTitle(t: string) {
  useEffect(() => {
    document.title = `${t} — админ-панель ГА ВКО`;
  }, [t]);
}

// ---------------- филиалы ----------------
interface BranchAdmin {
  id: string;
  slug: string;
  type: string;
  official_name: string | null;
  phone: string | null;
  email: string | null;
  director: string | null;
  lat: number | null;
  lon: number | null;
  coords_verified: boolean;
  visible: boolean;
  can_edit: boolean;
  can_edit_all_fields: boolean;
  translations: Record<string, Record<string, string | null>>;
}

export function BranchesAdmin() {
  useDocTitle("Филиалы");
  const q = useQuery({ queryKey: ["admin-branches"], queryFn: () => admin.get<BranchAdmin[]>("/admin/branches") });
  return (
    <>
      <PageHeader title="Филиалы" />
      {q.isLoading && <Loading />}
      {q.isError && <Alert kind="error">{(q.error as Error).message}</Alert>}
      <ul className="grid gap-3 md:grid-cols-2">
        {q.data?.map((b) => (
          <li key={b.id} className="card p-4">
            <Link to={`/admin/branches/${b.id}`} className="font-medium">{b.translations.ru?.short_name ?? b.slug}</Link>
            <p className="text-sm text-muted">{b.translations.ru?.address}</p>
            <p className="text-sm">{b.phone ?? "—"} · {b.email ?? "—"}</p>
            {!b.coords_verified && <p className="mt-1 text-xs text-warn">Координаты не подтверждены</p>}
          </li>
        ))}
      </ul>
    </>
  );
}

export function BranchEdit() {
  const { id = "" } = useParams();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["admin-branch", id], queryFn: () => admin.get<BranchAdmin>(`/admin/branches/${id}`), retry: false });
  useDocTitle(q.data?.translations.ru?.short_name ?? "Филиал");
  const [lang, setLang] = useState("ru");
  const [f, setF] = useState<Record<string, string | boolean>>({});
  const [tr, setTr] = useState<Record<string, Record<string, string | null>>>({});
  useEffect(() => {
    if (!q.data) return;
    setF({
      phone: q.data.phone ?? "", email: q.data.email ?? "", director: q.data.director ?? "",
      lat: q.data.lat?.toString() ?? "", lon: q.data.lon?.toString() ?? "", coords_verified: q.data.coords_verified, visible: q.data.visible,
    });
    setTr(q.data.translations);
  }, [q.data]);
  const save = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = {
        phone: f.phone || null,
        email: f.email || null,
        director: f.director || null,
        translations: Object.fromEntries(Object.entries(tr).map(([l, v]) => [l, { address: v.address, hours: v.hours, description: v.description || null }])),
      };
      if (q.data?.can_edit_all_fields) {
        body.lat = f.lat === "" ? null : Number(f.lat);
        body.lon = f.lon === "" ? null : Number(f.lon);
        body.coords_verified = !!f.coords_verified;
        body.visible = !!f.visible;
      }
      return admin.patch<BranchAdmin>(`/admin/branches/${id}`, body);
    },
    onSuccess: (b) => {
      qc.setQueryData(["admin-branch", id], b);
      void qc.invalidateQueries({ queryKey: ["admin-branches"] });
    },
  });
  if (q.isLoading) return <Loading />;
  if (q.isError || !q.data) return <Alert kind="error">{(q.error as Error)?.message ?? "Нет доступа"}</Alert>;
  const b = q.data;
  const cur = tr[lang] ?? {};
  const all = b.can_edit_all_fields;
  return (
    <>
      <PageHeader title={b.translations.ru?.short_name ?? b.slug} />
      <form
        data-form="admin"
        className="card max-w-3xl space-y-4 p-5"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <p className="text-sm text-muted">{b.official_name}</p>
        {!all && <Alert kind="info">Вы можете изменять контакты, адрес, режим работы и описание только своего филиала. Координаты и видимость на карте меняет администратор сайта.</Alert>}
        <div className="grid gap-4 sm:grid-cols-2">
          {(["phone", "email", "director"] as const).map((k) => (
            <label key={k} className="block text-sm font-medium">
              {{ phone: "Телефон", email: "E-mail", director: "Руководитель" }[k]}
              <input className="input mt-1" type={k === "email" ? "email" : "text"} value={String(f[k] ?? "")} onChange={(e) => setF((x) => ({ ...x, [k]: e.target.value }))} />
            </label>
          ))}
        </div>
        <fieldset disabled={!all} className="grid gap-4 rounded-lg border border-line p-3 sm:grid-cols-2">
          <legend className="px-1 text-sm font-medium">Карта {all ? "" : "(только администратор сайта)"}</legend>
          <label className="block text-sm">
            Широта
            <input className="input mt-1" inputMode="decimal" value={String(f.lat ?? "")} onChange={(e) => setF((x) => ({ ...x, lat: e.target.value }))} />
          </label>
          <label className="block text-sm">
            Долгота
            <input className="input mt-1" inputMode="decimal" value={String(f.lon ?? "")} onChange={(e) => setF((x) => ({ ...x, lon: e.target.value }))} />
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={!!f.coords_verified} onChange={(e) => setF((x) => ({ ...x, coords_verified: e.target.checked }))} /> Координаты подтверждены заказчиком
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={!!f.visible} onChange={(e) => setF((x) => ({ ...x, visible: e.target.checked }))} /> Показывать на карте
          </label>
        </fieldset>
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">Языковая версия</span>
          <LangTabs value={lang} onChange={setLang} />
        </div>
        {(["address", "hours", "description"] as const).map((k) => (
          <label key={k} className="block text-sm font-medium">
            {{ address: "Адрес", hours: "Режим работы", description: "Краткая информация о деятельности" }[k]}
            <textarea className="input mt-1 min-h-12" value={cur[k] ?? ""} onChange={(e) => setTr((t) => ({ ...t, [lang]: { ...(t[lang] ?? {}), [k]: e.target.value } }))} />
          </label>
        ))}
        {save.isError && <Alert kind="error">{(save.error as Error).message}</Alert>}
        {save.isSuccess && <Alert kind="ok">Сохранено. Изменение записано в журнал.</Alert>}
        <button type="submit" className="btn-primary" disabled={save.isPending}>Сохранить</button>
      </form>
    </>
  );
}

// ---------------- журнал действий ----------------
interface AuditRow {
  id: number;
  ts: string;
  user_email: string | null;
  action: string;
  entity: string | null;
  entity_id: string | null;
  result: string;
  ip: string | null;
  details: Record<string, unknown> | null;
}

export function AuditAdmin() {
  useDocTitle("Журнал действий");
  const [sp, setSp] = useSearchParams();
  const key = sp.toString();
  const q = useQuery({
    queryKey: ["admin-audit", key],
    queryFn: () => admin.get<{ items: AuditRow[]; total: number }>(`/admin/audit?${key}`),
    placeholderData: keepPreviousData,
  });
  const set = (k: string, v: string) => {
    const n = new URLSearchParams(sp);
    if (v) n.set(k, v);
    else n.delete(k);
    if (k !== "page") n.delete("page");
    setSp(n);
  };
  const page = Number(sp.get("page") ?? "1");
  return (
    <>
      <PageHeader title="Журнал действий" />
      <div className="mb-4 flex flex-wrap gap-3">
        <select className="input w-48" aria-label="Результат" value={sp.get("result") ?? ""} onChange={(e) => set("result", e.target.value)}>
          <option value="">Все результаты</option>
          <option value="success">Успешно</option>
          <option value="denied">Отказано</option>
          <option value="error">Ошибка</option>
        </select>
        <input className="input w-56" aria-label="Тип операции" placeholder="Операция (напр. branch)" defaultValue={sp.get("action") ?? ""} onBlur={(e) => set("action", e.target.value.trim())} />
        <input className="input w-56" aria-label="Пользователь" placeholder="E-mail пользователя" defaultValue={sp.get("user") ?? ""} onBlur={(e) => set("user", e.target.value.trim())} />
      </div>
      {q.isLoading && <Loading />}
      {q.data && (
        <>
          <p className="mb-2 text-sm text-muted">Записей: {q.data.total}</p>
          <div className="overflow-x-auto rounded-xl border border-line">
            <table className="w-full min-w-[56rem] text-sm">
              <thead className="bg-surface-2 text-left">
                <tr>
                  {["Дата и время", "Пользователь", "Операция", "Объект", "Результат", "IP", "Подробности"].map((h) => (
                    <th key={h} scope="col" className="px-3 py-2">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {q.data.items.map((r) => (
                  <tr key={r.id} className={`border-t border-line ${r.result === "denied" ? "bg-danger/5" : ""}`}>
                    <td className="whitespace-nowrap px-3 py-2">{new Date(r.ts).toLocaleString("ru-RU")}</td>
                    <td className="px-3 py-2">{r.user_email ?? "—"}</td>
                    <td className="px-3 py-2 font-mono text-xs">{r.action}</td>
                    <td className="px-3 py-2 text-xs">{r.entity} {r.entity_id ? <span className="font-mono text-muted">{r.entity_id.slice(0, 8)}…</span> : ""}</td>
                    <td className="px-3 py-2">
                      <span className={`badge ${r.result === "success" ? "border-ok/60 text-ok" : "border-danger/60 text-danger"}`}>
                        {{ success: "успешно", denied: "отказано", error: "ошибка" }[r.result] ?? r.result}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-xs">{r.ip}</td>
                    <td className="max-w-xs truncate px-3 py-2 font-mono text-xs" title={r.details ? JSON.stringify(r.details) : ""}>
                      {r.details ? JSON.stringify(r.details) : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-4 flex gap-2">
            <button type="button" className="btn-ghost" disabled={page <= 1} onClick={() => set("page", String(page - 1))}>Назад</button>
            <button type="button" className="btn-ghost" disabled={page * 50 >= q.data.total} onClick={() => set("page", String(page + 1))}>Далее</button>
          </div>
        </>
      )}
    </>
  );
}

// ---------------- пользователи ----------------
interface UserRow {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  roles: string[];
  branch: string | null;
  last_login_at: string | null;
}

export function UsersAdmin() {
  const { me } = useAuth();
  const qc = useQueryClient();
  useDocTitle("Пользователи");
  const users = useQuery({ queryKey: ["admin-users"], queryFn: () => admin.get<UserRow[]>("/admin/users") });
  const branches = useQuery({ queryKey: ["admin-branches"], queryFn: () => admin.get<BranchAdmin[]>("/admin/branches") });
  const [form, setForm] = useState({ email: "", full_name: "", role: "editor", branch_id: "" });
  const create = useMutation({
    mutationFn: () => admin.post<UserRow & { temporary_password: string }>("/admin/users", { ...form, branch_id: form.role === "branch_admin" ? form.branch_id : null }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["admin-users"] }),
  });
  const deactivate = useMutation({
    mutationFn: (id: string) => admin.post(`/admin/users/${id}/deactivate`),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["admin-users"] }),
  });
  return (
    <>
      <PageHeader title="Пользователи и роли" />
      <form
        data-form="admin"
        className="card mb-6 grid gap-3 p-4 md:grid-cols-5"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <input className="input" type="email" required placeholder="E-mail" aria-label="E-mail" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <input className="input" required minLength={3} placeholder="ФИО" aria-label="ФИО" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
        <select className="input" aria-label="Роль" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
          {Object.entries(ROLE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <select className="input" aria-label="Филиал" disabled={form.role !== "branch_admin"} value={form.branch_id} onChange={(e) => setForm({ ...form, branch_id: e.target.value })}>
          <option value="">Филиал (для админа филиала)</option>
          {branches.data?.map((b) => <option key={b.id} value={b.id}>{b.translations.ru?.short_name ?? b.slug}</option>)}
        </select>
        <button type="submit" className="btn-primary" disabled={create.isPending}>Создать</button>
        {create.isError && <div className="md:col-span-5"><Alert kind="error">{(create.error as Error).message}</Alert></div>}
        {create.data && (
          <div className="md:col-span-5">
            <Alert kind="ok">
              Пользователь создан. Временный пароль (показывается один раз, передайте безопасным способом): <code className="cipher">{create.data.temporary_password}</code>
            </Alert>
          </div>
        )}
      </form>
      {users.isLoading && <Loading />}
      <div className="overflow-x-auto rounded-xl border border-line">
        <table className="w-full min-w-[48rem] text-sm">
          <thead className="bg-surface-2 text-left">
            <tr>
              {["Пользователь", "Роли", "Филиал", "Последний вход", ""].map((h) => <th key={h} scope="col" className="px-3 py-2">{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {users.data?.map((u) => (
              <tr key={u.id} className={`border-t border-line ${u.is_active ? "" : "opacity-60"}`}>
                <td className="px-3 py-2">{u.full_name}<span className="block text-xs text-muted">{u.email}</span></td>
                <td className="px-3 py-2">{u.roles.map((r) => ROLE_LABEL[r] ?? r).join(", ")}</td>
                <td className="px-3 py-2">{u.branch ?? "—"}</td>
                <td className="px-3 py-2 text-xs">{u.last_login_at ? new Date(u.last_login_at).toLocaleString("ru-RU") : "—"}</td>
                <td className="px-3 py-2">
                  {u.is_active && u.id !== me.id ? (
                    <ConfirmButton danger title="Заблокировать пользователя?" message={`${u.email} не сможет войти в админ-панель. Действие записывается в журнал.`} onConfirm={() => deactivate.mutate(u.id)}>
                      Заблокировать
                    </ConfirmButton>
                  ) : !u.is_active ? (
                    <span className="text-xs text-muted">заблокирован</span>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
