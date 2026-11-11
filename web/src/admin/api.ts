// Клиент админ-API: сессия в httpOnly-cookie, CSRF double-submit в заголовке X-CSRF-Token.
import { ApiError } from "../lib/api";

function csrfToken(): string {
  const m = document.cookie.match(/(?:^|;\s*)vko_csrf=([^;]+)/);
  return m?.[1] ? decodeURIComponent(m[1]) : "";
}

export const SESSION_EXPIRED_EVENT = "vko:session-expired";

async function request<T>(method: string, path: string, body?: unknown, form?: FormData): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (method !== "GET") headers["X-CSRF-Token"] = csrfToken();
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(`/api${path}`, {
    method,
    headers,
    credentials: "same-origin",
    body: form ?? (body !== undefined ? JSON.stringify(body) : undefined),
  });
  if (res.status === 401 && !path.startsWith("/auth/login")) {
    window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = (await res.json()) as { detail?: unknown };
      if (typeof data.detail === "string") detail = data.detail;
      else if (Array.isArray(data.detail))
        detail = data.detail
          .map((d: { loc?: unknown[]; msg?: string }) => `${(d.loc ?? []).slice(1).join(".")}: ${d.msg ?? ""}`)
          .join("; ");
    } catch {
      /* не JSON */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const admin = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  patch: <T>(path: string, body: unknown) => request<T>("PATCH", path, body),
  del: (path: string) => request<void>("DELETE", path),
  upload: <T>(path: string, form: FormData) => request<T>("POST", path, undefined, form),
};

export interface Me {
  id: string;
  email: string;
  full_name: string;
  roles: string[];
  permissions: string[];
  branches: { id: string; slug: string }[];
  idle_minutes: number;
}

export const ROLE_LABEL: Record<string, string> = {
  superadmin: "Главный администратор",
  site_admin: "Администратор сайта",
  editor: "Редактор",
  archivist: "Сотрудник архива",
  branch_admin: "Администратор филиала",
  moderator: "Модератор",
  analyst: "Аналитик",
};

export const STATUS_LABEL: Record<string, string> = {
  draft: "Черновик",
  review: "На проверке",
  needs_rework: "Требует доработки",
  approved: "Одобрено",
  published: "Опубликовано",
  archived: "Архивировано",
};

export const DESC_LABEL: Record<string, string> = { public: "Публично", hidden: "Не публиковать", review: "Требует проверки" };
export const ACCESS_LABEL: Record<string, string> = { open: "Копия открыта", restricted: "Ограничен", closed: "Закрыт" };
