import { useQuery } from "@tanstack/react-query";
import { useT } from "../../app/useT";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useLang, useLocalePath } from "../../app/lang";
import { useTitle } from "../../app/useTitle";
import { DemoBadge, TranslationNotice } from "../../components/ui/Badges";
import { Breadcrumbs, type Crumb } from "../../components/ui/Breadcrumbs";
import { Icon } from "../../components/ui/Icon";
import { ErrorState, Loading, NothingFound } from "../../components/ui/States";
import { DocumentRow, yearsLabel } from "../../features/catalog/shared";
import { apiGet } from "../../lib/api";
import type { ChildItem, HierarchyNode } from "../../lib/types";

const CHILD_ROUTE = { fund: "inventories", inventory: "cases", case: "" } as const;

function ChildList({ items, route, label }: { items: ChildItem[]; route: string; label: string }) {
  const { t } = useT();
  const lp = useLocalePath();
  return (
    <ul className="grid gap-3 md:grid-cols-2">
      {items.map((c) => (
        <li key={c.id}>
          <Link to={lp(`/catalog/${route}/${c.id}`)} className="card-link h-full p-4 sm:p-5">
            <p className="text-sm text-muted">
              {label} {c.number}
              {c.year_from ? ` · ${yearsLabel(c.year_from, c.year_to)}` : ""}
            </p>
            <p className="mt-1 text-lg font-semibold leading-snug">{c.title}</p>
            <p className="cipher mt-1 text-sm text-muted">{c.cipher}</p>
            {c.count !== null && <p className="mt-2 text-sm text-primary">{t("hierarchy.docsCount", { count: c.count })}</p>}
          </Link>
        </li>
      ))}
    </ul>
  );
}

export function FundsPage() {
  const { t } = useT();
  const lang = useLang();
  const [sp] = useSearchParams();
  const personal = sp.get("personal") === "true";
  const title = personal ? t("catalog.personalFunds") : t("hierarchy.funds");
  useTitle(title, t("hierarchy.fundsLead"));
  const q = useQuery({
    queryKey: ["funds", lang, personal],
    queryFn: () => apiGet<ChildItem[]>("/catalog/funds", lang, personal ? { personal: true } : {}),
  });
  return (
    <div className="container-page py-8 sm:py-10">
      <Breadcrumbs items={[{ label: t("catalog.title"), to: "/catalog" }, { label: title }]} />
      <h1>{title}</h1>
      <p className="lead mt-2">{t("hierarchy.fundsLead")}</p>
      <div className="mt-6">
        {q.isLoading && <Loading />}
        {q.isError && <ErrorState error={q.error} onRetry={() => void q.refetch()} />}
        {q.data && q.data.length === 0 && <NothingFound />}
        {q.data && q.data.length > 0 && <ChildList items={q.data} route="funds" label={t("doc.fund")} />}
      </div>
    </div>
  );
}

export function HierarchyPage({ level }: { level: "fund" | "inventory" | "case" }) {
  const { id = "" } = useParams();
  const { t } = useT();
  const lang = useLang();
  const endpoint = { fund: "funds", inventory: "inventories", case: "cases" }[level];
  const q = useQuery({
    queryKey: ["node", level, id, lang],
    queryFn: () => apiGet<HierarchyNode>(`/catalog/${endpoint}/${encodeURIComponent(id)}`, lang),
    retry: false,
  });
  const node = q.data;
  useTitle(node ? `${t(`hierarchy.level.${level}`)} ${node.number}: ${node.title}` : undefined, node?.summary);

  if (q.isLoading) return <Loading />;
  if (q.isError || !node)
    return (
      <div className="container-page py-8 sm:py-10">
        <ErrorState error={q.error} />
      </div>
    );

  const parentRoutes = ["funds", "inventories"];
  const crumbs: Crumb[] = [
    { label: t("catalog.title"), to: "/catalog" },
    { label: t("hierarchy.funds"), to: "/catalog/funds" },
    ...node.parents.map((p, i) => ({
      label: `${t(`hierarchy.level.${i === 0 ? "fund" : "inventory"}`)} ${p.number}`,
      to: `/catalog/${parentRoutes[i]}/${p.id}`,
    })),
    { label: `${t(`hierarchy.level.${level}`)} ${node.number}` },
  ];
  const childRoute = CHILD_ROUTE[level];

  return (
    <div className="container-page py-8 sm:py-10">
      <Breadcrumbs items={crumbs} />
      <header className="space-y-2">
        <p className="text-muted">
          {t(`hierarchy.level.${level}`)} {node.number}
          {node.year_from ? ` · ${yearsLabel(node.year_from, node.year_to)}` : ""}
        </p>
        <h1>{node.title}</h1>
        <p className="cipher text-sm text-muted">{node.cipher}</p>
        <div className="flex flex-wrap gap-2">
          {node.is_personal_fund && <span className="badge border-accent/50 text-accent">{t("doc.personalFund")}</span>}
          {node.branch && <span className="badge border-line">{node.branch.name}</span>}
          {node.is_demo && <DemoBadge />}
        </div>
        <TranslationNotice info={node.translation} />
      </header>

      {(node.historical_note || node.summary) && (
        <section className="mt-6 max-w-3xl">
          <h2>{t("doc.historicalNote")}</h2>
          <p className="mt-2 leading-relaxed">{node.historical_note ?? node.summary}</p>
        </section>
      )}
      {node.restricted_note && (
        <section className="mt-4 flex max-w-3xl gap-3 rounded-lg border border-warn/50 bg-warn/10 p-4" aria-label={t("hierarchy.restrictedNote")}>
          <Icon name="lock" size={20} className="shrink-0 text-warn" />
          <div>
            <h2 className="text-[1.125rem]">{t("hierarchy.restrictedNote")}</h2>
            <p className="mt-1 text-sm">{node.restricted_note}</p>
          </div>
        </section>
      )}

      {node.children.length > 0 && (
        <section className="mt-8">
          <h2 className="mb-3">{level === "fund" ? t("hierarchy.inventories") : t("hierarchy.cases")}</h2>
          <ChildList items={node.children} route={childRoute} label={t(`hierarchy.level.${level === "fund" ? "inventory" : "case"}`)} />
        </section>
      )}
      {level === "case" && (
        <section className="mt-8">
          <h2 className="mb-3">{t("hierarchy.documents")}</h2>
          {node.documents.length === 0 ? (
            <NothingFound />
          ) : (
            <ul className="space-y-3">
              {node.documents.map((d) => (
                <li key={d.id}>
                  <DocumentRow item={d} />
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
