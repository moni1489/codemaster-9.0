import clsx from "clsx";
import { useT } from "../../app/useT";
import type { FileAccess, TranslationInfo } from "../../lib/types";
import { Icon } from "./Icon";

export function DemoBadge({ short = false }: { short?: boolean }) {
  const { t } = useT();
  return (
    <span className="badge border-warn/50 bg-warn/10 text-warn" title={t("common.demo")}>
      {short ? t("common.demoShort") : t("common.demo")}
    </span>
  );
}

const ACCESS_STYLE: Record<FileAccess, string> = {
  open: "border-ok/50 bg-ok/10 text-ok",
  restricted: "border-warn/50 bg-warn/10 text-warn",
  closed: "border-danger/50 bg-danger/10 text-danger",
};

/** Статус доступа: цвет + иконка + текст (не только цвет — WCAG 1.4.1). Неизвестное значение = закрыто. */
export function AccessBadge({ access }: { access: FileAccess }) {
  const { t } = useT();
  const safe: FileAccess = access in ACCESS_STYLE ? access : "closed";
  return (
    <span className={clsx("badge", ACCESS_STYLE[safe])}>
      <Icon name={safe === "open" ? "image" : "lock"} size={14} />
      {t(`access.${safe}`)}
    </span>
  );
}

export function UnverifiedBadge({ label }: { label: string }) {
  return (
    <span className="badge border-line bg-surface-2 text-muted">
      <Icon name="alert" size={14} />
      {label}
    </span>
  );
}

/** Уведомление о фолбэке перевода или машинном переводе (D-009, Д §3.3). */
export function TranslationNotice({ info }: { info: TranslationInfo }) {
  const { t } = useT();
  if (info.is_fallback) {
    return (
      <p className="flex items-start gap-2 rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm" role="note">
        <Icon name="info" size={18} className="mt-0.5 shrink-0" />
        {t("translation.fallback", { lang: t(`translation.langName.${info.lang}`) })}
      </p>
    );
  }
  if (info.status === "machine") {
    return (
      <p className="flex items-start gap-2 text-sm text-muted" role="note">
        <Icon name="info" size={16} className="mt-0.5 shrink-0" />
        {t("translation.machine")}
      </p>
    );
  }
  return null;
}
