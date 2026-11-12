import { useQuery } from "@tanstack/react-query";
import { type FormEvent, lazy, Suspense, useState } from "react";
import { useT } from "../app/useT";
import { Link, useNavigate } from "react-router-dom";
import { useLang, useLocalePath } from "../app/lang";
import { useTitle } from "../app/useTitle";
import { DemoBadge, TranslationNotice } from "../components/ui/Badges";
import { ExternalLink } from "../components/ui/ExternalLink";
import { Icon } from "../components/ui/Icon";
import { Loading } from "../components/ui/States";
import { yearsLabel } from "../features/catalog/shared";
import { apiGet } from "../lib/api";
import { SITE } from "../lib/site";
import type { Branch, NewsList, SearchResponse, TodayResponse } from "../lib/types";
import { NewsCard } from "./NewsPages";

const MiniMap = lazy(() => import("../components/MiniMap"));

const EXAMPLES = {
  ru: ["фотографии Усть-Каменогорска 1960-х", "Лениногорск", "газета 1945", "личные фонды"],
  kk: ["Өскемен фотосуреттері", "Риддер", "газет 1945", "Ұлы Отан соғысы"],
  en: ["Oskemen photo", "Ridder", "newspaper 1945", "Great Patriotic War"],
} as const;

function SectionTitle({ id, title, text, to, more }: { id: string; title: string; text?: string; to?: string; more?: string }) {
  const lp = useLocalePath();
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
      <div>
        <h2 id={id} className="text-2xl sm:text-3xl">
          {title}
        </h2>
        {text && <p className="mt-1 text-muted">{text}</p>}
      </div>
      {to && more && (
        <Link to={lp(to)} className="text-sm font-medium">
          {more} →
        </Link>
      )}
    </div>
  );
}

function Hero() {
  const { t } = useT();
  const lang = useLang();
  const lp = useLocalePath();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const go = (query: string) => navigate(lp(`/catalog${query ? `?q=${encodeURIComponent(query)}` : ""}`));
  const submit = (e: FormEvent) => {
    e.preventDefault();
    go(q.trim());
  };
  return (
    <section className="hero-bg border-b border-line" aria-labelledby="hero-title">
      <div className="container-page grid gap-8 py-12 lg:grid-cols-[3fr_2fr] lg:py-16">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wider text-accent">{t("org.tagline")}</p>
          <h1 id="hero-title" className="mt-2 text-3xl leading-tight sm:text-4xl lg:text-5xl">
            {t("home.heroTitle")}
          </h1>
          <p className="mt-4 max-w-2xl text-lg text-muted">{t("home.heroText")}</p>
          <form role="search" onSubmit={submit} className="mt-6 max-w-2xl">
            <label htmlFor="hero-q" className="mb-2 block font-medium">
              {t("home.quickSearch")}
            </label>
            <div className="flex gap-2">
              <input
                id="hero-q"
                type="search"
                className="input py-3 text-base"
                placeholder={t("catalog.queryPlaceholder")}
                value={q}
                onChange={(e) => setQ(e.target.value)}
                maxLength={300}
              />
              <button type="submit" className="btn-primary px-5">
                <Icon name="search" />
                <span className="hidden sm:inline">{t("header.search")}</span>
              </button>
            </div>
            <p className="mt-3 flex flex-wrap items-center gap-2 text-sm">
              <span className="text-muted">{t("home.examples")}</span>
              {EXAMPLES[lang].map((ex) => (
                <button key={ex} type="button" className="badge border-line bg-surface hover:border-primary" onClick={() => go(ex)}>
                  {ex}
                </button>
              ))}
            </p>
          </form>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link to={lp("/catalog")} className="btn-ghost">
              {t("home.advanced")}
            </Link>
            <Link to={lp("/exhibitions")} className="btn-ghost">
              {t("home.toExhibitions")}
            </Link>
            <Link to={lp("/branches")} className="btn-ghost">
              <Icon name="pin" size={16} /> {t("home.toBranches")}
            </Link>
          </div>
        </div>
        <TodayBlock />
      </div>
    </section>
  );
}

