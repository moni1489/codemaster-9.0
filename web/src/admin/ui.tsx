import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { useTheme } from "../app/theme";
import { Logo } from "../components/layout/Logo";
import { Icon } from "../components/ui/Icon";
import { admin, ROLE_LABEL, STATUS_LABEL } from "./api";
import { useAuth } from "./auth";

const NAV: { to: string; label: string; perms: string[] }[] = [
  { to: "/admin", label: "Сводка", perms: [] },
  { to: "/admin/catalog", label: "Каталог", perms: ["catalog.read_all", "catalog.edit"] },
  { to: "/admin/catalog/import", label: "Импорт / экспорт", perms: ["catalog.import", "catalog.export"] },
  { to: "/admin/news", label: "Новости", perms: ["content.edit", "content.review"] },
  { to: "/admin/pages", label: "Страницы", perms: ["content.edit", "content.review"] },
  { to: "/admin/faq", label: "FAQ", perms: ["content.edit", "content.review"] },
  { to: "/admin/branches", label: "Филиалы", perms: ["branches.edit_any", "branches.edit_own"] },
  { to: "/admin/users", label: "Пользователи", perms: ["users.manage"] },
  { to: "/admin/audit", label: "Журнал действий", perms: ["audit.read"] },
  { to: "/admin/feedback", label: "Отзывы", perms: ["content.review", "users.manage"] },
];

export function AdminLayout() {
  const { me, can, logout } = useAuth();
  const [theme, toggle] = useTheme();
  const [open, setOpen] = useState(false);
  // Пункты меню скрываются для удобства; права всё равно проверяет сервер на каждый запрос
  const items = NAV.filter((n) => n.perms.length === 0 || n.perms.some(can));
  return (
    <div className="flex min-h-screen flex-col bg-bg lg:flex-row">
      <a href="#admin-main" className="sr-only-focusable absolute left-2 top-2 z-50 rounded bg-primary px-3 py-2 text-primary-ink">
        Перейти к содержанию
      </a>
      <aside className="border-b border-line bg-surface lg:w-64 lg:border-b-0 lg:border-r">
        <div className="flex items-center justify-between gap-2 p-4">
          <Link to="/admin" className="flex items-center gap-2 text-ink no-underline">
            <Logo className="h-9 w-9" />
            <span className="font-serif font-bold leading-tight">
              Админ-панель
              <span className="block text-xs font-normal text-muted">ГА ВКО</span>
            </span>
          </Link>
          <button type="button" className="btn-ghost px-2 lg:hidden" aria-expanded={open} aria-controls="admin-nav" aria-label="Меню" onClick={() => setOpen((v) => !v)}>
            <Icon name={open ? "close" : "menu"} />
          </button>
        </div>
        <nav id="admin-nav" aria-label="Разделы админ-панели" className={clsx("px-3 pb-4 lg:block", open ? "block" : "hidden")}>
          <ul className="space-y-1">
            {items.map((n) => (
              <li key={n.to}>
                <NavLink
                  to={n.to}
                  end={n.to === "/admin"}
                  onClick={() => setOpen(false)}
                  className={({ isActive }) =>
                    clsx("block rounded-md px-3 py-2 text-sm no-underline", isActive ? "bg-primary/10 font-medium text-primary" : "text-ink hover:bg-surface-2")
                  }
                >
                  {n.label}
                </NavLink>
              </li>
            ))}
          </ul>
          <div className="mt-6 border-t border-line pt-4 text-sm">
            <p className="font-medium">{me.full_name}</p>
            <p className="break-all text-xs text-muted">{me.email}</p>
            <p className="mt-1 flex flex-wrap gap-1">
              {me.roles.map((r) => (
                <span key={r} className="badge border-line">{ROLE_LABEL[r] ?? r}</span>
              ))}
            </p>
            {me.branches.length > 0 && <p className="mt-1 text-xs text-muted">Филиал: {me.branches.map((b) => b.slug).join(", ")}</p>}
            <div className="mt-3 flex gap-2">
              <button type="button" className="btn-ghost px-2 py-1 text-xs" onClick={toggle} aria-label="Сменить тему">
                <Icon name={theme === "dark" ? "sun" : "moon"} size={16} />
              </button>
              <a href="/ru" className="btn-ghost px-2 py-1 text-xs">На сайт</a>
              <button type="button" className="btn-ghost px-2 py-1 text-xs" onClick={() => void logout()}>
                Выйти
              </button>
            </div>
          </div>
        </nav>
      </aside>
      <main id="admin-main" tabIndex={-1} className="min-w-0 flex-1 p-4 outline-none lg:p-8">
        <Outlet />
      </main>
    </div>
  );
}

