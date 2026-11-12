import { useQuery } from "@tanstack/react-query";
import { useT } from "../../app/useT";
import { Link } from "react-router-dom";
import { useLang, useLocalePath } from "../../app/lang";
import { apiGet } from "../../lib/api";
import { NAV, SITE } from "../../lib/site";
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
      <div className="container-page grid gap-10 py-12 md:grid-cols-2 lg:grid-cols-[3fr_2fr_2fr]">
        <section aria-labelledby="f-contacts">
          <h2 id="f-contacts" className="text-[1.25rem]">
            {t("org.short")}
          </h2>
          <ul className="mt-4 space-y-3">
            <li className="flex gap-3">
              <Icon name="pin" size={20} className="mt-1 shrink-0 text-muted" />
              <span>
                <span className="sr-only">{t("footer.address")}: </span>
                {main?.address ?? "г. Усть-Каменогорск, ул. Бейбітшілік, 26/1"}
              </span>
            </li>
            <li className="flex gap-3">
              <Icon name="phone" size={20} className="mt-1 shrink-0 text-muted" />
              <a href={`tel:${SITE.phoneReception.replace(/[^\d+]/g, "")}`}>{SITE.phoneReception}</a>
            </li>
            <li className="flex gap-3">
              <Icon name="mail" size={20} className="mt-1 shrink-0 text-muted" />
              <a href={`mailto:${SITE.email}`}>{SITE.email}</a>
            </li>
            <li className="flex gap-3">
              <Icon name="clock" size={20} className="mt-1 shrink-0 text-muted" />
              <span>
                <span className="sr-only">{t("footer.hours")}: </span>
                {main?.hours ?? "Пн–Пт 8:00–17:00"}
              </span>
            </li>
          </ul>
          <ul className="mt-5 flex flex-wrap gap-2">
            <li>
              <ExternalLink href={SITE.social.instagram.url} className="chip gap-2">
                <Icon name="instagram" size={20} /> Instagram
              </ExternalLink>
            </li>
            <li>
              <ExternalLink href={SITE.social.facebook.url} className="chip gap-2">
                <Icon name="facebook" size={20} /> Facebook
              </ExternalLink>
            </li>
          </ul>
        </section>

        <nav aria-label={t("a11y.footerNav")}>
          <h2 className="text-[1.25rem]">{t("footer.sections")}</h2>
          <ul className="mt-4 space-y-1">
            {NAV.map((item) => (
              <li key={item.key}>
                <Link to={lp(item.to)} className="inline-flex min-h-11 items-center">
                  {t(`nav.${item.key}`)}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        <section aria-labelledby="f-gov">
          <h2 id="f-gov" className="text-[1.25rem]">
            {t("footer.gov")}
          </h2>
          <ul className="mt-4 space-y-1">
            {SITE.gov.map((g) => (
              <li key={g.url}>
                <ExternalLink href={g.url} className="inline-flex min-h-11 items-center gap-1">
                  {g.label}
                </ExternalLink>
              </li>
            ))}
          </ul>
        </section>
      </div>
      <div className="border-t border-line">
        <div className="container-page space-y-2 pb-28 pt-6 text-sm text-muted sm:pb-8">
          <p>{t("org.full")}</p>
          <p>{t("footer.infoOnly")}</p>
          <p>
            © 1940–{new Date().getFullYear()} {t("org.short")}. {t("footer.copyright")}{" "}
            <Link to={lp("/about/privacy")}>{t("footer.privacy")}</Link>
          </p>
          <p>
            {t("footer.photoCredit")}:{" "}
            <a href="https://commons.wikimedia.org/wiki/File:Strelka_oskemen.jpg" target="_blank" rel="noopener noreferrer">
              Iskanderov Damir, Wikimedia Commons
            </a>
            ,{" "}
            <a href="https://creativecommons.org/licenses/by/3.0" target="_blank" rel="noopener noreferrer">
              CC BY 3.0
            </a>
          </p>
        </div>
      </div>
    </footer>
  );
}
