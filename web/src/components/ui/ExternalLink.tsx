import type { ReactNode } from "react";
import { useT } from "../../app/useT";
import { Icon } from "./Icon";

/** Явно помеченная внешняя ссылка (иконка ↗ + текст для скринридера), rel="noopener noreferrer". */
export function ExternalLink({ href, children, className }: { href: string; children: ReactNode; className?: string }) {
  const { t } = useT();
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={className ?? "inline-flex items-center gap-1"}>
      {children}
      <Icon name="external" size={14} />
      <span className="sr-only">({t("a11y.external")})</span>
    </a>
  );
}
