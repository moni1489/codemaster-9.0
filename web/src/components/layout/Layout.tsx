import { useEffect } from "react";
import { useT } from "../../app/useT";
import { Outlet, useLocation } from "react-router-dom";
import { useSyncLang } from "../../app/lang";
import { Footer } from "./Footer";
import { Header } from "./Header";

export function Layout() {
  const { t } = useT();
  useSyncLang();
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [pathname]);

  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only-focusable absolute left-2 top-2 z-50 rounded bg-primary px-3 py-2 text-primary-ink">
        {t("a11y.skip")}
      </a>
      <Header />
      <main id="main" tabIndex={-1} className="flex-1 outline-none">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}
