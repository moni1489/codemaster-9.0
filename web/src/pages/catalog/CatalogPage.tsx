import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { type FormEvent, useEffect, useMemo, useState } from "react";
import { useT } from "../../app/useT";
import { Link, useSearchParams } from "react-router-dom";
import { useLang, useLocalePath } from "../../app/lang";
import { useTitle } from "../../app/useTitle";
import { Breadcrumbs } from "../../components/ui/Breadcrumbs";
import { Icon } from "../../components/ui/Icon";
import { ErrorState, Loading, NothingFound } from "../../components/ui/States";
import { DocumentRow, Pagination } from "../../features/catalog/shared";
import { apiGet } from "../../lib/api";
import type { Facets, SearchResponse } from "../../lib/types";

// Текстовые поля поиска (ТЗ §5.3) — применяются кнопкой «Найти»
const TEXT_FIELDS = ["q", "title", "fund", "inventory", "case", "year", "author", "topic", "place"] as const;
// Фильтры — применяются сразу
const LIST_FIELDS = ["category", "doc_type"] as const;
const PERIODS = [
  { key: "p1", from: 1000, to: 1916 },
  { key: "p2", from: 1917, to: 1940 },
  { key: "p3", from: 1941, to: 1945 },
  { key: "p4", from: 1946, to: 1991 },
  { key: "p5", from: 1991, to: 2100 },
] as const;
const SORTS = ["relevance", "date_asc", "date_desc", "cipher"] as const;
const CATEGORIES = ["historical", "photo", "map", "written", "organization", "personal", "audiovisual"] as const;

type Draft = Record<(typeof TEXT_FIELDS)[number], string>;

function draftFrom(sp: URLSearchParams): Draft {
  return Object.fromEntries(TEXT_FIELDS.map((k) => [k, sp.get(k) ?? ""])) as Draft;
}