function TodayBlock() {
  const { t } = useT();
  const lang = useLang();
  const lp = useLocalePath();
  const q = useQuery({
    queryKey: ["today", lang],
    queryFn: () => apiGet<TodayResponse>("/memorial-dates/today", lang, { limit: 4 }),
    staleTime: 60 * 60_000,
  });
  return (
    <section className="card self-start p-5" aria-labelledby="today-title">
      <h2 id="today-title" className="flex items-center gap-2 text-xl">
        <Icon name="calendar" /> {t("home.todayTitle")}
      </h2>
      {q.isLoading && <Loading />}
      {q.data && (
        <>
          {!q.data.exact && <p className="mt-1 text-sm text-muted">{t("home.todayNearest")}</p>}
          <ul className="mt-3 space-y-3">
            {q.data.items.map((m) => (
              <li key={m.id} className="border-l-4 border-accent pl-3">
                <p className="text-sm font-semibold text-accent">{m.date_label ?? `${m.day}.${m.month}`}</p>
                <p className="text-sm leading-snug">{m.title}</p>
                {m.translation.is_fallback && <TranslationNotice info={m.translation} />}
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-muted">{t("home.todaySource")}</p>
          <Link to={lp("/visitors/memorial-dates")} className="mt-2 inline-block text-sm">
            {t("common.more")} →
          </Link>
        </>
      )}
    </section>
  );
}

function HistoryInDocuments() {
  const { t } = useT();
  const lang = useLang();
  const lp = useLocalePath();
  const q = useQuery({
    queryKey: ["home-history", lang],
    queryFn: () => apiGet<SearchResponse>("/catalog/search", lang, { has_copy: true, category: ["photo"], sort: "date_asc", page_size: 8 }),
    staleTime: 5 * 60_000,
  });
  return (
    <section className="container-page py-12" aria-labelledby="h-history">
      <SectionTitle id="h-history" title={t("home.historyTitle")} text={t("home.historyText")} to="/catalog?has_copy=true&category=photo" more={t("nav.catalog")} />
      {q.isLoading && <Loading />}
      <ul className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {q.data?.items.map((d) => (
          <li key={d.id}>
            <Link to={lp(`/catalog/documents/${d.id}`)} className="group block text-ink no-underline">
              <div className="aspect-[4/3] overflow-hidden rounded-xl border border-line bg-surface-2">
                {d.thumb_url && (
                  <img
                    src={d.thumb_url}
                    alt=""
                    loading="lazy"
                    decoding="async"
                    className="h-full w-full object-cover transition-transform group-hover:scale-105"
                  />
                )}
              </div>
              <p className="mt-2 line-clamp-2 text-sm font-medium leading-snug group-hover:text-primary">{d.title}</p>
              <p className="text-xs text-muted">
                {d.period_label || yearsLabel(d.year_from, d.year_to)} {d.is_demo && <DemoBadge short />}
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

function InfoCards() {
  const { t } = useT();
  const lang = useLang();
  const lp = useLocalePath();
  const branches = useQuery({
    queryKey: ["branches", lang],
    queryFn: () => apiGet<Branch[]>("/branches", lang),
    staleTime: 10 * 60_000,
  });
  const filials = branches.data?.filter((b) => b.type === "branch") ?? [];
  return (
    <section className="container-page grid gap-6 pb-12 lg:grid-cols-3" aria-label={t("home.usefulTitle")}>
      <article className="card flex flex-col p-6">
        <h2 className="text-xl">{t("home.exhibitionsTitle")}</h2>
        <p className="mt-2 flex-1 text-muted">{t("home.exhibitionsText")}</p>
        <Link to={lp("/exhibitions")} className="btn-primary mt-4 self-start">
          {t("home.toExhibitions")}
        </Link>
      </article>
      <article className="card flex flex-col p-6">
        <h2 className="text-xl">{t("home.branchesTitle")}</h2>
        <p className="mt-2 text-muted">{t("home.branchesText", { count: filials.length || 13 })}</p>
        <div className="mt-3" aria-hidden="true">
          <Suspense fallback={<div className="h-40 rounded-lg bg-surface-2" />}>{filials.length > 0 && <MiniMap branches={branches.data ?? []} />}</Suspense>
        </div>
        <ul className="mt-3 flex flex-1 flex-wrap gap-1">
          {filials.slice(0, 8).map((b) => (
            <li key={b.id} className="badge border-line">
              {b.locality}
            </li>
          ))}
        </ul>
        <Link to={lp("/branches")} className="btn-primary mt-4 self-start">
          <Icon name="pin" size={16} /> {t("home.toBranches")}
        </Link>
      </article>
      <article className="card flex flex-col border-primary/40 bg-primary/5 p-6">
        <h2 className="text-xl">{t("home.howTitle")}</h2>
        <p className="mt-2 flex-1">{t("home.howText")}</p>
        <Link to={lp("/services/state")} className="btn-primary mt-4 self-start">
          {t("home.howLink")}
        </Link>
      </article>
    </section>
  );
}

function LatestNews() {
  const { t } = useT();
  const lang = useLang();
  const q = useQuery({
    queryKey: ["home-news", lang],
    queryFn: () => apiGet<NewsList>("/news", lang, { page_size: 3 }),
    staleTime: 5 * 60_000,
  });
  if (!q.data?.items.length) return null;
  return (
    <section className="container-page pb-12" aria-labelledby="h-news">
      <SectionTitle id="h-news" title={t("home.newsTitle")} to="/news" more={t("nav.news")} />
      <ul className="grid gap-5 md:grid-cols-3">
        {q.data.items.map((n) => (
          <li key={n.id}>
            <NewsCard item={n} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function Useful() {
  const { t } = useT();
  const lp = useLocalePath();
  const links = [
    { key: "catalog", to: "/visitors/catalog-guide" },
    { key: "structure", to: "/visitors/structure" },
    { key: "access", to: "/visitors/access" },
    { key: "branches", to: "/branches" },
  ] as const;
  return (
    <section className="border-y border-line bg-surface" aria-labelledby="h-useful">
      <div className="container-page grid gap-8 py-12 lg:grid-cols-2">
        <div>
          <h2 id="h-useful" className="text-2xl sm:text-3xl">
            {t("home.usefulTitle")}
          </h2>
          <ul className="mt-4 space-y-2">
            {links.map((l) => (
              <li key={l.key}>
                <Link to={lp(l.to)} className="flex items-center gap-2 rounded-lg p-2 hover:bg-surface-2">
                  <Icon name="info" size={18} /> {t(`home.useful.${l.key}`)}
                </Link>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h2 className="text-2xl sm:text-3xl">{t("home.socialTitle")}</h2>
          <ul className="mt-4 grid gap-3 sm:grid-cols-2">
            <li>
              <ExternalLink href={SITE.social.instagram.url} className="card flex items-center gap-3 p-4 no-underline">
                <Icon name="instagram" size={28} />
                <span>
                  <span className="block font-semibold text-ink">Instagram</span>
                  <span className="text-sm text-muted">{SITE.social.instagram.handle}</span>
                </span>
              </ExternalLink>
            </li>
            <li>
              <ExternalLink href={SITE.social.facebook.url} className="card flex items-center gap-3 p-4 no-underline">
                <Icon name="facebook" size={28} />
                <span>
                  <span className="block font-semibold text-ink">Facebook</span>
                  <span className="text-sm text-muted">{SITE.social.facebook.handle}</span>
                </span>
              </ExternalLink>
            </li>
          </ul>
        </div>
      </div>
    </section>
  );
}

export function HomePage() {
  const { t } = useT();
  useTitle(undefined, t("home.heroText"));
  return (
    <>
      <Hero />
      <HistoryInDocuments />
      <InfoCards />
      <LatestNews />
      <Useful />
    </>
  );
}
