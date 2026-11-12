import type React from "react";
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

const InfoPage = lazy(() => import("../pages/info/InfoPages").then((m) => ({ default: m.InfoPage })));
const SectionHub = lazy(() => import("../pages/info/InfoPages").then((m) => ({ default: m.SectionHub })));
const MemorialDatesPage = lazy(() =>
  import("../pages/info/InfoPages").then((m) => ({ default: m.MemorialDatesPage })),
);
const NewsListPage = lazy(() => import("../pages/NewsPages").then((m) => ({ default: m.NewsListPage })));
const NewsDetailPage = lazy(() => import("../pages/NewsPages").then((m) => ({ default: m.NewsDetailPage })));
const AssistantPage = lazy(() => import("../features/assistant/Assistant").then((m) => ({ default: m.AssistantPage })));
const FaqPage = lazy(() => import("../pages/FaqPage").then((m) => ({ default: m.FaqPage })));

// Админ-панель — отдельный чанк, на публичных страницах не загружается
const adminLazy = <K extends string>(loader: () => Promise<Record<K, React.ComponentType>>, name: K) =>
  lazy(() => loader().then((m) => ({ default: m[name] })));
const RequireAuth = lazy(() => import("../admin/auth").then((m) => ({ default: m.RequireAuth })));
const AdminLayout = adminLazy(() => import("../admin/ui"), "AdminLayout");
const LoginPage = adminLazy(() => import("../admin/pages/LoginDashboard"), "LoginPage");
const Dashboard = adminLazy(() => import("../admin/pages/LoginDashboard"), "Dashboard");
const NewsList = adminLazy(() => import("../admin/pages/ContentPages"), "NewsList");
const NewsEdit = adminLazy(() => import("../admin/pages/ContentPages"), "NewsEdit");
const PagesList = adminLazy(() => import("../admin/pages/ContentPages"), "PagesList");
const PageEdit = adminLazy(() => import("../admin/pages/ContentPages"), "PageEdit");
const FaqAdminPage = adminLazy(() => import("../admin/pages/ContentPages"), "FaqAdminPage");
const FeedbackAdmin = adminLazy(() => import("../admin/pages/ContentPages"), "FeedbackAdmin");
const CatalogList = adminLazy(() => import("../admin/pages/CatalogAdmin"), "CatalogList");
const DocumentEdit = adminLazy(() => import("../admin/pages/CatalogAdmin"), "DocumentEdit");
const BranchesAdmin = adminLazy(() => import("../admin/pages/SystemAdmin"), "BranchesAdmin");
const BranchEdit = adminLazy(() => import("../admin/pages/SystemAdmin"), "BranchEdit");
const AuditAdmin = adminLazy(() => import("../admin/pages/SystemAdmin"), "AuditAdmin");
const UsersAdmin = adminLazy(() => import("../admin/pages/SystemAdmin"), "UsersAdmin");

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
  { path: "/admin/login", element: page(<LoginPage />) },
  {
    path: "/admin",
    element: page(
      <RequireAuth>
        <AdminLayout />
      </RequireAuth>,
    ),
    children: [
      { index: true, element: page(<Dashboard />) },
      { path: "catalog", element: page(<CatalogList />) },
      { path: "catalog/:id", element: page(<DocumentEdit />) },
      { path: "news", element: page(<NewsList />) },
      { path: "news/:id", element: page(<NewsEdit />) },
      { path: "pages", element: page(<PagesList />) },
      { path: "pages/:id", element: page(<PageEdit />) },
      { path: "faq", element: page(<FaqAdminPage />) },
      { path: "feedback", element: page(<FeedbackAdmin />) },
      { path: "branches", element: page(<BranchesAdmin />) },
      { path: "branches/:id", element: page(<BranchEdit />) },
      { path: "audit", element: page(<AuditAdmin />) },
      { path: "users", element: page(<UsersAdmin />) },
      { path: "*", element: <NotFound /> },
    ],
  },
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
      { path: "about", element: page(<InfoPage key="about" section="about" />) },
      { path: "about/:sub", element: page(<InfoPage section="about" />) },
      { path: "services", element: page(<SectionHub key="services" section="services" />) },
      { path: "services/:sub", element: page(<InfoPage section="services" />) },
      { path: "visitors", element: page(<SectionHub key="visitors" section="visitors" />) },
      { path: "visitors/memorial-dates", element: page(<MemorialDatesPage />) },
      { path: "visitors/:sub", element: page(<InfoPage section="visitors" />) },
      { path: "history/*", element: dev("history") },
      { path: "exhibitions/*", element: dev("exhibitions") },
      { path: "news", element: page(<NewsListPage />) },
      { path: "news/:slug", element: page(<NewsDetailPage />) },
      { path: "branches/*", element: dev("branches") },
      { path: "faq", element: page(<FaqPage />) },
      { path: "assistant", element: page(<AssistantPage />) },
      { path: "*", element: <NotFound /> },
    ],
  },
], {
  future: { v7_relativeSplatPath: true, v7_fetcherPersist: true, v7_normalizeFormMethod: true, v7_partialHydration: true, v7_skipActionErrorRevalidation: true },
});
