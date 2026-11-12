import clsx from "clsx";
import { useEffect, useState } from "react";
import { useT } from "../../app/useT";
import { Link, NavLink, useLocation } from "react-router-dom";
import { useLang, useLocalePath, useSwitchLangHref } from "../../app/lang";
import { useTheme } from "../../app/theme";
import { NAV } from "../../lib/site";
import { LANGS } from "../../lib/types";
import { Icon } from "../ui/Icon";
import { Logo } from "./Logo";

const LANG_LABEL = { kk: "Қаз", ru: "Рус", en: "Eng" } as const;

export function LangSwitch() {
  const { t } = useT();
  const lang = useLang();
  const href = useSwitchLangHref();
  return (
    <ul role="list" aria-label={t("a11y.langSwitch")} className="flex gap-1">
      {LANGS.map((l) => (
        <li key={l}>
          <Link
            to={href(l)}
            hrefLang={l}
            lang={l}
            aria-current={l === lang ? "true" : undefined}
            className={clsx(
              "inline-flex min-h-12 min-w-12 items-center justify-center rounded-lg px-3 font-medium no-underline",
              l === lang ? "bg-ink text-bg" : "text-ink hover:bg-surface",
            )}
          >
            {LANG_LABEL[l]}
          </Link>
        </li>
      ))}
    </ul>
  );
}

function ThemeToggle() {
  const { t } = useT();
  const [theme, toggle] = useTheme();
  const label = theme === "dark" ? t("a11y.themeToLight") : t("a11y.themeToDark");
  return (
    <button type="button" onClick={toggle} className="btn-ghost btn-icon" aria-label={label} title={label}>
      <Icon name={theme === "dark" ? "sun" : "moon"} size={22} />
    </button>
  );
}

export function Header() {
  const { t } = useT();
  const lp = useLocalePath();
  const [open, setOpen] = useState(false);
  const location = useLocation();
  useEffect(() => setOpen(false), [location.pathname]);

  return (
    <header className="border-b border-line bg-bg">
      <div className="container-page flex min-h-[4.5rem] items-center gap-4 py-2">
        <Link to={lp("/")} className="flex min-w-0 flex-1 items-center gap-3 text-ink no-underline lg:flex-none">
          <Logo className="h-12 w-12 shrink-0" />
          <span className="truncate font-serif text-[1.25rem] leading-tight">{t("org.short")}</span>
        </Link>
        <div className="ml-auto hidden items-center gap-3 lg:flex">
          <LangSwitch />
          <ThemeToggle />
          <Link to={lp("/catalog")} className="btn-primary whitespace-nowrap">
            {t("header.catalogButton")}
          </Link>
        </div>
        <button
          type="button"
          className="btn-ghost lg:hidden"
          aria-expanded={open}
          aria-controls="mobile-nav"
          onClick={() => setOpen((v) => !v)}
        >
          <Icon name={open ? "close" : "menu"} size={22} />
          {open ? t("common.close") : t("header.menu")}
        </button>
      </div>

      <nav aria-label={t("a11y.mainNav")} className="hidden border-t border-line lg:block">
        <ul className="container-page flex flex-wrap gap-x-2">
          {NAV.map((item) => (
            <li key={item.key}>
              <NavLink
                to={lp(item.to)}
                className={({ isActive }) =>
                  clsx(
                    "block border-b-2 px-3 py-3 font-medium no-underline hover:bg-surface",
                    isActive ? "border-ink text-ink" : "border-transparent text-ink",
                  )
                }
              >
                {t(`nav.${item.key}`)}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      {open && (
        <nav id="mobile-nav" aria-label={t("a11y.mainNav")} className="border-t border-line lg:hidden">
          <ul className="container-page divide-y divide-line py-2">
            <li className="py-2">
              <Link to={lp("/catalog")} className="btn-primary w-full">
                {t("header.catalogButton")}
              </Link>
            </li>
            {NAV.filter((n) => n.key !== "catalog").map((item) => (
              <li key={item.key}>
                <NavLink to={lp(item.to)} className="block min-h-14 py-4 text-ink no-underline">
                  {t(`nav.${item.key}`)}
                </NavLink>
              </li>
            ))}
            <li className="flex items-center justify-between gap-3 py-3">
              <LangSwitch />
              <ThemeToggle />
            </li>
          </ul>
        </nav>
      )}
    </header>
  );
}
