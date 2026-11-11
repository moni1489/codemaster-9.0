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
  }, [title, description, t]);
}
