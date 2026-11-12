import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, NavLink, useParams } from "react-router-dom";
import { useLang, useLocalePath } from "../../app/lang";
import { useT } from "../../app/useT";
import { useTitle } from "../../app/useTitle";
import { SafeHtml } from "../../components/SafeHtml";
import { DemoBadge, TranslationNotice } from "../../components/ui/Badges";
import { Breadcrumbs } from "../../components/ui/Breadcrumbs";
import { ExternalLink } from "../../components/ui/ExternalLink";
import { Icon } from "../../components/ui/Icon";
import { ErrorState, Loading } from "../../components/ui/States";
import { apiGet } from "../../lib/api";
import { formatDate, monthName } from "../../lib/format";
import type { Attachment, LegalAct, MemorialDate, PageLink, PageOut, PriceData } from "../../lib/types";

type Section = "about" | "services" | "visitors";
const SECTION_NAV_KEY: Record<Section, string> = { about: "nav.about", services: "nav.services", visitors: "nav.visitors" };

/** /about → about; /services/paid → services-paid */
export function slugFor(section: Section, sub?: string): string {
  return sub ? `${section}-${sub}` : section;
}

function routeFor(slug: string): string {
  const [section, ...rest] = slug.split("-");
  return rest.length ? `/${section}/${rest.join("-")}` : `/${section}`;
}

