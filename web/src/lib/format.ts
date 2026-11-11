import type { Lang } from "./types";

const LOCALE: Record<Lang, string> = { ru: "ru-RU", kk: "kk-KZ", en: "en-GB" };

export function formatDate(iso: string | null | undefined, lang: Lang, withYear = true): string {
  if (!iso) return "";
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(LOCALE[lang], { day: "numeric", month: "long", ...(withYear ? { year: "numeric" } : {}) });
}

export function monthName(month: number, lang: Lang): string {
  return new Date(2026, month - 1, 1).toLocaleDateString(LOCALE[lang], { month: "long" });
}
