import { useQuery } from "@tanstack/react-query";
import { useT } from "../../app/useT";
import { Link } from "react-router-dom";
import { useLang, useLocalePath } from "../../app/lang";
import { apiGet } from "../../lib/api";
import { SITE } from "../../lib/site";
import type { Branch } from "../../lib/types";
import { ExternalLink } from "../ui/ExternalLink";
import { Icon } from "../ui/Icon";

export function Footer() {
  const { t } = useT();
  const lang = useLang();
  const lp = useLocalePath();
  const { data } = useQuery({
    queryKey: ["branches", lang],
    queryFn: () => apiGet<Branch[]>("/branches", lang),
    staleTime: 10 * 60_000,
  });
  const main = data?.find((b) => b.type === "main");

  return (
    <footer className="mt-16 border-t border-line bg-surface">
      <div className="container-page grid gap-8 py-10 md:grid-cols-2 lg:grid-cols-4">
        <section>
          <h2 className="font-serif text-lg">{t("org.short")}</h2>
          <p className="mt-2 text-sm text-muted">{t("org.full")}</p>
        </section>
        <section aria-labelledby="f-contacts">
          <h2 id="f-contacts" className="font-serif text-lg">
            {t("footer.contacts")}
          </h2>
          <ul className="mt-2 space-y-2 text-sm">
            <li className="flex gap-2">
              <Icon name="pin" size={16} className="mt-0.5 shrink-0 text-muted" />
              <span>
                <span className="sr-only">{t("footer.address")}: </span>
                {main?.address ?? "070000, г. Усть-Каменогорск, ул. Бейбітшілік, 26/1"}
              </span>
            </li>
            <li className="flex gap-2">
              <Icon name="phone" size={16} className="mt-0.5 shrink-0 text-muted" />
              <a href={`tel:${SITE.phoneReception.replace(/[^\d+]/g, "")}`}>{SITE.phoneReception}</a>
            </li>
            <li className="flex gap-2">
              <Icon name="mail" size={16} className="mt-0.5 shrink-0 text-muted" />
              <a href={`mailto:${SITE.email}`}>{SITE.email}</a>
            </li>
            <li className="flex gap-2">
              <Icon name="clock" size={16} className="mt-0.5 shrink-0 text-muted" />
              <span>
                <span className="sr-only">{t("footer.hours")}: </span>
                {main?.hours ?? "Пн–Пт 8:00–17:00"}
              </span>
            </li>
          </ul>
          <Link to={lp("/branches")} className="mt-3 inline-block text-sm">
            {t("nav.branches")} →
          </Link>
        </section>
        <section aria-labelledby="f-social">
          <h2 id="f-social" className="font-serif text-lg">
            {t("footer.social")}
          </h2>
          <ul className="mt-2 space-y-2 text-sm">
            <li>
              <ExternalLink href={SITE.social.instagram.url} className="inline-flex items-center gap-2">
                <Icon name="instagram" size={18} /> Instagram {SITE.social.instagram.handle}
              </ExternalLink>
            </li>
            <li>
              <ExternalLink href={SITE.social.facebook.url} className="inline-flex items-center gap-2">
                <Icon name="facebook" size={18} /> Facebook {SITE.social.facebook.handle}
              </ExternalLink>
            </li>
          </ul>
        </section>
        <section aria-labelledby="f-gov">
          <h2 id="f-gov" className="font-serif text-lg">
            {t("footer.gov")}
          </h2>
          <ul className="mt-2 space-y-1 text-sm">
            {SITE.gov.map((g) => (
              <li key={g.url}>
                <ExternalLink href={g.url}>{g.label}</ExternalLink>
              </li>
            ))}
          </ul>
        </section>
      </div>
      <div className="border-t border-line">
        <div className="container-page flex flex-col gap-2 py-4 text-xs text-muted md:flex-row md:items-center md:justify-between">
          <p>
            © 1940–{new Date().getFullYear()} {t("org.short")}. {t("footer.copyright")}
          </p>
          <p className="flex flex-wrap gap-4">
            <Link to={lp("/about/privacy")}>{t("footer.privacy")}</Link>
          </p>
        </div>
        <p className="container-page pb-4 text-xs text-muted">{t("footer.infoOnly")}</p>
      </div>
    </footer>
  );
}