export function CatalogPage() {
  const { t } = useT();
  const lang = useLang();
  const lp = useLocalePath();
  const [sp, setSp] = useSearchParams();
  const [draft, setDraft] = useState<Draft>(() => draftFrom(sp));
  const [showFilters, setShowFilters] = useState(false);
  useTitle(t("catalog.title"), t("catalog.lead"));

  // URL — единственный источник истины (смена языка/темы/назад сохраняют фильтры)
  const spKey = sp.toString();
  useEffect(() => setDraft(draftFrom(new URLSearchParams(spKey))), [spKey]);

  const params = useMemo(() => {
    const p: Record<string, string | string[]> = {};
    new URLSearchParams(spKey).forEach((v, k) => {
      if ((LIST_FIELDS as readonly string[]).includes(k)) p[k] = [...((p[k] as string[]) ?? []), v];
      else p[k] = v;
    });
    return p;
  }, [spKey]);
  const page = Number(sp.get("page") ?? "1") || 1;

  const facets = useQuery({
    queryKey: ["facets", lang],
    queryFn: () => apiGet<Facets>("/catalog/facets", lang),
    staleTime: 5 * 60_000,
  });
  const result = useQuery({
    queryKey: ["search", lang, spKey],
    queryFn: () => apiGet<SearchResponse>("/catalog/search", lang, params),
    placeholderData: keepPreviousData,
  });

  const update = (mutate: (next: URLSearchParams) => void) => {
    const next = new URLSearchParams(sp);
    mutate(next);
    if (!next.has("page_keep")) next.delete("page");
    next.delete("page_keep");
    setSp(next);
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    update((next) => {
      for (const k of TEXT_FIELDS) {
        const v = draft[k].trim();
        const valid = k !== "year" || /^\d{4}$/.test(v);
        if (v && valid) next.set(k, v);
        else next.delete(k);
      }
    });
  };

  const toggleList = (key: (typeof LIST_FIELDS)[number], value: string) =>
    update((next) => {
      const values = next.getAll(key);
      next.delete(key);
      (values.includes(value) ? values.filter((v) => v !== value) : [...values, value]).forEach((v) => next.append(key, v));
    });

  const setOne = (key: string, value: string | null) =>
    update((next) => {
      if (value) next.set(key, value);
      else next.delete(key);
    });

  const activePeriod = PERIODS.find(
    (p) => sp.get("period_from") === String(p.from) && sp.get("period_to") === String(p.to),
  )?.key;
  const hasAny = [...sp.keys()].some((k) => k !== "page" && k !== "sort");

  const field = (
    k: (typeof TEXT_FIELDS)[number],
    label: string,
    extra: { inputMode?: "numeric"; maxLength?: number; fullLabel?: string } = {},
  ) => (
    <div>
      <label htmlFor={`f-${k}`} className="mb-1 block truncate text-sm font-medium" title={extra.fullLabel}>
        {label}
        {extra.fullLabel && <span className="sr-only"> ({extra.fullLabel})</span>}
      </label>
      <input
        id={`f-${k}`}
        className="input"
        value={draft[k]}
        onChange={(e) => setDraft((d) => ({ ...d, [k]: e.target.value }))}
        maxLength={extra.maxLength ?? 200}
        inputMode={extra.inputMode}
      />
    </div>
  );

  const data = result.data;

  return (
    <div className="container-page py-6">
      <Breadcrumbs items={[{ label: t("catalog.title") }]} />
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl">{t("catalog.title")}</h1>
          <p className="mt-1 max-w-3xl text-muted">{t("catalog.lead")}</p>
        </div>
        <div className="flex gap-2">
          <Link to={lp("/catalog/funds")} className="btn-ghost">
            <Icon name="folder" size={16} /> {t("catalog.browseFunds")}
          </Link>
          <Link to={lp("/catalog/funds?personal=true")} className="btn-ghost">
            {t("catalog.personalFunds")}
          </Link>
        </div>
      </div>

      <form role="search" onSubmit={submit} className="mt-5">
        <div className="flex gap-2">
          <label htmlFor="f-q" className="sr-only">
            {t("catalog.query")}
          </label>
          <input
            id="f-q"
            type="search"
            className="input text-base"
            placeholder={t("catalog.queryPlaceholder")}
            value={draft.q}
            onChange={(e) => setDraft((d) => ({ ...d, q: e.target.value }))}
            maxLength={300}
          />
          <button type="submit" className="btn-primary">
            <Icon name="search" size={18} />
            <span className="hidden sm:inline">{t("header.search")}</span>
          </button>
        </div>

        <div className="mt-3 flex items-center justify-between lg:hidden">
          <button
            type="button"
            className="btn-ghost"
            aria-expanded={showFilters}
            aria-controls="catalog-filters"
            onClick={() => setShowFilters((v) => !v)}
          >
            <Icon name="filter" size={16} />
            {showFilters ? t("catalog.hideFilters") : t("catalog.showFilters")}
          </button>
        </div>

        <div className="mt-4 grid gap-6 lg:grid-cols-[18rem_1fr]">
          {/* панель фильтров */}
          <aside
            id="catalog-filters"
            aria-label={t("catalog.filters")}
            className={`${showFilters ? "block" : "hidden"} space-y-5 lg:block`}
          >
            <fieldset className="card space-y-3 p-4">
              <legend>{t("catalog.advancedFields")}</legend>
              {field("title", t("catalog.fields.title"))}
              <div className="grid grid-cols-3 gap-2">
                {field("fund", t("catalog.fields.fundShort"), { maxLength: 32, fullLabel: t("catalog.fields.fund") })}
                {field("inventory", t("catalog.fields.inventoryShort"), {
                  maxLength: 32,
                  fullLabel: t("catalog.fields.inventory"),
                })}
                {field("case", t("catalog.fields.caseShort"), { maxLength: 32, fullLabel: t("catalog.fields.case") })}
              </div>
              {field("year", t("catalog.fields.year"), { inputMode: "numeric", maxLength: 4 })}
              {field("author", t("catalog.fields.author"))}
              {field("topic", t("catalog.fields.topic"))}
              {field("place", t("catalog.fields.place"))}
              <button type="submit" className="btn-primary w-full">
                {t("common.apply")}
              </button>
            </fieldset>

            <fieldset className="card space-y-2 p-4">
              <legend>{t("catalog.periods.label")}</legend>
              {PERIODS.map((p) => (
                <label key={p.key} className="flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="period"
                    checked={activePeriod === p.key}
                    onChange={() =>
                      update((next) => {
                        next.set("period_from", String(p.from));
                        next.set("period_to", String(p.to));
                      })
                    }
                  />
                  {t(`catalog.periods.${p.key}`)}
                </label>
              ))}
              {(sp.has("period_from") || sp.has("period_to")) && (
                <button
                  type="button"
                  className="text-sm text-primary underline"
                  onClick={() =>
                    update((next) => {
                      next.delete("period_from");
                      next.delete("period_to");
                    })
                  }
                >
                  {t("common.reset")}
                </button>
              )}
            </fieldset>

            <fieldset className="card space-y-2 p-4">
              <legend>{t("catalog.fields.category")}</legend>
              {CATEGORIES.map((c) => {
                const count = facets.data?.categories.find((f) => f.value === c)?.count ?? 0;
                return (
                  <label key={c} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={sp.getAll("category").includes(c)}
                      onChange={() => toggleList("category", c)}
                    />
                    <span className="flex-1">{t(`categories.${c}`)}</span>
                    <span className="text-xs text-muted">{count}</span>
                  </label>
                );
              })}
            </fieldset>

            <fieldset className="card space-y-2 p-4">
              <legend>{t("catalog.fields.docType")}</legend>
              {(facets.data?.doc_types ?? []).map((f) => (
                <label key={f.value} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={sp.getAll("doc_type").includes(f.value)}
                    onChange={() => toggleList("doc_type", f.value)}
                  />
                  <span className="flex-1">{t(`docTypes.${f.value}`)}</span>
                  <span className="text-xs text-muted">{f.count}</span>
                </label>
              ))}
            </fieldset>

            <fieldset className="card space-y-3 p-4">
              <legend>{t("catalog.fields.branch")}</legend>
              <label htmlFor="f-branch" className="sr-only">
                {t("catalog.fields.branch")}
              </label>
              <select
                id="f-branch"
                className="input"
                value={sp.get("branch") ?? ""}
                onChange={(e) => setOne("branch", e.target.value || null)}
              >
                <option value="">{t("catalog.anyBranch")}</option>
                {(facets.data?.branches ?? []).map((b) => (
                  <option key={b.value} value={b.value}>
                    {b.label ?? b.value} ({b.count})
                  </option>
                ))}
              </select>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={sp.get("personal") === "true"}
                  onChange={(e) => setOne("personal", e.target.checked ? "true" : null)}
                />
                {t("catalog.fields.personal")}
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={sp.get("has_copy") === "true"}
                  onChange={(e) => setOne("has_copy", e.target.checked ? "true" : null)}
                />
                {t("catalog.fields.hasCopy")}
              </label>
            </fieldset>
          </aside>

          {/* результаты */}
          <section aria-labelledby="results-heading" aria-busy={result.isFetching}>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <h2 id="results-heading" className="text-lg font-semibold" aria-live="polite">
                {data ? t("catalog.found", { count: data.total }) : t("a11y.loading")}
              </h2>
              <div className="flex items-center gap-2">
                {hasAny && (
                  <button type="button" className="btn-ghost" onClick={() => setSp(new URLSearchParams())}>
                    <Icon name="reset" size={16} /> {t("catalog.resetAll")}
                  </button>
                )}
                <label htmlFor="f-sort" className="sr-only">
                  {t("catalog.sort.label")}
                </label>
                <select
                  id="f-sort"
                  className="input w-auto"
                  value={sp.get("sort") ?? "relevance"}
                  onChange={(e) => setOne("sort", e.target.value === "relevance" ? null : e.target.value)}
                >
                  {SORTS.map((s) => (
                    <option key={s} value={s}>
                      {t(`catalog.sort.${s}`)}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {data?.fuzzy && (
              <p className="mb-3 rounded-lg border border-warn/50 bg-warn/10 px-3 py-2 text-sm" role="status">
                {t("catalog.fuzzy")}
              </p>
            )}
            {data && data.expanded_terms.length > 0 && !data.fuzzy && (
              <p className="mb-3 text-sm text-muted">{t("catalog.synonyms")}</p>
            )}

            {result.isLoading && <Loading />}
            {result.isError && <ErrorState error={result.error} onRetry={() => void result.refetch()} />}
            {data && data.total === 0 && (
              <NothingFound>
                {hasAny && (
                  <button type="button" className="btn-primary" onClick={() => setSp(new URLSearchParams())}>
                    {t("catalog.resetAll")}
                  </button>
                )}
              </NothingFound>
            )}
            {data && data.total > 0 && (
              <>
                <ul className={`space-y-3 ${result.isFetching ? "opacity-60" : ""}`}>
                  {data.items.map((item) => (
                    <li key={item.id}>
                      <DocumentRow item={item} />
                    </li>
                  ))}
                </ul>
                <Pagination
                  page={page}
                  pages={data.pages}
                  onPage={(p) =>
                    update((next) => {
                      next.set("page", String(p));
                      next.set("page_keep", "1");
                    })
                  }
                />
              </>
            )}
          </section>
        </div>
      </form>
    </div>
  );
}
