import { useTranslation } from "react-i18next";
import { useLang } from "./lang";

/** t(), жёстко привязанный к языку из URL: интерфейс всегда совпадает с префиксом /kk|/ru|/en. */
export function useT() {
  const lang = useLang();
  return useTranslation(undefined, { lng: lang });
}
