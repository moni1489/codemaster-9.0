import { useEffect } from "react";
import { useT } from "./useT";

/** <title> и meta description для страницы (ТЗ §7.5). */
export function useTitle(title: string | undefined, description?: string | null): void {
  const { t } = useT();
  useEffect(() => {
    const site = t("org.short");
    document.title = title ? `${title} — ${site}` : site;
    const meta = document.querySelector('meta[name="description"]');
    if (meta && description) meta.setAttribute("content", description.slice(0, 300));
    // Open Graph для «поделиться»
    const og = (prop: string, value: string) => {
      let el = document.querySelector(`meta[property="${prop}"]`);
      if (!el) {
        el = document.createElement("meta");
        el.setAttribute("property", prop);
        document.head.appendChild(el);
      }
      el.setAttribute("content", value);
    };
    og("og:title", document.title);
    og("og:url", window.location.href);
    if (description) og("og:description", description.slice(0, 300));
  }, [title, description, t]);
}
