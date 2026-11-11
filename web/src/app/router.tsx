import { lazy, Suspense, type ReactNode } from "react";
import { createBrowserRouter, Navigate, useLocation, useParams } from "react-router-dom";
import { Layout } from "../components/layout/Layout";
import { InDevelopment, Loading, NotFound } from "../components/ui/States";
import { isLang } from "./lang";

// Разделение кода по маршрутам (ТЗ §7.2)
const HomePage = lazy(() => import("../pages/HomePage").then((m) => ({ default: m.HomePage })));
const CatalogPage = lazy(() => import("../pages/catalog/CatalogPage").then((m) => ({ default: m.CatalogPage })));
const DocumentPage = lazy(() => import("../pages/catalog/DocumentPage").then((m) => ({ default: m.DocumentPage })));
const FundsPage = lazy(() => import("../pages/catalog/HierarchyPages").then((m) => ({ default: m.FundsPage })));
const HierarchyPage = lazy(() =>
  import("../pages/catalog/HierarchyPages").then((m) => ({ default: m.HierarchyPage })),
);

const page = (node: ReactNode) => <Suspense fallback={<Loading />}>{node}</Suspense>;

function preferredLang(): string {
  const nav = (typeof navigator !== "undefined" && navigator.language) || "ru";
  if (nav.startsWith("kk")) return "kk";
  if (nav.startsWith("en")) return "en";
  return "ru";
}

function RootRedirect() {
  const { search } = useLocation();
  return <Navigate to={`/${preferredLang()}${search}`} replace />;
}

/** Неизвестный префикс языка → тот же путь на русском. */
function LangGuard({ children }: { children: ReactNode }) {
  const { lang } = useParams();
  const location = useLocation();
  if (!isLang(lang)) return <Navigate to={`/ru${location.pathname}${location.search}`} replace />;
  return <>{children}</>;
}

const dev = (key: string) => page(<InDevelopment titleKey={`nav.${key}`} />);

export const router = createBrowserRouter([
  { path: "/", element: <RootRedirect /> },
  {
    path: "/:lang",
    element: (
      <LangGuard>
        <Layout />
      </LangGuard>
    ),
    children: [
      { index: true, element: page(<HomePage />) },
      { path: "catalog", element: page(<CatalogPage />) },
      { path: "catalog/funds", element: page(<FundsPage />) },
      { path: "catalog/funds/:id", element: page(<HierarchyPage level="fund" />) },
      { path: "catalog/inventories/:id", element: page(<HierarchyPage level="inventory" />) },
      { path: "catalog/cases/:id", element: page(<HierarchyPage level="case" />) },
      { path: "catalog/documents/:id", element: page(<DocumentPage />) },
      // Разделы следующих этапов — явно помечены как «раздел наполняется»
      { path: "about/*", element: dev("about") },
      { path: "visitors/*", element: dev("visitors") },
      { path: "services/*", element: dev("services") },
      { path: "history/*", element: dev("history") },
      { path: "exhibitions/*", element: dev("exhibitions") },
      { path: "news/*", element: dev("news") },
      { path: "branches/*", element: dev("branches") },
      { path: "faq", element: dev("faq") },
      { path: "assistant", element: dev("assistant") },
      { path: "*", element: <NotFound /> },
    ],
  },
], {
  future: { v7_relativeSplatPath: true, v7_fetcherPersist: true, v7_normalizeFormMethod: true, v7_partialHydration: true, v7_skipActionErrorRevalidation: true },
});
