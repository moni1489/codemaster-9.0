import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { TransformComponent, TransformWrapper } from "react-zoom-pan-pinch";
import { useLang, useLocalePath } from "../app/lang";
import { useT } from "../app/useT";
import { useTitle } from "../app/useTitle";
import { TranslationNotice } from "../components/ui/Badges";
import { Breadcrumbs } from "../components/ui/Breadcrumbs";
import { Icon } from "../components/ui/Icon";
import { ErrorState, Loading } from "../components/ui/States";
import { apiGet } from "../lib/api";
import type { TranslationInfo } from "../lib/types";

interface DocLink { id: string; cipher: string; title: string }
interface Exhibit {
  id: string; order: number; caption: string; description: string | null; image_url: string | null;
  source_text: string | null; rights_note: string | null; document: DocLink | null; translation: TranslationInfo;
}
interface Exhibition {
  slug: string; title: string; summary: string | null; body: string | null; period_from: number | null;
  period_to: number | null; cover_url: string | null; is_demo: boolean; exhibits: Exhibit[]; translation: TranslationInfo;
}

export function ExhibitionsPage() {
  const { t } = useT();
  const lang = useLang();
  const lp = useLocalePath();
  useTitle(t("exh.title"), t("exh.lead"));
  const q = useQuery({ queryKey: ["exhibitions", lang], queryFn: () => apiGet<Exhibition[]>("/exhibitions", lang) });
  return (
    <div className="container-page py-8 sm:py-10">
      <Breadcrumbs items={[{ label: t("exh.title") }]} />
      <h1>{t("exh.title")}</h1>
      <p className="lead mt-2">{t("exh.lead")}</p>
      {q.isLoading && <Loading />}
      {q.isError && <ErrorState error={q.error} />}
      <ul className="mt-6 grid gap-5 md:grid-cols-2">
        {q.data?.map((e) => (
          <li key={e.slug} className="card overflow-hidden">
            {e.cover_url && <img src={e.cover_url} alt="" loading="lazy" className="aspect-[16/9] w-full object-cover" />}
            <div className="p-5">
              <p className="text-muted">{e.period_from}–{e.period_to}</p>
              <h2 className="mt-1">{e.title}</h2>
              {e.summary && <p className="mt-2 text-muted">{e.summary}</p>}
              <Link to={lp(`/exhibitions/${e.slug}`)} className="btn-primary mt-4">{t("exh.open")}</Link>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ExhibitionPage() {
  const { slug = "" } = useParams();
  const { t } = useT();
  const lang = useLang();
  const lp = useLocalePath();
  const q = useQuery({ queryKey: ["exhibition", slug, lang], queryFn: () => apiGet<Exhibition>(`/exhibitions/${encodeURIComponent(slug)}`, lang), retry: false });
  const [i, setI] = useState(0);
  const e = q.data;
  useTitle(e?.title, e?.summary ?? undefined);
  const total = e?.exhibits.length ?? 0;
  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => {
      if ((ev.target as HTMLElement)?.tagName === "INPUT") return;
      if (ev.key === "ArrowRight") setI((x) => Math.min(total - 1, x + 1));
      if (ev.key === "ArrowLeft") setI((x) => Math.max(0, x - 1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [total]);
  if (q.isLoading) return <Loading />;
  if (q.isError || !e) return <div className="container-page py-8 sm:py-10"><ErrorState error={q.error} /></div>;
  const x = e.exhibits[i];
  return (
    <div className="container-page py-8 sm:py-10">
      <Breadcrumbs items={[{ label: t("exh.title"), to: "/exhibitions" }, { label: e.title }]} />
      <h1>{e.title}</h1>
      {e.summary && <p className="mt-1 max-w-3xl text-muted">{e.summary}</p>}
      <TranslationNotice info={e.translation} />
      {x && (
        <section className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]" aria-label={t("exh.item", { n: i + 1, total })}>
          <div className="card overflow-hidden">
            <div className="flex items-center justify-between border-b border-line px-3 py-2">
              <p className="text-sm font-medium" aria-live="polite">{t("exh.item", { n: i + 1, total })}</p>
              <div className="flex gap-1">
                <button type="button" className="btn-ghost btn-icon" disabled={i === 0} onClick={() => setI(i - 1)} aria-label={t("common.prev")}><Icon name="left" size={18} /></button>
                <button type="button" className="btn-ghost btn-icon" disabled={i >= total - 1} onClick={() => setI(i + 1)} aria-label={t("common.next")}><Icon name="right" size={18} /></button>
              </div>
            </div>
            <div className="h-[60vh] min-h-[300px] bg-surface-2">
              {x.image_url && (
                <TransformWrapper key={x.id} minScale={1} maxScale={6} centerOnInit>
                  {({ zoomIn, zoomOut, resetTransform }) => (
                    <>
                      <div className="absolute z-10 m-2 flex gap-1">
                        <button type="button" className="btn-ghost btn-icon" onClick={() => zoomIn()} aria-label={t("viewer.zoomIn")}><Icon name="zoomIn" size={16} /></button>
                        <button type="button" className="btn-ghost btn-icon" onClick={() => zoomOut()} aria-label={t("viewer.zoomOut")}><Icon name="zoomOut" size={16} /></button>
                        <button type="button" className="btn-ghost btn-icon" onClick={() => resetTransform()} aria-label={t("viewer.reset")}><Icon name="reset" size={16} /></button>
                      </div>
                      <TransformComponent wrapperStyle={{ width: "100%", height: "100%" }} contentStyle={{ width: "100%", height: "100%" }}>
                        <img src={x.image_url ?? ""} alt={x.caption} className="h-full w-full object-contain" data-keep />
                      </TransformComponent>
                    </>
                  )}
                </TransformWrapper>
              )}
            </div>
          </div>
          <div className="space-y-3">
            <h2>{x.caption}</h2>
            {x.description && <p className="leading-relaxed">{x.description}</p>}
            {x.translation.is_fallback && <TranslationNotice info={x.translation} />}
            <dl className="card space-y-2 p-4 text-sm">
              <div><dt className="text-muted">{t("exh.source")}</dt><dd>{x.source_text}</dd></div>
              {x.document && <div><dt className="text-muted">{t("doc.cipher")}</dt><dd className="cipher">{x.document.cipher}</dd></div>}
              {x.rights_note && <div><dt className="text-muted">{t("exh.rights")}</dt><dd>{x.rights_note}</dd></div>}
            </dl>
            {x.document && <Link to={lp(`/catalog/documents/${x.document.id}`)} className="btn-primary">{t("exh.toDoc")}</Link>}
          </div>
        </section>
      )}
      <h2 className="mt-8">{t("exh.list")}</h2>
      <ol className="mt-3 flex gap-2 overflow-x-auto pb-2">
        {e.exhibits.map((ex, n) => (
          <li key={ex.id}>
            <button type="button" onClick={() => setI(n)} aria-current={n === i ? "true" : undefined} aria-label={ex.caption} className={`block h-20 w-24 overflow-hidden rounded border-2 ${n === i ? "border-primary" : "border-transparent"}`}>
              {ex.image_url && <img src={ex.image_url} alt="" loading="lazy" className="h-full w-full object-cover" />}
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}

interface Person { slug: string; name: string; role_line: string | null; bio: string | null; source: string | null; birth_label: string | null; death_label: string | null; dates_verified: boolean; is_fictional: boolean; translation: TranslationInfo }
interface CollectionT { slug: string; title: string; summary: string | null; editorial_note: string | null; is_demo: boolean; documents: DocLink[]; persons: Person[]; translation: TranslationInfo }
interface EventT { id: string; year: number; year_to: number | null; title: string; description: string | null; place: string | null; source: string | null; topic: string; date_verified: boolean; is_editorial: boolean; document: DocLink | null; translation: TranslationInfo }

export function HistoryPage() {
  const { t } = useT();
  const lang = useLang();
  const lp = useLocalePath();
  useTitle(t("hist.title"), t("hist.lead"));
  const [topic, setTopic] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const cols = useQuery({ queryKey: ["collections", lang], queryFn: () => apiGet<CollectionT[]>("/history/collections", lang) });
  const tl = useQuery({
    queryKey: ["timeline", lang, topic, from, to],
    queryFn: () => apiGet<EventT[]>("/history/timeline", lang, { topic, year_from: /^\d{4}$/.test(from) ? from : undefined, year_to: /^\d{4}$/.test(to) ? to : undefined }),
  });
  return (
    <div className="container-page py-8 sm:py-10">
      <Breadcrumbs items={[{ label: t("hist.title") }]} />
      <h1>{t("hist.title")}</h1>
      <p className="lead mt-2">{t("hist.lead")}</p>

      <section className="mt-8" aria-labelledby="col-h">
        <h2 id="col-h">{t("hist.collections")}</h2>
        {cols.isLoading && <Loading />}
        <div className="mt-4 grid grid-cols-1 gap-5 lg:grid-cols-3">
          {cols.data?.map((c) => (
            <article key={c.slug} className="card p-5">
              <h3>{c.title}</h3>
              {c.summary && <p className="mt-2 text-sm text-muted">{c.summary}</p>}
              {c.editorial_note && <p className="mt-3 rounded border-l-4 border-accent bg-surface-2 p-2 text-xs"><strong>{t("hist.editorial")}:</strong> {c.editorial_note}</p>}
              <h4 className="mt-3 text-sm font-semibold">{t("hist.documents")}</h4>
              <ul className="mt-1 space-y-1 text-sm">
                {c.documents.map((d) => <li key={d.id}><Link to={lp(`/catalog/documents/${d.id}`)}>{d.title}</Link></li>)}
              </ul>
              {c.persons.length > 0 && <>
                <h4 className="mt-3 text-sm font-semibold">{t("hist.persons")}</h4>
                <ul className="mt-1 space-y-2 text-sm">
                  {c.persons.map((p) => (
                    <li key={p.slug}>
                      <strong>{p.name}</strong>{p.role_line && ` — ${p.role_line}`}
                      {(p.birth_label || p.death_label) && <span className="text-muted"> ({p.birth_label ?? "?"}–{p.death_label ?? ""}){!p.dates_verified && `, ${t("hist.unverifiedDate")}`}</span>}
                      {p.is_fictional && <span className="badge ml-1 border-warn/60 text-warn">{t("hist.fictional")}</span>}
                      {p.bio && <p className="text-xs text-muted">{p.bio}</p>}
                    </li>
                  ))}
                </ul>
              </>}
            </article>
          ))}
        </div>
      </section>

      <section className="mt-10" aria-labelledby="tl-h">
        <h2 id="tl-h">{t("hist.timeline")}</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          <select className="input w-44" aria-label={t("hist.topic")} value={topic} onChange={(e) => setTopic(e.target.value)}>
            <option value="">{t("hist.topic")}: {t("common.all")}</option>
            {(["city", "industry", "war", "archive"] as const).map((k) => <option key={k} value={k}>{t(`hist.topics.${k}`)}</option>)}
          </select>
          <input className="input w-28" inputMode="numeric" aria-label={t("hist.from")} placeholder={t("hist.from")} value={from} onChange={(e) => setFrom(e.target.value)} />
          <input className="input w-28" inputMode="numeric" aria-label={t("hist.to")} placeholder={t("hist.to")} value={to} onChange={(e) => setTo(e.target.value)} />
        </div>
        {tl.isError && <ErrorState error={tl.error} />}
        <ol className="relative mt-6 border-l-2 border-line pl-6">
          {tl.data?.map((ev) => (
            <li key={ev.id} className="mb-6">
              <span className="absolute -left-[9px] mt-1 h-4 w-4 rounded-full border-2 border-bg bg-primary" aria-hidden="true" />
              <p className="font-serif text-xl text-accent">{ev.year}{ev.year_to ? `–${ev.year_to}` : ""}</p>
              <p className="font-medium">{ev.title}</p>
              <p className="mt-1 flex flex-wrap gap-1 text-xs">
                <span className="badge border-line">{t(`hist.topics.${ev.topic}`)}</span>
                {!ev.date_verified && <span className="badge border-warn/60 text-warn">{t("hist.unverifiedDate")}</span>}
                {ev.is_editorial && <span className="badge border-accent/60 text-accent">{t("hist.interpretation")}</span>}
                {ev.place && <span className="text-muted">{ev.place}</span>}
              </p>
              {ev.description && <p className="mt-1 text-sm">{ev.description}</p>}
              {ev.source && <p className="mt-1 text-xs text-muted">{t("hist.source")}: {ev.source}</p>}
              {ev.document && <Link to={lp(`/catalog/documents/${ev.document.id}`)} className="text-sm">{ev.document.title} →</Link>}
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