const STATUS_STYLE: Record<string, string> = {
  draft: "border-line text-muted",
  review: "border-warn/60 bg-warn/10 text-warn",
  needs_rework: "border-danger/60 bg-danger/10 text-danger",
  approved: "border-primary/60 bg-primary/10 text-primary",
  published: "border-ok/60 bg-ok/10 text-ok",
  archived: "border-line bg-surface-2 text-muted",
};

export function StatusBadge({ status }: { status: string }) {
  return <span className={clsx("badge", STATUS_STYLE[status] ?? "border-line")}>{STATUS_LABEL[status] ?? status}</span>;
}

export function PageHeader({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
      <h1 className="text-2xl sm:text-3xl">{title}</h1>
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  );
}

export function Alert({ kind, children }: { kind: "error" | "ok" | "warn" | "info"; children: ReactNode }) {
  const style = {
    error: "border-danger/50 bg-danger/10",
    ok: "border-ok/50 bg-ok/10",
    warn: "border-warn/50 bg-warn/10",
    info: "border-line bg-surface-2",
  }[kind];
  return (
    <div role={kind === "error" ? "alert" : "status"} className={clsx("my-3 rounded-lg border px-3 py-2 text-sm", style)}>
      {children}
    </div>
  );
}

/** Кнопка с подтверждением (Д §3.3: предупреждение перед опасными действиями администратора). */
export function ConfirmButton({
  children,
  title,
  message,
  onConfirm,
  danger = false,
  disabled,
  requireText,
}: {
  children: ReactNode;
  title: string;
  message: ReactNode;
  onConfirm: () => void;
  danger?: boolean;
  disabled?: boolean;
  requireText?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [typed, setTyped] = useState("");
  useEffect(() => setTyped(""), [requireText]);
  return (
    <>
      <button type="button" className={danger ? "btn border border-danger/60 text-danger hover:bg-danger/10" : "btn-primary"} disabled={disabled} onClick={() => ref.current?.showModal()}>
        {children}
      </button>
      <dialog ref={ref} className="w-[min(32rem,90vw)] rounded-xl border border-line bg-surface p-0 text-ink backdrop:bg-black/50" aria-labelledby="confirm-title">
        <div className="p-5">
          <h2 id="confirm-title" className="text-xl">{title}</h2>
          <div className="mt-3 text-sm">{message}</div>
          {requireText && (
            <label className="mt-3 block text-sm">
              Для подтверждения введите: <code className="cipher">{requireText}</code>
              <input className="input mt-1" value={typed} onChange={(e) => setTyped(e.target.value)} />
            </label>
          )}
          <div className="mt-5 flex justify-end gap-2">
            <button type="button" className="btn-ghost" onClick={() => ref.current?.close()}>
              Отмена
            </button>
            <button
              type="button"
              className={danger ? "btn bg-danger text-white" : "btn-primary"}
              disabled={!!requireText && typed.trim() !== requireText}
              onClick={() => {
                ref.current?.close();
                onConfirm();
              }}
            >
              Подтвердить
            </button>
          </div>
        </div>
      </dialog>
    </>
  );
}

const ACTIONS: { from: string[]; to: string; label: string; perms: string[]; confirm?: string }[] = [
  { from: ["draft", "needs_rework"], to: "review", label: "Отправить на проверку", perms: ["content.submit"] },
  { from: ["review", "approved"], to: "needs_rework", label: "Вернуть на доработку", perms: ["content.review"] },
  { from: ["review"], to: "approved", label: "Одобрить", perms: ["content.review"] },
  { from: ["review"], to: "published", label: "Одобрить и опубликовать", perms: ["content.review", "content.publish"], confirm: "Материал станет виден посетителям сайта." },
  { from: ["approved"], to: "published", label: "Опубликовать", perms: ["content.publish"], confirm: "Материал станет виден посетителям сайта." },
  { from: ["published"], to: "draft", label: "Снять с публикации", perms: ["content.publish"], confirm: "Материал перестанет быть виден на сайте." },
  { from: ["published"], to: "archived", label: "В архив", perms: ["content.publish"], confirm: "Материал будет скрыт и перемещён в архив." },
  { from: ["archived"], to: "draft", label: "Вернуть в черновики", perms: ["content.publish"] },
];

interface Version {
  version: number;
  status: string;
  changed_at: string;
  author: string | null;
  reviewer: string | null;
  comment: string | null;
}

/** Согласование (ТЗ §6.7): доступные переходы, комментарий, история версий. */
export function WorkflowPanel({ entity, id, status, invalidate }: { entity: string; id: string; status: string; invalidate: unknown[][] }) {
  const { can } = useAuth();
  const qc = useQueryClient();
  const [comment, setComment] = useState("");
  const versions = useQuery({
    queryKey: ["versions", entity, id],
    queryFn: () => admin.get<Version[]>(`/admin/workflow/${entity}/${id}/versions`),
  });
  const move = useMutation({
    mutationFn: (to: string) => admin.post<{ status: string; warning: string | null }>(`/admin/workflow/${entity}/${id}`, { to, comment: comment || null }),
    onSuccess: () => {
      setComment("");
      invalidate.forEach((key) => void qc.invalidateQueries({ queryKey: key }));
      void qc.invalidateQueries({ queryKey: ["versions", entity, id] });
    },
  });
  const available = ACTIONS.filter((a) => a.from.includes(status) && a.perms.every(can));
  return (
    <section className="card space-y-3 p-4" aria-labelledby="wf-h">
      <h2 id="wf-h" className="flex items-center justify-between gap-2 text-lg">
        Согласование <StatusBadge status={status} />
      </h2>
      {available.length > 0 ? (
        <>
          <label className="block text-sm">
            Комментарий (сохраняется в истории)
            <textarea className="input mt-1 min-h-16" value={comment} maxLength={1000} onChange={(e) => setComment(e.target.value)} />
          </label>
          <div className="flex flex-wrap gap-2">
            {available.map((a) =>
              a.confirm ? (
                <ConfirmButton key={a.to} title={a.label} message={a.confirm} onConfirm={() => move.mutate(a.to)} disabled={move.isPending}>
                  {a.label}
                </ConfirmButton>
              ) : (
                <button key={a.to} type="button" className="btn-ghost" disabled={move.isPending} onClick={() => move.mutate(a.to)}>
                  {a.label}
                </button>
              ),
            )}
          </div>
        </>
      ) : (
        <p className="text-sm text-muted">Для текущего статуса у вашей роли нет доступных действий.</p>
      )}
      {move.isError && <Alert kind="error">{(move.error as Error).message}</Alert>}
      {move.data?.warning && <Alert kind="warn">{move.data.warning}</Alert>}
      <details>
        <summary className="cursor-pointer text-sm font-medium">История версий ({versions.data?.length ?? 0})</summary>
        <ol className="mt-2 space-y-2 text-sm">
          {versions.data?.map((v) => (
            <li key={v.version} className="border-l-2 border-line pl-3">
              <p>
                <strong>v{v.version}</strong> · <StatusBadge status={v.status} /> · {new Date(v.changed_at).toLocaleString("ru-RU")}
              </p>
              <p className="text-xs text-muted">
                {v.author && <>автор: {v.author} </>}
                {v.reviewer && <>согласующий: {v.reviewer}</>}
              </p>
              {v.comment && <p className="text-xs">«{v.comment}»</p>}
            </li>
          ))}
        </ol>
      </details>
    </section>
  );
}

export function LangTabs({ value, onChange }: { value: string; onChange: (l: string) => void }) {
  return (
    <div role="tablist" aria-label="Язык версии" className="flex gap-1">
      {(["ru", "kk", "en"] as const).map((l) => (
        <button key={l} type="button" role="tab" aria-selected={value === l} className={value === l ? "btn-primary px-3 py-1" : "btn-ghost px-3 py-1"} onClick={() => onChange(l)}>
          {l.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
