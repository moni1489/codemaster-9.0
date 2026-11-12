import type { ReactNode } from "react";
import { useT } from "../../app/useT";
import { Link } from "react-router-dom";
import { useLocalePath } from "../../app/lang";
import { ApiError } from "../../lib/api";
import { Icon, type IconName } from "./Icon";

function StateBox({
  icon,
  title,
  text,
  children,
  headingLevel = 2,
}: {
  icon: IconName;
  title: string;
  text: string;
  children?: ReactNode;
  headingLevel?: 1 | 2;
}) {
  const H = headingLevel === 1 ? "h1" : "h2";
  return (
    <section className="card mx-auto my-8 max-w-2xl p-8 text-center" aria-live="polite">
      <Icon name={icon} size={40} className="mx-auto text-muted" />
      <H className="mt-3 text-2xl">{title}</H>
      <p className="mt-2 text-muted">{text}</p>
      {children && <div className="mt-5 flex flex-wrap justify-center gap-3">{children}</div>}
    </section>
  );
}

export function Loading({ label }: { label?: string }) {
  const { t } = useT();
  return (
    <div className="flex items-center justify-center gap-3 py-12 text-muted" role="status">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-line border-t-primary" aria-hidden="true" />
      {label ?? t("a11y.loading")}
    </div>
  );
}

export function NothingFound({ children }: { children?: ReactNode }) {
  const { t } = useT();
  return (
    <StateBox icon="search" title={t("states.nothingTitle")} text={t("states.nothingText")}>
      {children}
    </StateBox>
  );
}

export function NotFound() {
  const { t } = useT();
  const lp = useLocalePath();
  return (
    <div className="container-page">
      <StateBox icon="alert" title={t("states.notFoundTitle")} text={t("states.notFoundText")} headingLevel={1}>
        <Link className="btn-primary" to={lp("/")}>
          {t("states.toHome")}
        </Link>
        <Link className="btn-ghost" to={lp("/catalog")}>
          {t("states.toCatalog")}
        </Link>
      </StateBox>
    </div>
  );
}

export function Unavailable() {
  const { t } = useT();
  const lp = useLocalePath();
  return (
    <StateBox icon="lock" title={t("states.unavailableTitle")} text={t("states.unavailableText")} headingLevel={1}>
      <Link className="btn-primary" to={lp("/catalog")}>
        {t("states.toCatalog")}
      </Link>
      <Link className="btn-ghost" to={lp("/visitors/reading-room")}>
        {t("doc.readingRoom")}
      </Link>
    </StateBox>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useT();
  if (error instanceof ApiError && (error.status === 404 || error.status === 403)) return <Unavailable />;
  return (
    <StateBox icon="alert" title={t("common.error")} text={error instanceof Error ? error.message : ""}>
      {onRetry && (
        <button type="button" className="btn-primary" onClick={onRetry}>
          {t("common.retry")}
        </button>
      )}
    </StateBox>
  );
}

export function InDevelopment({ titleKey }: { titleKey: string }) {
  const { t } = useT();
  return (
    <div className="container-page py-8">
      <h1>{t(titleKey)}</h1>
      <StateBox icon="info" title={t("common.inDevelopment")} text={t("common.inDevelopmentText")} />
    </div>
  );
}
