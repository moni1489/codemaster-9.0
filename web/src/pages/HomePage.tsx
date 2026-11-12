import { useQuery } from "@tanstack/react-query";
import { type FormEvent, lazy, Suspense, useState } from "react";
import { useT } from "../app/useT";
import { Link, useNavigate } from "react-router-dom";
import { useLang, useLocalePath } from "../app/lang";
import { useTitle } from "../app/useTitle";
import { TranslationNotice } from "../components/ui/Badges";
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

const TASKS: { key: string; to: string }[] = [
  { key: "catalog", to: "/catalog" },
  { key: "certificate", to: "/services/state" },
  { key: "paid", to: "/services/paid" },
  { key: "reading", to: "/visitors/reading-room" },
  { key: "branches", to: "/branches" },
  { key: "assistant", to: "/assistant" },
  { key: "faq", to: "/faq" },
];

/** Заголовок секции: h2 слева, ссылка «все» справа (на телефоне — под заголовком). */
function SectionHead({ id, title, to, more }: { id: string; title: string; to?: string; more?: string }) {
  const lp = useLocalePath();
  return (
    <div className="mb-6 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
      <h2 id={id}>{title}</h2>
      {to && more && (
        <Link to={lp(to)} className="inline-flex min-h-11 items-center gap-1 font-medium">
          {more} <Icon name="right" size={18} />
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
    <section className="hero-band bg-primary text-primary-ink" aria-labelledby="hero-title" data-enter>
      <div className="container-page grid items-center gap-10 py-10 sm:py-14 lg:grid-cols-[minmax(0,7fr)_minmax(0,4fr)] lg:py-16">
        <div>
          <h1 id="hero-title" className="text-[1.75rem] sm:text-[2.5rem] lg:text-[2.75rem]">
            {t("home.heroTitle")}
          </h1>
          <p className="mt-4 max-w-2xl text-lg opacity-90">{t("home.heroLead")}</p>
          <form role="search" onSubmit={submit} className="mt-8 max-w-2xl">
            <label htmlFor="hero-q" className="mb-3 block text-lg font-semibold">
              {t("home.quickSearch")}
            </label>
            <div className="flex">
              <input
                id="hero-q"
                type="search"
                className="min-h-14 w-full min-w-0 rounded-l-lg border-0 bg-white px-4 text-lg text-black placeholder:text-neutral-600 focus-visible:outline-white"
                placeholder={t("home.searchPlaceholder")}
                value={q}
                onChange={(e) => setQ(e.target.value)}
                maxLength={300}
                enterKeyHint="search"
              />
              <button
                type="submit"
                className="inline-flex min-h-14 min-w-14 shrink-0 items-center justify-center gap-2 rounded-r-lg bg-ink px-4 text-lg font-semibold text-bg hover:opacity-90 sm:px-6"
              >
                <Icon name="search" size={24} />
                <span className="sr-only sm:not-sr-only">{t("header.search")}</span>
              </button>
            </div>
          </form>
          <p className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-2">
            <span className="opacity-90">{t("home.examples")}</span>
            {EXAMPLES[lang].map((ex) => (
              <button key={ex} type="button" className="min-h-11 text-left font-medium underline underline-offset-4 hover:decoration-2" onClick={() => go(ex)}>
                {ex}
              </button>
            ))}
          </p>
          <Link
            to={lp("/assistant")}
            className="mt-8 inline-flex min-h-14 items-center gap-3 rounded-full border-2 border-current px-5 py-2 text-lg font-semibold text-primary-ink no-underline hover:bg-white/10"
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-ink text-primary">
              <Icon name="mic" size={22} />
            </span>
            {t("voice.heroAsk")}
          </Link>
        </div>
        <div className="photo hidden aspect-square rounded-2xl lg:block">
          <img
            src="/photos/photo-f9691888-960.jpg"
            srcSet="/photos/photo-f9691888-500.jpg 500w, /photos/photo-f9691888-960.jpg 960w, /photos/photo-f9691888-1280.jpg 1280w"
            sizes="33vw"
            width={1280}
            height={962}
            alt={t("home.heroPhotoAlt")}
            decoding="async"
            data-source="stand-in"
            data-subject="Ust-Kamenogorsk"
          />
        </div>
      </div>
    </section>
  );
}

function Tasks() {
  const { t } = useT();
  const lp = useLocalePath();
  return (
    <section className="container-page section" aria-labelledby="h-tasks">
      <SectionHead id="h-tasks" title={t("home.tasksTitle")} />
      <ul className="grid gap-x-10 gap-y-7 md:grid-cols-2 lg:grid-cols-3">
        {TASKS.map((task) => (
          <li key={task.key} className="flex gap-4">
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-primary/10 text-ink" aria-hidden="true">
              <Icon name="arrow" size={24} />
            </span>
            <span className="min-w-0">
              <Link to={lp(task.to)} className="text-lg font-semibold leading-snug">
                {t(`home.tasks.${task.key}.title`)}
              </Link>
              <span className="mt-1 block text-muted">{t(`home.tasks.${task.key}.text`)}</span>
            </span>
          </li>
        ))}
      </ul>
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
    <section className="border-y border-line bg-surface" aria-labelledby="h-history">
      <div className="container-page section">
        <SectionHead id="h-history" title={t("home.historyTitle")} to="/catalog?has_copy=true&category=photo" more={t("common.all")} />
        <p className="lead -mt-3 mb-6">{t("home.historyText")}</p>
        {q.isLoading && <Loading />}
        <ul className="grid grid-cols-2 gap-x-4 gap-y-6 md:grid-cols-4">
          {q.data?.items.map((d, i) => (
            <li key={d.id} className={i >= 4 ? "hidden md:block" : undefined}>
              <Link to={lp(`/catalog/documents/${d.id}`)} className="group block text-ink no-underline">
                <div className="photo aspect-[4/3] rounded-xl">
                  {d.thumb_url && <img src={d.thumb_url} alt="" loading="lazy" decoding="async" />}
                </div>
                <p className="mt-3 font-medium leading-normal group-hover:underline">{d.title}</p>
                <p className="meta mt-1">{d.period_label || yearsLabel(d.year_from, d.year_to)}</p>
              </Link>
            </li>
          ))}
        </ul>
        <Link to={lp("/exhibitions")} className="btn-ghost mt-8">
          {t("home.toExhibitions")}
        </Link>
      </div>
    </section>
  );
}

function Today() {
  const { t } = useT();
  const lang = useLang();
  const q = useQuery({
    queryKey: ["today", lang],
    queryFn: () => apiGet<TodayResponse>("/memorial-dates/today", lang, { limit: 4 }),
    staleTime: 60 * 60_000,
  });
  if (!q.isLoading && !q.data?.items.length) return null;
  return (
    <section className="container-page section" aria-labelledby="today-title">
      <SectionHead id="today-title" title={t("home.todayTitle")} to="/visitors/memorial-dates" more={t("common.more")} />
      {q.isLoading && <Loading />}
      {q.data && (
        <>
          {!q.data.exact && <p className="-mt-3 mb-6 text-muted">{t("home.todayNearest")}</p>}
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {q.data.items.map((m, i) => (
              <li key={m.id} className={`card-flat p-5 ${i >= 2 ? "hidden sm:block" : ""}`}>
                <p className="text-lg font-semibold text-primary">{m.date_label ?? `${m.day}.${m.month}`}</p>
                <p className="mt-2 leading-snug">{m.title}</p>
                {m.translation.is_fallback && (
                  <div className="mt-2">
                    <TranslationNotice info={m.translation} />
                  </div>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

function Visit() {
  const { t } = useT();
  const lang = useLang();
  const lp = useLocalePath();
  const branches = useQuery({
    queryKey: ["branches", lang],
    queryFn: () => apiGet<Branch[]>("/branches", lang),
    staleTime: 10 * 60_000,
  });
  const main = branches.data?.find((b) => b.type === "main");
  const filials = branches.data?.filter((b) => b.type === "branch") ?? [];
  const tel = SITE.phoneReception.replace(/[^\d+]/g, "");
  return (
    <section className="border-t border-line bg-surface" aria-labelledby="h-visit">
      <div className="container-page section grid gap-8 lg:grid-cols-2 lg:items-center">
        <div>
          <h2 id="h-visit">{t("home.visitTitle")}</h2>
          <dl className="mt-6 space-y-5 text-lg">
            <div className="flex gap-3">
              <Icon name="pin" size={24} className="mt-1 shrink-0 text-primary" />
              <div>
                <dt className="sr-only">{t("footer.address")}</dt>
                <dd>{main?.address ?? "г. Усть-Каменогорск, ул. Бейбітшілік, 26/1"}</dd>
              </div>
            </div>
            <div className="flex gap-3">
              <Icon name="clock" size={24} className="mt-1 shrink-0 text-primary" />
              <div>
                <dt className="sr-only">{t("footer.hours")}</dt>
                <dd>{main?.hours ?? "Пн–Пт 8:00–17:00"}</dd>
              </div>
            </div>
            <div className="flex gap-3">
              <Icon name="phone" size={24} className="mt-1 shrink-0 text-primary" />
              <div>
                <dt className="sr-only">{t("header.phone")}</dt>
                <dd>
                  {t("header.phone")}: <a href={`tel:${tel}`}>{SITE.phoneReception}</a>
                </dd>
              </div>
            </div>
          </dl>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <a href={`tel:${tel}`} className="btn-primary btn-lg">
              <Icon name="phone" size={22} /> {t("home.call")}
            </a>
            <Link to={lp("/branches")} className="btn-ghost btn-lg">
              <Icon name="pin" size={22} /> {t("home.allBranches")}
            </Link>
          </div>
          {filials.length > 0 && <p className="mt-4 text-muted">{t("home.branchesText", { count: filials.length })}</p>}
        </div>
        <div className="overflow-hidden rounded-2xl border border-line" aria-hidden="true">
          <Suspense fallback={<div className="h-72 bg-surface-2 lg:h-96" />}>
            {branches.data && branches.data.length > 0 ? (
              <MiniMap branches={branches.data} className="h-72 w-full lg:h-96" />
            ) : (
              <div className="h-72 bg-surface-2 lg:h-96" />
            )}
          </Suspense>
        </div>
      </div>
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
    <section className="container-page section" aria-labelledby="h-news">
      <SectionHead id="h-news" title={t("home.newsTitle")} to="/news" more={t("common.all")} />
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

export function HomePage() {
  const { t } = useT();
  useTitle(undefined, t("home.heroText"));
  return (
    <>
      <Hero />
      <Tasks />
      <HistoryInDocuments />
      <Today />
      <Visit />
      <LatestNews />
    </>
  );
}
