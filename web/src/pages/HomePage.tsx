import { useQuery } from "@tanstack/react-query";
import { type FormEvent, lazy, Suspense, useState } from "react";
import { useT } from "../app/useT";
import { Link, useNavigate } from "react-router-dom";
import { useLang, useLocalePath } from "../app/lang";
import { useTitle } from "../app/useTitle";
import { DemoBadge, TranslationNotice } from "../components/ui/Badges";
import { Icon, type IconName } from "../components/ui/Icon";
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

const TASKS: { key: string; to: string; icon: IconName }[] = [
  { key: "catalog", to: "/catalog", icon: "search" },
  { key: "certificate", to: "/services/state", icon: "doc" },
  { key: "paid", to: "/services/paid", icon: "copy" },
  { key: "reading", to: "/visitors/reading-room", icon: "clock" },
  { key: "branches", to: "/branches", icon: "pin" },
  { key: "assistant", to: "/assistant", icon: "chat" },
  { key: "faq", to: "/faq", icon: "help" },
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
    <section className="border-b border-line" aria-labelledby="hero-title" data-enter>
      <div className="container-page grid items-center gap-8 py-8 sm:py-12 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] lg:gap-12 lg:py-16">
        <div>
          <h1 id="hero-title" className="text-[1.625rem] sm:text-[2.5rem] lg:text-[2.875rem]">
            {t("home.heroTitle")}
          </h1>
          <p className="lead mt-4">{t("home.heroLead")}</p>
          <form role="search" onSubmit={submit} className="mt-8">
            <label htmlFor="hero-q" className="mb-3 block text-lg font-semibold">
              {t("home.quickSearch")}
            </label>
            <div className="flex flex-col gap-3 sm:flex-row">
              <input
                id="hero-q"
                type="search"
                className="input input-lg"
                placeholder={t("catalog.queryPlaceholder")}
                value={q}
                onChange={(e) => setQ(e.target.value)}
                maxLength={300}
                enterKeyHint="search"
              />
              <button type="submit" className="btn-primary btn-lg">
                <Icon name="search" size={22} />
                {t("header.search")}
              </button>
            </div>
          </form>
          <div className="mt-5">
            <p className="text-muted">{t("home.examples")}</p>
            <ul className="mt-2 flex flex-wrap gap-2">
              {EXAMPLES[lang].map((ex) => (
                <li key={ex}>
                  <button type="button" className="chip" onClick={() => go(ex)}>
                    {ex}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
        <div className="photo aspect-[16/10] rounded-2xl lg:aspect-[4/5]">
          <img
            src="/photos/photo-f9691888-960.jpg"
            srcSet="/photos/photo-f9691888-500.jpg 500w, /photos/photo-f9691888-960.jpg 960w, /photos/photo-f9691888-1280.jpg 1280w"
            sizes="(min-width: 1024px) 40vw, 100vw"
            width={1280}
            height={962}
            alt={t("home.heroPhotoAlt")}
            fetchPriority="high"
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
      <ul className="grid gap-3 md:grid-cols-2">
        {TASKS.map((task) => (
          <li key={task.key}>
            <Link to={lp(task.to)} className="card-link flex h-full items-center gap-4 p-4 sm:p-5">
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                <Icon name={task.icon} size={24} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-lg font-semibold leading-snug">{t(`home.tasks.${task.key}.title`)}</span>
                <span className="mt-1 block text-muted">{t(`home.tasks.${task.key}.text`)}</span>
              </span>
              <Icon name="right" size={22} className="shrink-0 text-muted" />
            </Link>
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
          {q.data?.items.map((d) => (
            <li key={d.id}>
              <Link to={lp(`/catalog/documents/${d.id}`)} className="group block text-ink no-underline">
                <div className="photo aspect-[4/3] rounded-xl">
                  {d.thumb_url && <img src={d.thumb_url} alt="" loading="lazy" decoding="async" />}
                </div>
                <p className="mt-2 line-clamp-2 font-medium leading-snug group-hover:underline">{d.title}</p>
                <p className="meta">
                  {d.period_label || yearsLabel(d.year_from, d.year_to)} {d.is_demo && <DemoBadge short />}
                </p>
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
            {q.data.items.map((m) => (
              <li key={m.id} className="card-flat p-5">
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
          <p className="meta mt-4">{t("home.todaySource")}</p>
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