export function AttachmentList({ items, title }: { items: Attachment[]; title?: string }) {
  const { t } = useT();
  if (!items.length) return null;
  return (
    <section className="mt-8" aria-labelledby="attachments-h">
      <h2 id="attachments-h" className="text-xl">
        {title ?? t("info.documents")}
      </h2>
      <ul className="mt-3 grid gap-2 md:grid-cols-2">
        {items.map((a) => (
          <li key={a.url + a.title}>
            {a.external ? (
              <ExternalLink href={a.url} className="card flex h-full items-start gap-3 p-3 no-underline hover:border-primary">
                <Icon name="external" size={20} className="mt-0.5 shrink-0 text-primary" />
                <span className="flex-1">
                  <span className="block text-ink">{a.title}</span>
                  <span className="text-xs text-muted">{new URL(a.url).hostname}</span>
                  {!a.verified && (
                    <span className="mt-1 block text-xs text-warn">⚠ {t("info.unverifiedLink")}</span>
                  )}
                </span>
              </ExternalLink>
            ) : (
              <a href={a.url} target="_blank" rel="noopener" className="card flex h-full items-start gap-3 p-3 no-underline hover:border-primary">
                <Icon name="doc" size={20} className="mt-0.5 shrink-0 text-primary" />
                <span className="flex-1">
                  <span className="block text-ink">{a.title}</span>
                  <span className="text-xs text-muted">
                    {t("info.pdf")}
                    {a.lang ? ` · ${a.lang.toUpperCase()}` : ""}
                  </span>
                </span>
              </a>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function SectionNav({ section, current }: { section: Section; current: string }) {
  const { t } = useT();
  const lang = useLang();
  const lp = useLocalePath();
  const q = useQuery({
    queryKey: ["pages", section, lang],
    queryFn: () => apiGet<PageLink[]>("/pages", lang, { section }),
    staleTime: 5 * 60_000,
  });
  const extra =
    section === "visitors"
      ? [
          { to: "/visitors/memorial-dates", title: t("info.memorialTitle") },
          { to: "/faq", title: t("nav.faq") },
        ]
      : [];
  return (
    <nav aria-label={t("info.inSection")} className="card p-3">
      <p className="px-2 pb-2 text-sm font-semibold text-muted">{t(SECTION_NAV_KEY[section])}</p>
      <ul className="space-y-1">
        {(q.data ?? []).map((p) => (
          <li key={p.slug}>
            <NavLink
              to={lp(routeFor(p.slug))}
              end
              aria-current={p.slug === current ? "page" : undefined}
              className={`block rounded-md px-2 py-1.5 text-sm no-underline ${p.slug === current ? "bg-primary/10 font-medium text-primary" : "text-ink hover:bg-surface-2"}`}
            >
              {p.title}
            </NavLink>
          </li>
        ))}
        {extra.map((e) => (
          <li key={e.to}>
            <Link to={lp(e.to)} className="block rounded-md px-2 py-1.5 text-sm text-ink no-underline hover:bg-surface-2">
              {e.title}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export function NoOrdersBanner({ variant = "price" }: { variant?: "price" | "applications" }) {
  const { t } = useT();
  return (
    <div role="note" className="flex gap-3 rounded-xl border-2 border-warn/60 bg-warn/10 p-4">
      <Icon name="info" size={24} className="shrink-0 text-warn" />
      <div>
        <p className="font-semibold">{t("info.noOrdersBanner")}</p>
        <p className="mt-1 text-sm">{variant === "price" ? t("info.noOrdersText") : t("info.noApplicationsText")}</p>
      </div>
    </div>
  );
}

function PriceBlock({ data }: { data: PriceData }) {
  const { t } = useT();
  const lang = useLang();
  return (
    <section className="mt-8" aria-labelledby="price-h">
      <h2 id="price-h" className="text-2xl">
        {t("info.priceExtract")}
      </h2>
      <div className="card mt-3 p-4 text-sm">
        <p className="font-semibold">{t("info.actTitle")}</p>
        <p className="mt-1">
          {t("info.act", { kind: data.act.kind, issuer: data.act.issuer, date: formatDate(data.act.date, lang), number: data.act.number })}
          {" — «"}
          {data.act.title}»
        </p>
        <p className="mt-2 text-muted">{data.act.basis}</p>
        <p className="mt-2 text-muted">{data.act.in_force}</p>
      </div>
      <p className="mt-3 flex gap-2 text-sm text-muted" role="note">
        <Icon name="alert" size={16} className="mt-0.5 shrink-0" /> {data.transcription_note}
      </p>
      {data.sections.map((s) => (
        <div key={s.no} className="mt-6">
          <h3 className="text-xl">
            {s.no}. {s.title}
          </h3>
          <div className="mt-2 overflow-x-auto rounded-xl border border-line">
            <table className="w-full min-w-[40rem] border-collapse text-sm">
              <caption className="sr-only">
                {t("info.priceExtract")}: {s.no}. {s.title}
              </caption>
              <thead className="bg-surface-2">
                <tr>
                  <th scope="col" className="w-24 px-3 py-2 text-left">{t("info.priceIndex")}</th>
                  <th scope="col" className="px-3 py-2 text-left">{t("info.priceName")}</th>
                  <th scope="col" className="w-40 px-3 py-2 text-left">{t("info.priceUnit")}</th>
                  <th scope="col" className="w-32 px-3 py-2 text-right">{t("info.pricePrice", { currency: data.currency })}</th>
                </tr>
              </thead>
              <tbody>
                {s.rows.map((r) => (
                  <tr key={r.index} className={`border-t border-line ${r.price ? "" : "bg-surface-2/50 font-medium"}`}>
                    <td className="whitespace-nowrap px-3 py-2 align-top font-mono text-xs">{r.index}</td>
                    <td className="px-3 py-2 align-top">{r.name}</td>
                    <td className="px-3 py-2 align-top text-muted">{r.unit}</td>
                    <td className="whitespace-nowrap px-3 py-2 text-right align-top tabular-nums">{r.price}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {s.footnote && <p className="mt-2 text-sm text-muted">{s.footnote}</p>}
        </div>
      ))}
      <h3 className="mt-8 text-xl">{t("info.priceOther")}</h3>
      <ul className="mt-2 space-y-1 text-sm">
        {data.other_sections.map((o) => (
          <li key={o.no}>
            {o.no}. {o.title} <span className="text-muted">({t("info.pricePages", { pages: o.pages })})</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function LegalTable({ acts }: { acts: LegalAct[] }) {
  const { t } = useT();
  const link = (a: LegalAct) => (
    <>
      {a.local ? (
        <a href={a.url} target="_blank" rel="noopener">{t("info.pdf")}</a>
      ) : (
        <ExternalLink href={a.url}>{new URL(a.url).hostname}</ExternalLink>
      )}
      {!a.verified && <span className="mt-1 block text-xs text-warn">⚠ {t("info.unverifiedLink")}</span>}
      {a.note && <span className="mt-1 block text-xs text-muted">{a.note}</span>}
    </>
  );
  return (
    <>
    {/* телефон: карточки вместо широкой таблицы */}
    <ul className="mt-6 space-y-3 md:hidden">
      {acts.map((a) => (
        <li key={a.title} className="card p-3 text-sm">
          <p className="font-medium">{a.title}</p>
          <p className="mt-1 text-muted">{a.requisites}</p>
          <div className="mt-2">{link(a)}</div>
        </li>
      ))}
    </ul>
    <div className="mt-6 hidden overflow-x-auto rounded-xl border border-line md:block">
      <table className="w-full border-collapse text-sm">
        <thead className="bg-surface-2">
          <tr>
            <th scope="col" className="px-3 py-2 text-left">{t("info.legalAct")}</th>
            <th scope="col" className="px-3 py-2 text-left">{t("info.legalReq")}</th>
            <th scope="col" className="px-3 py-2 text-left">{t("info.legalLink")}</th>
          </tr>
        </thead>
        <tbody>
          {acts.map((a) => (
            <tr key={a.title} className="border-t border-line">
              <td className="px-3 py-2 align-top">{a.title}</td>
              <td className="px-3 py-2 align-top text-muted">{a.requisites}</td>
              <td className="px-3 py-2 align-top">
                {a.local ? (
                  <a href={a.url} target="_blank" rel="noopener">{t("info.pdf")}</a>
                ) : (
                  <ExternalLink href={a.url}>{new URL(a.url).hostname}</ExternalLink>
                )}
                {!a.verified && <span className="mt-1 block text-xs text-warn">⚠ {t("info.unverifiedLink")}</span>}
                {a.note && <span className="mt-1 block text-xs text-muted">{a.note}</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
    </>
  );
}

export function InfoPage({ section }: { section: Section }) {
  const { sub } = useParams();
  const { t } = useT();
  const lang = useLang();
  const slug = slugFor(section, sub);
  const q = useQuery({
    queryKey: ["page", slug, lang],
    queryFn: () => apiGet<PageOut>(`/pages/${encodeURIComponent(slug)}`, lang),
    retry: false,
  });
  const page = q.data;
  useTitle(page?.title, page?.meta_description);

  const crumbs = [
    ...(section === "about" && !sub ? [] : [{ label: t(SECTION_NAV_KEY[section]), to: `/${section}` }]),
    { label: page?.title ?? "…" },
  ];
  const isPaid = slug === "services-paid";
  const isState = slug === "services-state";

  return (
    <div className="container-page py-6">
      <Breadcrumbs items={crumbs} />
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[16rem_1fr]">
        <aside className="order-2 lg:order-1">
          <SectionNav section={section} current={slug} />
        </aside>
        <article className="order-1 min-w-0 lg:order-2">
          {q.isLoading && <Loading />}
          {q.isError && <ErrorState error={q.error} onRetry={() => void q.refetch()} />}
          {page && (
            <>
              <header className="space-y-3">
                <h1 className="text-3xl leading-tight">{page.title}</h1>
                <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
                  {page.actualized_at && <span>{t("info.actualized", { date: formatDate(page.actualized_at, lang) })}</span>}
                  {page.is_demo && <DemoBadge />}
                </div>
                <TranslationNotice info={page.translation} />
                {page.is_demo && <p className="text-sm text-muted">{t("info.demoText")}</p>}
              </header>
              {(isPaid || isState) && (
                <div className="mt-6">
                  <NoOrdersBanner variant={isPaid ? "price" : "applications"} />
                </div>
              )}
              {page.body && <SafeHtml html={page.body} className="prose mt-6" />}
              {page.data?.acts && <LegalTable acts={page.data.acts} />}
              {isPaid && page.data?.sections && <PriceBlock data={page.data as PriceData} />}
              <AttachmentList items={page.attachments} title={isState ? t("info.officialChannels") : undefined} />
            </>
          )}
        </article>
      </div>
    </div>
  );
}

/** Хаб раздела «Услуги» / «Посетителям»: карточки страниц раздела. */
export function SectionHub({ section }: { section: "services" | "visitors" }) {
  const { t } = useT();
  const lang = useLang();
  const lp = useLocalePath();
  const title = section === "services" ? t("info.servicesTitle") : t("info.visitorsTitle");
  const lead = section === "services" ? t("info.servicesLead") : t("info.visitorsLead");
  useTitle(title, lead);
  const q = useQuery({
    queryKey: ["pages", section, lang],
    queryFn: () => apiGet<PageLink[]>("/pages", lang, { section }),
  });
  const extra =
    section === "visitors"
      ? [
          { to: "/visitors/memorial-dates", title: t("info.memorialTitle") },
          { to: "/faq", title: t("nav.faq") },
          { to: "/branches", title: t("nav.branches") },
        ]
      : [];
  return (
    <div className="container-page py-6">
      <Breadcrumbs items={[{ label: t(SECTION_NAV_KEY[section]) }]} />
      <h1 className="text-3xl">{title}</h1>
      <p className="mt-2 max-w-3xl text-muted">{lead}</p>
      {section === "services" && (
        <div className="mt-6 max-w-3xl">
          <NoOrdersBanner variant="applications" />
        </div>
      )}
      {q.isLoading && <Loading />}
      {q.isError && <ErrorState error={q.error} />}
      <ul className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {[...(q.data ?? []).map((p) => ({ to: routeFor(p.slug), title: p.title })), ...extra].map((c) => (
          <li key={c.to}>
            <Link to={lp(c.to)} className="card flex h-full items-center justify-between gap-3 p-5 text-ink no-underline hover:border-primary">
              <span className="font-serif text-lg">{c.title}</span>
              <Icon name="right" />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function MemorialDatesPage() {
  const { t } = useT();
  const lang = useLang();
  const [year, setYear] = useState(new Date().getFullYear() <= 2026 ? new Date().getFullYear() : 2026);
  const [month, setMonth] = useState<number | "">(new Date().getMonth() + 1);
  useTitle(t("info.memorialTitle"), t("info.memorialLead"));
  const q = useQuery({
    queryKey: ["memorial", year, month, lang],
    queryFn: () => apiGet<MemorialDate[]>("/memorial-dates", lang, { year, month: month || undefined }),
  });
  return (
    <div className="container-page py-6">
      <Breadcrumbs items={[{ label: t("nav.visitors"), to: "/visitors" }, { label: t("info.memorialTitle") }]} />
      <h1 className="text-3xl">{t("info.memorialTitle")}</h1>
      <p className="mt-2 max-w-3xl text-muted">{t("info.memorialLead")}</p>
      <div className="mt-5 flex flex-wrap gap-3">
        <label className="text-sm">
          <span className="mb-1 block font-medium">{t("info.year")}</span>
          <select className="input w-32" value={year} onChange={(e) => setYear(Number(e.target.value))}>
            {[2022, 2023, 2024, 2025, 2026].map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block font-medium">{t("info.month")}</span>
          <select className="input w-48" value={month} onChange={(e) => setMonth(e.target.value ? Number(e.target.value) : "")}>
            <option value="">{t("info.allMonths")}</option>
            {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
              <option key={m} value={m}>{monthName(m, lang)}</option>
            ))}
          </select>
        </label>
      </div>
      {q.isLoading && <Loading />}
      {q.isError && <ErrorState error={q.error} />}
      <ul className="mt-6 space-y-3">
        {q.data?.map((m) => (
          <li key={m.id} className="card flex gap-4 p-4">
            <span className="w-28 shrink-0 text-sm font-semibold text-accent">{m.date_label ?? t("info.noDate")}</span>
            <span className="flex-1">
              {m.title}
              {m.translation.is_fallback && (
                <span className="ml-2 badge border-line text-muted">{m.translation.lang.toUpperCase()}</span>
              )}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-4 text-xs text-muted">{t("home.todaySource")}</p>
    </div>
  );
}
