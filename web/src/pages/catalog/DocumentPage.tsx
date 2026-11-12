import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useT } from "../../app/useT";
import { Link, useParams } from "react-router-dom";
import { useLang, useLocalePath } from "../../app/lang";
import { useTitle } from "../../app/useTitle";
import { AccessBadge, DemoBadge, TranslationNotice } from "../../components/ui/Badges";
import { Breadcrumbs } from "../../components/ui/Breadcrumbs";
import { Icon } from "../../components/ui/Icon";
import { ErrorState, Loading } from "../../components/ui/States";
import { CopyButton, ShareButton, yearsLabel } from "../../features/catalog/shared";
import { Viewer } from "../../features/catalog/Viewer";
import { apiGet } from "../../lib/api";
import type { DocumentCard } from "../../lib/types";

function Row({ label, children }: { label: string; children: ReactNode }) {
  if (children === null || children === undefined || children === "") return null;
  return (
    <div className="grid gap-1 border-b border-line py-2 sm:grid-cols-[13rem_1fr] sm:gap-4">
      <dt className="text-muted">{label}</dt>
      <dd className="min-w-0">{children}</dd>
    </div>
  );
}

function formatDate(iso: string | null, lang: string): string {
  if (!iso) return "";
  const d = new Date(`${iso}T00:00:00`);
  return d.toLocaleDateString(lang === "kk" ? "kk-KZ" : lang === "en" ? "en-GB" : "ru-RU", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export function DocumentPage() {
  const { id = "" } = useParams();
  const { t } = useT();
  const lang = useLang();
  const lp = useLocalePath();
  const q = useQuery({
    queryKey: ["document", id, lang],
    queryFn: () => apiGet<DocumentCard>(`/catalog/documents/${encodeURIComponent(id)}`, lang),
    retry: (n, err) => !(err instanceof Error && "status" in err) && n < 2,
  });
  const doc = q.data;
  useTitle(doc?.title, doc?.summary);

  if (q.isLoading) return <Loading />;
  if (q.isError || !doc)
    return (
      <div className="container-page py-8 sm:py-10">
        <ErrorState error={q.error} onRetry={() => void q.refetch()} />
      </div>
    );

  const exactDates =
    doc.date_from && doc.date_to && doc.date_from === doc.date_to
      ? formatDate(doc.date_from, lang)
      : doc.date_from && doc.date_to
        ? `${formatDate(doc.date_from, lang)} — ${formatDate(doc.date_to, lang)}`
        : "";
  const period = [doc.period_label, exactDates || yearsLabel(doc.year_from, doc.year_to)].filter(Boolean).join(" · ");

  return (
    <div className="container-page py-8 sm:py-10">
      <Breadcrumbs
        items={[
          { label: t("catalog.title"), to: "/catalog" },
          { label: `${t("doc.fund")} ${doc.fund.number}`, to: `/catalog/funds/${doc.fund.id}` },
          { label: `${t("doc.inventory")} ${doc.inventory.number}`, to: `/catalog/inventories/${doc.inventory.id}` },
          { label: `${t("doc.case")} ${doc.case.number}`, to: `/catalog/cases/${doc.case.id}` },
          { label: doc.title },
        ]}
      />

      <header className="space-y-3">
        <div className="flex flex-wrap gap-2">
          <AccessBadge access={doc.file_access} />
          {doc.is_demo && <DemoBadge />}
        </div>
        <h1>{doc.title}</h1>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-muted">{t("doc.cipher")}:</span>
          <code className="cipher rounded bg-surface-2 px-2 py-1 text-sm">{doc.cipher}</code>
          <CopyButton text={doc.cipher} label={t("doc.copyCipher")} />
          <ShareButton title={doc.title} />
        </div>
        <TranslationNotice info={doc.translation} />
      </header>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="min-w-0 space-y-6">
          {doc.pages.length > 0 ? (
            <Viewer pages={doc.pages} title={doc.title} />
          ) : (
            <section className="card p-6" aria-labelledby="no-copy">
              <div className="flex items-start gap-3">
                <Icon name="lock" size={28} className="shrink-0 text-muted" />
                <div>
                  <h2 id="no-copy">
                    {doc.has_digital_copy ? t("doc.noCopyTitle") : t("catalog.noCopy")}
                  </h2>
                  <p className="mt-2 text-muted">{t(`access.${doc.file_access}Hint`)}</p>
                  {doc.access_conditions && (
                    <div className="mt-4">
                      <h3 className="font-semibold">{t("doc.accessConditions")}</h3>
                      <p className="mt-1">{doc.access_conditions}</p>
                    </div>
                  )}
                  <Link to={lp("/visitors/reading-room")} className="mt-4 inline-block">
                    {t("doc.readingRoom")} →
                  </Link>
                </div>
              </div>
            </section>
          )}
          {doc.summary && (
            <section>
              <h2>{t("doc.summary")}</h2>
              <p className="mt-2 leading-relaxed">{doc.summary}</p>
            </section>
          )}
          {doc.historical_note && (
            <section>
              <h2>{t("doc.historicalNote")}</h2>
              <p className="mt-2 leading-relaxed">{doc.historical_note}</p>
            </section>
          )}
        </div>

        <aside className="min-w-0 space-y-6">
          <section className="card p-4">
            <h2>{t("doc.metadata")}</h2>
            <dl className="mt-2">
              <Row label={t("doc.fund")}>
                <Link to={lp(`/catalog/funds/${doc.fund.id}`)}>
                  {doc.fund.number} — {doc.fund.title}
                </Link>
              </Row>
              <Row label={t("doc.inventory")}>
                <Link to={lp(`/catalog/inventories/${doc.inventory.id}`)}>
                  {doc.inventory.number} — {doc.inventory.title}
                </Link>
              </Row>
              <Row label={t("doc.case")}>
                <Link to={lp(`/catalog/cases/${doc.case.id}`)}>
                  {doc.case.number} — {doc.case.title}
                </Link>
              </Row>
              <Row label={t("doc.date")}>{doc.date_verified ? period : `${period} (${t("catalog.unverifiedDate").toLowerCase()})`}</Row>
              <Row label={t("doc.docType")}>{t(`docTypes.${doc.doc_type}`)}</Row>
              <Row label={t("doc.category")}>{t(`categories.${doc.category}`)}</Row>
              <Row label={t("doc.language")}>{doc.language}</Row>
              <Row label={t("doc.author")}>{doc.author_org}</Row>
              <Row label={t("doc.place")}>{doc.place}</Row>
              <Row label={t("doc.topic")}>{doc.topic}</Row>
              <Row label={t("doc.sheets")}>{doc.sheets}</Row>
              <Row label={t("doc.sheetsCount")}>{doc.sheets_count ?? null}</Row>
              <Row label={t("doc.storage")}>{doc.storage_location}</Row>
              <Row label={t("doc.branch")}>{doc.branch?.name}</Row>
              <Row label={t("doc.tags")}>
                {doc.tags.length > 0 && (
                  <ul className="flex flex-wrap gap-1">
                    {doc.tags.map((tag) => (
                      <li key={tag}>
                        <Link to={lp(`/catalog?topic=${encodeURIComponent(tag)}`)} className="badge border-line no-underline">
                          {tag}
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </Row>
            </dl>
          </section>
        </aside>
      </div>
    </div>
  );
}
