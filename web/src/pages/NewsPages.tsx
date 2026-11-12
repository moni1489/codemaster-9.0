import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { type FormEvent, useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useLang, useLocalePath } from "../app/lang";
import { useT } from "../app/useT";
import { useTitle } from "../app/useTitle";
import { SafeHtml } from "../components/SafeHtml";
import { DemoBadge, TranslationNotice } from "../components/ui/Badges";
import { Breadcrumbs } from "../components/ui/Breadcrumbs";
import { ExternalLink } from "../components/ui/ExternalLink";
import { Icon } from "../components/ui/Icon";
import { ErrorState, Loading, NothingFound } from "../components/ui/States";
import { Pagination, ShareButton } from "../features/catalog/shared";
import { apiGet } from "../lib/api";
import { formatDate } from "../lib/format";
import type { NewsItem, NewsList, NewsOut } from "../lib/types";

const CATEGORIES = ["news", "exhibition", "conference", "event", "research", "branch"] as const;

export function NewsCard({ item }: { item: NewsItem }) {
  const lang = useLang();
  const lp = useLocalePath();
  return (
    <article className="card-hit flex h-full flex-col overflow-hidden">
      <div className="photo aspect-[16/9]">
        {item.cover_url && <img src={item.cover_url} alt="" loading="lazy" decoding="async" />}
      </div>
      <div className="flex flex-1 flex-col p-4">
        <p className="text-muted">
          {item.published_at && <time dateTime={item.published_at}>{formatDate(item.published_at, lang)}</time>}
        </p>
        <h3 className="mt-2 text-lg leading-snug">
          <Link to={lp(`/news/${item.slug}`)} className="hit">
            {item.title}
          </Link>
        </h3>
        {item.lead && <p className="mt-2 text-muted">{item.lead}</p>}
      </div>
    </article>
  );
}

export function NewsListPage() {
  const { t } = useT();
  const lang = useLang();
  const [sp, setSp] = useSearchParams();
  const [q, setQ] = useState(sp.get("q") ?? "");
  const spKey = sp.toString();
  useEffect(() => setQ(new URLSearchParams(spKey).get("q") ?? ""), [spKey]);
  useTitle(t("newsPage.title"));
  const category = sp.get("category") ?? "";
  const page = Number(sp.get("page") ?? "1") || 1;
  const res = useQuery({
    queryKey: ["news", lang, spKey],
    queryFn: () => apiGet<NewsList>("/news", lang, { category, q: sp.get("q") ?? "", page }),
    placeholderData: keepPreviousData,
  });
  const set = (k: string, v: string | null) => {
    const next = new URLSearchParams(sp);
    if (v) next.set(k, v);
    else next.delete(k);
    if (k !== "page") next.delete("page");
    setSp(next);
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    set("q", q.trim() || null);
  };
  return (
    <div className="container-page py-8 sm:py-10">
      <Breadcrumbs items={[{ label: t("newsPage.title") }]} />
      <h1>{t("newsPage.title")}</h1>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <form role="search" onSubmit={submit} className="flex min-w-[16rem] flex-1 gap-2">
          <label htmlFor="news-q" className="sr-only">{t("newsPage.search")}</label>
          <input id="news-q" type="search" className="input" placeholder={t("newsPage.search")} value={q} onChange={(e) => setQ(e.target.value)} maxLength={200} />
          <button type="submit" className="btn-primary" aria-label={t("header.search")}>
            <Icon name="search" size={18} />
          </button>
        </form>
        <div role="group" aria-label={t("catalog.fields.category")} className="flex flex-wrap gap-1">
          <button type="button" aria-pressed={!category} className={!category ? "btn-primary" : "btn-ghost"} onClick={() => set("category", null)}>
            {t("newsPage.allCategories")}
          </button>
          {CATEGORIES.map((c) => (
            <button key={c} type="button" aria-pressed={category === c} className={category === c ? "btn-primary" : "btn-ghost"} onClick={() => set("category", c)}>
              {t(`newsPage.categories.${c}`)}
            </button>
          ))}
        </div>
      </div>
      {res.isLoading && <Loading />}
      {res.isError && <ErrorState error={res.error} onRetry={() => void res.refetch()} />}
      {res.data && res.data.total === 0 && <NothingFound />}
      {res.data && res.data.total > 0 && (
        <>
          <ul className="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {res.data.items.map((n) => (
              <li key={n.id}>
                <NewsCard item={n} />
              </li>
            ))}
          </ul>
          <Pagination page={page} pages={res.data.pages} onPage={(p) => set("page", String(p))} />
        </>
      )}
    </div>
  );
}

export function NewsDetailPage() {
  const { slug = "" } = useParams();
  const { t } = useT();
  const lang = useLang();
  const lp = useLocalePath();
  const q = useQuery({
    queryKey: ["news-item", slug, lang],
    queryFn: () => apiGet<NewsOut>(`/news/${encodeURIComponent(slug)}`, lang),
    retry: false,
  });
  const n = q.data;
  useTitle(n?.title, n?.lead);
  if (q.isLoading) return <Loading />;
  if (q.isError || !n)
    return (
      <div className="container-page py-8 sm:py-10">
        <ErrorState error={q.error} />
      </div>
    );
  return (
    <div className="container-page py-8 sm:py-10">
      <Breadcrumbs items={[{ label: t("newsPage.title"), to: "/news" }, { label: n.title }]} />
      <article className="max-w-3xl">
        <p className="flex flex-wrap items-center gap-2 text-sm text-muted">
          <span className="badge border-line">{t(`newsPage.categories.${n.category}`)}</span>
          {n.published_at && <time dateTime={n.published_at}>{formatDate(n.published_at, lang)}</time>}
          {n.is_demo && <DemoBadge />}
        </p>
        <h1 className="mt-2">{n.title}</h1>
        <div className="mt-3 flex flex-wrap gap-2">
          <ShareButton title={n.title} />
        </div>
        <div className="mt-3">
          <TranslationNotice info={n.translation} />
        </div>
        {n.lead && <p className="mt-4 text-lg text-muted">{n.lead}</p>}
        {n.cover_url && <img src={n.cover_url} alt="" className="mt-6 w-full rounded-xl border border-line" />}
        {n.body && <SafeHtml html={n.body} className="prose mt-6" />}
        {n.video_url && (
          <p className="mt-4">
            <ExternalLink href={n.video_url}>Video</ExternalLink>
          </p>
        )}
      </article>
      {n.related.length > 0 && (
        <section className="mt-10" aria-labelledby="related-h">
          <h2 id="related-h">{t("newsPage.related")}</h2>
          <ul className="mt-4 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {n.related.map((r) => (
              <li key={r.id}>
                <NewsCard item={r} />
              </li>
            ))}
          </ul>
        </section>
      )}
      <Link to={lp("/news")} className="btn-ghost mt-10">
        <Icon name="left" size={18} /> {t("newsPage.back")}
      </Link>
    </div>
  );
}
