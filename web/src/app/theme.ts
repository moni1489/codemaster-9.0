import { useCallback, useSyncExternalStore } from "react";

export type Theme = "light" | "dark";
const KEY = "theme";
const listeners = new Set<() => void>();

function read(): Theme {
  const attr = document.documentElement.getAttribute("data-theme");
  return attr === "dark" ? "dark" : "light";
}

function save(theme: Theme): void {
  try {
    window.localStorage.setItem(KEY, theme);
  } catch {
    /* приватный режим / запрет хранилища — тема работает до перезагрузки */
  }
}

export function setTheme(theme: Theme): void {
  document.documentElement.setAttribute("data-theme", theme);
  save(theme);
  listeners.forEach((l) => l());
}

/** Тема без перезагрузки страницы: меняется только атрибут <html data-theme>. Маршрут и запрос не трогаются. */
export function useTheme(): [Theme, () => void] {
  const theme = useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    read,
    () => "light" as Theme,
  );
  const toggle = useCallback(() => setTheme(read() === "dark" ? "light" : "dark"), []);
  return [theme, toggle];
}
