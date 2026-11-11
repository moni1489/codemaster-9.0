import { useT } from "../../app/useT";
import { Link } from "react-router-dom";
import { useLocalePath } from "../../app/lang";

export interface Crumb {
  label: string;
  to?: string;
}

export function Breadcrumbs({ items }: { items: Crumb[] }) {
  const { t } = useT();
  const lp = useLocalePath();
  const all: Crumb[] = [{ label: t("nav.home"), to: "/" }, ...items];
  return (
    <nav aria-label={t("a11y.breadcrumbs")} className="mb-4 text-sm">
      <ol className="flex flex-wrap items-center gap-1 text-muted">
        {all.map((c, i) => (
          <li key={`${c.label}-${i}`} className="flex min-w-0 max-w-full items-center gap-1">
            {i > 0 && <span aria-hidden="true">/</span>}
            {c.to && i < all.length - 1 ? (
              <Link to={lp(c.to)} className="truncate hover:underline">
                {c.label}
              </Link>
            ) : (
              <span aria-current={i === all.length - 1 ? "page" : undefined} className="truncate text-ink">
                {c.label}
              </span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
