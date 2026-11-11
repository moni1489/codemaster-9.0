import type { Lang } from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

type Params = Record<string, string | number | boolean | string[] | undefined | null>;

export function buildQuery(params: Params): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    if (Array.isArray(v)) v.forEach((x) => q.append(k, x));
    else q.set(k, String(v));
  }
  const s = q.toString();
  return s ? `?${s}` : "";
}

/** GET к публичному API. Язык передаётся всегда — сервер отдаёт перевод или оригинал с флагом фолбэка. */
export async function apiGet<T>(path: string, lang: Lang, params: Params = {}): Promise<T> {
  const res = await fetch(`/api${path}${buildQuery({ ...params, lang })}`, {
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* тело не JSON */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}
