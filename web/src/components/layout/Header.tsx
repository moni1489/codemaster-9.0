import clsx from "clsx";
import { useEffect, useState } from "react";
import { useT } from "../../app/useT";
import { Link, NavLink, useLocation } from "react-router-dom";
import { useLang, useLocalePath, useSwitchLangHref } from "../../app/lang";
import { setLowVision, useLowVision, type LowVision } from "../../app/lowVision";
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
    <ul aria-label={t("a11y.langSwitch")} className="-ml-2 flex gap-1">
      {LANGS.map((l) => (
        <li key={l}>
          <Link
            to={href(l)}
            hrefLang={l}
            lang={l}
            aria-current={l === lang ? "true" : undefined}
            className={clsx(
              "inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg px-2 font-medium no-underline",
              l === lang ? "bg-ink text-bg" : "text-ink hover:bg-surface-2",
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

/** Группа «одна из»: кнопки с aria-pressed. */
function Choice<K extends string | number | boolean>({
  legend,
  value,
  options,
  onPick,
}: {
  legend: string;
  value: K;
  options: { v: K; label: string; className?: string; text?: string }[];
  onPick: (v: K) => void;
}) {
  return (
    <fieldset>
      <legend className="mb-2 font-semibold">{legend}</legend>
      <div className="flex flex-wrap gap-2">
        {options.map((o) => (
          <button
            key={String(o.v)}
            type="button"
            aria-pressed={value === o.v}
            aria-label={o.text ? o.label : undefined}
            title={o.label}
            onClick={() => onPick(o.v)}
            className={clsx(
              "btn min-w-12 border-2 px-3",
              value === o.v ? "border-ink ring-2 ring-ink ring-offset-2 ring-offset-bg" : "border-line",
              o.className ?? "bg-bg text-ink",
            )}
          >
            {o.text ?? o.label}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

function LowVisionPanel({ lv }: { lv: LowVision }) {
  const { t } = useT();
  // телефон: настройки свёрнуты, чтобы не занимать первый экран; планшет и шире — раскрыты
  const [expanded, setExpanded] = useState(() => window.matchMedia("(min-width: 640px)").matches);
  return (
    <section aria-label={t("lv.panel")} className="border-b-2 border-ink bg-bg">
      <div className="container-page flex flex-wrap gap-2 py-3 sm:hidden">
        <button type="button" className="btn-ghost flex-1 px-3" aria-expanded={expanded} aria-controls="lv-settings" onClick={() => setExpanded((v) => !v)}>
          <Icon name={expanded ? "close" : "filter"} size={20} /> {t("lv.panel")}
        </button>
        <button type="button" className="btn-primary flex-1 px-3" onClick={() => setLowVision({ on: false })}>
          <Icon name="eye" size={20} /> {t("lv.off")}
        </button>
      </div>
      <div id="lv-settings" className={clsx("container-page flex-col gap-5 py-5 sm:flex sm:flex-row sm:flex-wrap sm:items-end sm:gap-8", expanded ? "flex" : "hidden")}>
        <Choice
          legend={t("lv.fontSize")}
          value={lv.fs}
          onPick={(fs) => setLowVision({ fs })}
          options={[
            { v: 1, label: t("lv.fs1"), text: "А", className: "bg-bg text-ink text-[1rem]" },
            { v: 2, label: t("lv.fs2"), text: "А", className: "bg-bg text-ink text-[1.25rem]" },
            { v: 3, label: t("lv.fs3"), text: "А", className: "bg-bg text-ink text-[1.5rem]" },
          ]}
        />
        <Choice
          legend={t("lv.colors")}
          value={lv.scheme}
          onPick={(scheme) => setLowVision({ scheme })}
          options={[
            { v: "bw", label: t("lv.bw"), text: "Ц", className: "!bg-white !text-black" },
            { v: "wb", label: t("lv.wb"), text: "Ц", className: "!bg-black !text-white" },
            { v: "blue", label: t("lv.blue"), text: "Ц", className: "!bg-[#9dd1ff] !text-[#063462]" },
          ]}
        />
        <Choice
          legend={t("lv.images")}
          value={lv.img}
          onPick={(img) => setLowVision({ img })}
          options={[
            { v: true, label: t("lv.imgOn") },
            { v: false, label: t("lv.imgOff") },
          ]}
        />
        <Choice
          legend={t("lv.spacing")}
          value={lv.wide}
          onPick={(wide) => setLowVision({ wide })}
          options={[
            { v: false, label: t("lv.normal") },
            { v: true, label: t("lv.wide") },
          ]}
        />
        <button type="button" className="btn-primary hidden sm:ml-auto sm:inline-flex" onClick={() => setLowVision({ on: false })}>
          <Icon name="eye" size={22} /> {t("lv.off")}
        </button>
      </div>
    </section>
  );
}

export function Header() {
  const { t } = useT();
  const lp = useLocalePath();
  const lv = useLowVision();
  const [open, setOpen] = useState(false);
  const location = useLocation();
  useEffect(() => setOpen(false), [location.pathname]);

  return (
    <header className="bg-bg">
      {/* служебная полоса: язык и версия для слабовидящих — на виду и на телефоне */}
      <div className="border-b border-line bg-surface">
        <div className="container-page flex min-h-12 flex-wrap items-center justify-between gap-2 py-1">
          <LangSwitch />
          <div className="flex items-center gap-2">
            {!lv.on && (
              <button
                type="button"
                className="btn-ghost min-h-11 px-3"
                onClick={() => setLowVision({ on: true })}
                title={t("lv.toggle")}
              >
                <Icon name="eye" size={22} />
                <span className="sm:hidden">{t("lv.short")}</span>
                <span className="hidden sm:inline">{t("lv.toggle")}</span>
              </button>
            )}
            {!lv.on && (
              <span className="hidden sm:block">
                <ThemeToggle />
              </span>
            )}
          </div>
        </div>
      </div>
      {lv.on && <LowVisionPanel lv={lv} />}

      <div className="border-b border-line">
        <div className="container-page flex min-h-[4.5rem] flex-wrap items-center gap-3 py-2">
          <Link to={lp("/")} className="flex flex-1 items-center gap-2 text-ink no-underline sm:gap-3 lg:flex-none">
            <Logo className="h-10 w-10 shrink-0 sm:h-12 sm:w-12" />
            <span className="max-w-[12rem] text-[1rem] font-semibold leading-tight sm:max-w-none sm:text-[1.25rem]">
              {t("org.short")}
            </span>
          </Link>
          <Link to={lp("/catalog")} className="btn-primary ml-auto hidden whitespace-nowrap lg:inline-flex">
            <Icon name="search" size={20} /> {t("header.catalogButton")}
          </Link>
          <button
            type="button"
            className="btn-ghost shrink-0 px-4 lg:hidden"
            aria-expanded={open}
            aria-controls="mobile-nav"
            onClick={() => setOpen((v) => !v)}
          >
            <Icon name={open ? "close" : "menu"} size={22} />
            {open ? t("common.close") : t("header.menu")}
          </button>
        </div>

        <nav aria-label={t("a11y.mainNav")} className="hidden border-t border-line lg:block">
          <ul className="container-page flex flex-wrap">
            {NAV.map((item, i) => (
              <li key={item.key} className={i === 0 ? "-ml-2" : undefined}>
                <NavLink
                  to={lp(item.to)}
                  className={({ isActive }) =>
                    clsx(
                      "block border-b-4 px-2 py-3 text-[0.9375rem] font-medium text-ink no-underline hover:bg-surface",
                      isActive ? "border-primary" : "border-transparent",
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
              <li className="py-3">
                <Link to={lp("/catalog")} className="btn-primary w-full">
                  <Icon name="search" size={20} /> {t("header.catalogButton")}
                </Link>
              </li>
              {NAV.filter((n) => n.key !== "catalog").map((item) => (
                <li key={item.key}>
                  <NavLink to={lp(item.to)} className="flex min-h-14 items-center justify-between py-3 text-lg text-ink no-underline">
                    {t(`nav.${item.key}`)}
                    <Icon name="right" size={20} className="text-muted" />
                  </NavLink>
                </li>
              ))}
              {!lv.on && (
                <li className="py-3">
                  <ThemeToggle />
                </li>
              )}
            </ul>
          </nav>
        )}
      </div>
    </header>
  );
}
