import { useState } from "react";
import { useT } from "../../app/useT";
import { Link } from "react-router-dom";
import { useLocalePath } from "../../app/lang";
import { AccessBadge } from "../../components/ui/Badges";
import { Icon } from "../../components/ui/Icon";
import type { DocumentListItem } from "../../lib/types";

export function yearsLabel(from: number | null, to: number | null): string {
  if (!from && !to) return "";
  if (!to || from === to) return String(from ?? to);
  return `${from}–${to}`;
}

export function DocumentRow({ item }: { item: DocumentListItem }) {
  const lp = useLocalePath();
  const period = item.period_label || yearsLabel(item.year_from, item.year_to);
  return (
    <article className="card-hit flex gap-4 p-4">
      <div className="lv-img h-16 w-16 shrink-0 overflow-hidden rounded-lg bg-surface-2 sm:h-24 sm:w-28">
        {item.thumb_url ? (
          <img src={item.thumb_url} alt="" loading="lazy" decoding="async" className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full items-center justify-center text-muted" aria-hidden="true">
            <Icon name={item.file_access === "open" ? "doc" : "lock"} size={28} />
          </div>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <h3 className="text-lg leading-snug">
          <Link to={lp(`/catalog/documents/${item.id}`)} className="hit">
            {item.title}
          </Link>
        </h3>
        <p className="cipher mt-1 text-sm text-muted">{item.cipher}</p>
        {item.summary && <p className="mt-2 line-clamp-2">{item.summary}</p>}
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
          {period && <span className="font-medium">{period}</span>}
          <AccessBadge access={item.file_access} />
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
      <button type="button" className="btn-ghost btn-icon" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        <Icon name="left" size={16} />
        <span className="sr-only">{t("common.prev")}</span>
      </button>
      {nums.map((n, i) => (
        <span key={n} className="flex items-center gap-1">
          {i > 0 && n - (nums[i - 1] ?? n) > 1 && <span aria-hidden="true">…</span>}
          <button
            type="button"
            className={`${n === page ? "btn-primary" : "btn-ghost"} btn-icon`}
            aria-current={n === page ? "page" : undefined}
            onClick={() => onPage(n)}
          >
            {n}
          </button>
        </span>
      ))}
      <button type="button" className="btn-ghost btn-icon" disabled={page >= pages} onClick={() => onPage(page + 1)}>
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
      className="btn-ghost"
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
    <button type="button" className="btn-ghost" onClick={share}>
      <Icon name={done ? "check" : "share"} size={14} />
      {done ? t("common.linkCopied") : t("common.share")}
    </button>
  );
}
