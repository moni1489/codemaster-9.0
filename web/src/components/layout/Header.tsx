import clsx from "clsx";
import { type FormEvent, useEffect, useState } from "react";
import { useT } from "../../app/useT";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { useLang, useLocalePath, useSwitchLangHref } from "../../app/lang";
import { useTheme } from "../../app/theme";
import { SITE, NAV } from "../../lib/site";
import { LANGS } from "../../lib/types";
import { Icon } from "../ui/Icon";
import { Logo } from "./Logo";

const LANG_LABEL = { kk: "ҚАЗ", ru: "РУС", en: "ENG" } as const;

function LangSwitch() {
  const { t } = useT();
  const lang = useLang();
  const href = useSwitchLangHref();
  return (
    <div role="group" aria-label={t("a11y.langSwitch")} className="flex overflow-hidden rounded-lg border border-line">
      {LANGS.map((l) => (
        <Link
          key={l}
          to={href(l)}
          hrefLang={l}
          lang={l}
          aria-current={l === lang ? "true" : undefined}
          className={clsx(
            "px-2 py-1 text-xs font-semibold no-underline",
            l === lang ? "bg-primary text-primary-ink" : "text-ink hover:bg-surface-2",
          )}
        >
          {LANG_LABEL[l]}
        </Link>
      ))}
    </div>
  );
}

function ThemeToggle() {
  const { t } = useT();
  const [theme, toggle] = useTheme();
  const label = theme === "dark" ? t("a11y.themeToLight") : t("a11y.themeToDark");
  return (
    <button type="button" onClick={toggle} className="btn-ghost px-2 py-1" aria-label={label} title={label}>
      <Icon name={theme === "dark" ? "sun" : "moon"} size={18} />
    </button>
  );
}

function HeaderSearch({ onDone }: { onDone?: () => void }) {
  const { t } = useT();
  const lp = useLocalePath();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const query = q.trim();
    navigate(lp(`/catalog${query ? `?q=${encodeURIComponent(query)}` : ""}`));
    onDone?.();
  };
  return (
    <form role="search" onSubmit={submit} className="flex w-full items-center gap-2">
      <label htmlFor="header-search" className="sr-only">
        {t("header.searchPlaceholder")}
      </label>
      <input
        id="header-search"
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={t("header.searchPlaceholder")}
        className="input"
        maxLength={300}
      />
      <button type="submit" className="btn-primary" aria-label={t("header.search")}>
        <Icon name="search" size={18} />
        <span className="hidden sm:inline">{t("header.search")}</span>
      </button>
    </form>
  );
}

export function Header() {
  const { t } = useT();
  const lp = useLocalePath();
  const [open, setOpen] = useState(false);
  const location = useLocation();
  useEffect(() => setOpen(false), [location.pathname]);

  return (
    <header className="border-b border-line bg-surface">
      {/* верхняя строка: контакты, соцсети, язык, тема */}
      <div className="border-b border-line bg-surface-2 text-sm">
        <div className="container-page flex flex-wrap items-center justify-between gap-2 py-1.5">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-muted">
            <a href={`tel:${SITE.phoneReception.replace(/[^\d+]/g, "")}`} className="inline-flex items-center gap-1 text-ink no-underline hover:underline">
              <Icon name="phone" size={14} />
              <span className="sr-only sm:not-sr-only">{t("header.phone")}:</span> {SITE.phoneReception}
            </a>
            <a href={`mailto:${SITE.email}`} className="hidden items-center gap-1 text-ink no-underline hover:underline md:inline-flex">
              <Icon name="mail" size={14} /> {SITE.email}
            </a>
            <a href={SITE.social.instagram.url} target="_blank" rel="noopener noreferrer" className="text-ink" aria-label={`Instagram ${SITE.social.instagram.handle} (${t("a11y.external")})`}>
              <Icon name="instagram" size={16} />
            </a>
            <a href={SITE.social.facebook.url} target="_blank" rel="noopener noreferrer" className="text-ink" aria-label={`Facebook ${SITE.social.facebook.handle} (${t("a11y.external")})`}>
              <Icon name="facebook" size={16} />
            </a>
          </div>
          <div className="flex items-center gap-2">
            <LangSwitch />
            <ThemeToggle />
          </div>
        </div>
      </div>

      {/* логотип, поиск, кнопка каталога */}
      <div className="container-page flex items-center gap-4 py-3">
        <Link to={lp("/")} className="flex min-w-0 flex-1 items-center gap-3 text-ink no-underline lg:flex-none">
          <Logo className="h-11 w-11 shrink-0" />
          <span className="min-w-0">
            <span className="block font-serif text-lg font-bold leading-tight">{t("org.short")}</span>
            <span className="hidden max-w-md text-xs leading-snug text-muted md:block">{t("org.full")}</span>
          </span>
        </Link>
        <div className="hidden flex-1 lg:block">
          <HeaderSearch />
        </div>
        <Link to={lp("/catalog")} className="btn-primary hidden whitespace-nowrap sm:inline-flex">
          <Icon name="folder" size={18} />
          {t("header.catalogButton")}
        </Link>
        <button
          type="button"
          className="btn-ghost px-2 lg:hidden"
          aria-expanded={open}
          aria-controls="mobile-nav"
          aria-label={open ? t("a11y.closeMenu") : t("a11y.openMenu")}
          onClick={() => setOpen((v) => !v)}
        >
          <Icon name={open ? "close" : "menu"} />
        </button>
      </div>

      {/* навигация: десктоп */}
      <nav aria-label={t("a11y.mainNav")} className="hidden border-t border-line lg:block">
        <ul className="container-page flex flex-wrap gap-1 py-1">
          {NAV.map((item) => (
            <li key={item.key}>
              <NavLink
                to={lp(item.to)}
                className={({ isActive }) =>
                  clsx(
                    "block rounded-md px-3 py-2 text-sm font-medium no-underline",
                    isActive ? "bg-primary/10 text-primary" : "text-ink hover:bg-surface-2",
                  )
                }
              >
                {t(`nav.${item.key}`)}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      {/* навигация: мобильная */}
      {open && (
        <div id="mobile-nav" className="border-t border-line lg:hidden">
          <div className="container-page space-y-3 py-3">
            <HeaderSearch onDone={() => setOpen(false)} />
            <nav aria-label={t("a11y.mainNav")}>
              <ul className="grid grid-cols-1 gap-1 sm:grid-cols-2">
                <li>
                  <Link to={lp("/catalog")} className="block rounded-md bg-primary px-3 py-3 font-medium text-primary-ink no-underline">
                    {t("header.catalogButton")}
                  </Link>
                </li>
                {NAV.filter((n) => n.key !== "catalog").map((item) => (
                  <li key={item.key}>
                    <NavLink to={lp(item.to)} className="block rounded-md px-3 py-3 text-ink no-underline hover:bg-surface-2">
                      {t(`nav.${item.key}`)}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </nav>
          </div>
        </div>
      )}
    </header>
  );
}
