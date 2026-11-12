import { useSyncExternalStore } from "react";

/**
 * Версия для слабовидящих (по образцу госсайтов РК/РФ): размер шрифта, цветовая схема,
 * изображения, межбуквенный интервал. Хранится в localStorage, применяется атрибутами <html data-lv-*>
 * (public/theme-init.js применяет их до отрисовки — без мерцания).
 */
export interface LowVision {
  on: boolean;
  fs: 1 | 2 | 3;
  scheme: "bw" | "wb" | "blue";
  img: boolean;
  wide: boolean;
}

const KEY = "lowvision";
const DEFAULT: LowVision = { on: false, fs: 2, scheme: "bw", img: true, wide: false };
const listeners = new Set<() => void>();
let current: LowVision = load();

function load(): LowVision {
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? { ...DEFAULT, ...(JSON.parse(raw) as Partial<LowVision>) } : DEFAULT;
  } catch {
    return DEFAULT;
  }
}

export function applyLowVision(v: LowVision): void {
  const el = document.documentElement;
  const set = (k: string, val: string | null) => (val === null ? el.removeAttribute(k) : el.setAttribute(k, val));
  set("data-lv", v.on ? "on" : null);
  set("data-lv-fs", v.on ? String(v.fs) : null);
  set("data-lv-scheme", v.on ? v.scheme : null);
  set("data-lv-img", v.on && !v.img ? "off" : null);
  set("data-lv-ls", v.on && v.wide ? "wide" : null);
}

export function setLowVision(patch: Partial<LowVision>): void {
  current = { ...current, ...patch };
  applyLowVision(current);
  try {
    window.localStorage.setItem(KEY, JSON.stringify(current));
  } catch {
    /* хранилище запрещено — настройки действуют до перезагрузки */
  }
  listeners.forEach((l) => l());
}

export function useLowVision(): LowVision {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => current,
    () => DEFAULT,
  );
}
