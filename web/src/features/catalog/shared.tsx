import { useState } from "react";
import { useT } from "../../app/useT";
import { Link } from "react-router-dom";
import { useLocalePath } from "../../app/lang";
import { AccessBadge, DemoBadge, UnverifiedBadge } from "../../components/ui/Badges";
import { Icon } from "../../components/ui/Icon";
import type { DocumentListItem } from "../../lib/types";

export function yearsLabel(from: number | null, to: number | null): string {
  if (!from && !to) return "";
  if (!to || from === to) return String(from ?? to);
  return `${from}–${to}`;
}

export function DocumentRow({ item }: { item: DocumentListItem }) {
  const { t } = useT();
  const lp = useLocalePath();
  const period = item.period_label || yearsLabel(item.year_from, item.year_to);
  return (
    <article className="card flex gap-4 p-4 transition-shadow hover:shadow-md">
      <div className="hidden h-24 w-28 shrink-0 overflow-hidden rounded-lg border border-line bg-surface-2 sm:block">
        {item.thumb_url ? (
          <img src={item.thumb_url} alt="" loading="lazy" decoding="async" className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full items-center justify-center text-muted" aria-hidden="true">
            <Icon name={item.file_access === "open" ? "doc" : "lock"} size={28} />
          </div>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <h3 className="font-serif text-lg leading-snug">
          <Link to={lp(`/catalog/documents/${item.id}`)} className="text-ink hover:text-primary">
            {item.title}
          </Link>
        </h3>
        <p className="cipher mt-1 text-xs text-muted">{item.cipher}</p>
        {item.summary && <p className="mt-2 line-clamp-2 text-sm">{item.summary}</p>}
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
          {period && <span className="badge border-line text-ink">{period}</span>}
          <span className="badge border-line text-ink">{t(`docTypes.${item.doc_type}`)}</span>
          <AccessBadge access={item.file_access} />
          {!item.date_verified && <UnverifiedBadge label={t("catalog.unverifiedDate")} />}
          {item.is_personal_fund && <span className="badge border-accent/50 text-accent">{t("doc.personalFund")}</span>}
          {item.branch && <span className="text-muted">{item.branch.name}</span>}
          {item.is_demo && <DemoBadge short />}
          {item.translation.is_fallback && (
            <span className="badge border-line text-muted" title={t("translation.fallback", { lang: item.translation.lang })}>
              {item.translation.lang.toUpperCase()}
            </span>
          )}
        </div>
      </div>
    </article>
  );
}

export function Pagination({ page, pages, onPage }: { page: number; pages: number; onPage: (p: number) => void }) {
  const { t } = useT();
  if (pages <= 1) return null;
  const nums = Array.from(new Set([1, page - 1, page, page + 1, pages])).filter((n) => n >= 1 && n <= pages);
  return (
    <nav aria-label={t("catalog.pagination")} className="mt-6 flex flex-wrap items-center justify-center gap-1">
      <button type="button" className="btn-ghost" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        <Icon name="left" size={16} />
        <span className="sr-only">{t("common.prev")}</span>
      </button>
      {nums.map((n, i) => (
        <span key={n} className="flex items-center gap-1">
          {i > 0 && n - (nums[i - 1] ?? n) > 1 && <span aria-hidden="true">…</span>}
          <button
            type="button"
            className={n === page ? "btn-primary" : "btn-ghost"}
            aria-current={n === page ? "page" : undefined}
            onClick={() => onPage(n)}
          >
            {n}
          </button>
        </span>
      ))}
      <button type="button" className="btn-ghost" disabled={page >= pages} onClick={() => onPage(page + 1)}>
        <Icon name="right" size={16} />
        <span className="sr-only">{t("common.next")}</span>
      </button>
      <p className="sr-only" aria-live="polite">
        {t("catalog.page", { page, pages })}
      </p>
    </nav>
  );
}

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

export function CopyButton({ text, label }: { text: string; label: string }) {
  const { t } = useT();
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      className="btn-ghost px-2 py-1 text-xs"
      onClick={async () => {
        if (await copyText(text)) {
          setDone(true);
          window.setTimeout(() => setDone(false), 2000);
        }
      }}
    >
      <Icon name={done ? "check" : "copy"} size={14} />
      {done ? t("common.copied") : label}
      <span className="sr-only" aria-live="polite">
        {done ? t("common.copied") : ""}
      </span>
    </button>
  );
}

export function ShareButton({ title }: { title: string }) {
  const { t } = useT();
  const [done, setDone] = useState(false);
  const share = async () => {
    const url = window.location.href;
    if (typeof navigator.share === "function") {
      try {
        await navigator.share({ title, url });
        return;
      } catch {
        /* пользователь отменил — копируем ссылку */
      }
    }
    if (await copyText(url)) {
      setDone(true);
      window.setTimeout(() => setDone(false), 2000);
    }
  };
  return (
    <button type="button" className="btn-ghost px-2 py-1 text-xs" onClick={share}>
      <Icon name={done ? "check" : "share"} size={14} />
      {done ? t("common.linkCopied") : t("common.share")}
    </button>
  );
}
