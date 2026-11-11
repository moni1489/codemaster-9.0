import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useLocation, useParams } from "react-router-dom";
import { LANGS, type Lang } from "../lib/types";

export function isLang(v: string | undefined): v is Lang {
  return !!v && (LANGS as string[]).includes(v);
}

/** Текущий язык из URL-префикса. */
export function useLang(): Lang {
  const { lang } = useParams();
  return isLang(lang) ? lang : "ru";
}

/** Синхронизирует i18next и <html lang> с URL. */
export function useSyncLang(): Lang {
  const lang = useLang();
  const { i18n } = useTranslation();
  useEffect(() => {
    if (i18n.language !== lang) void i18n.changeLanguage(lang);
    document.documentElement.lang = lang === "kk" ? "kk" : lang;
  }, [lang, i18n]);
  return lang;
}

/** Тот же маршрут и query на другом языке (Д §3.3: сохранять открытый раздел и фильтры). */
export function useSwitchLangHref(): (target: Lang) => string {
  const location = useLocation();
  return (target: Lang) => {
    const parts = location.pathname.split("/");
    if (isLang(parts[1])) parts[1] = target;
    else parts.splice(1, 0, target);
    return `${parts.join("/") || `/${target}`}${location.search}${location.hash}`;
  };
}

/** Ссылка внутри текущего языка. */
export function useLocalePath(): (path: string) => string {
  const lang = useLang();
  return (path: string) => `/${lang}${path.startsWith("/") ? path : `/${path}`}`.replace(/\/$/, "") || `/${lang}`;
}
