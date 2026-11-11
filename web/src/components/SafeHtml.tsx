import DOMPurify from "dompurify";
import { useMemo } from "react";

// Внешние ссылки открываются в новой вкладке без доступа к window.opener
DOMPurify.addHook("afterSanitizeAttributes", (node) => {
  if (node.tagName === "A") {
    const href = node.getAttribute("href") ?? "";
    if (/^https?:\/\//i.test(href)) {
      node.setAttribute("target", "_blank");
      node.setAttribute("rel", "noopener noreferrer");
    }
  }
});

/** Вывод rich-text из CMS: уже очищен bleach на сервере, здесь — второй рубеж (DOMPurify). */
export function SafeHtml({ html, className }: { html: string; className?: string }) {
  const clean = useMemo(
    () =>
      DOMPurify.sanitize(html, {
        USE_PROFILES: { html: true },
        FORBID_TAGS: ["style", "script", "iframe", "form", "input", "button", "img"],
        FORBID_ATTR: ["style", "onerror", "onclick"],
      }),
    [html],
  );
  return <div className={className ?? "prose"} dangerouslySetInnerHTML={{ __html: clean }} />;
}
