import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useRef, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { Loading } from "../components/ui/States";
import { ApiError } from "../lib/api";
import { admin, type Me, SESSION_EXPIRED_EVENT } from "./api";

interface AuthValue {
  me: Me;
  can: (perm: string) => boolean;
  logout: (reason?: string) => Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

export function useAuth(): AuthValue {
  const v = useContext(AuthContext);
  if (!v) throw new Error("useAuth вне AuthProvider");
  return v;
}

const ACTIVITY_EVENTS = ["mousemove", "keydown", "click", "scroll", "touchstart"] as const;

/** Требует входа; следит за неактивностью (автовыход, ТЗ §7.3) — сервер независимо ограничивает срок cookie. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const qc = useQueryClient();
  const me = useQuery({
    queryKey: ["admin-me"],
    queryFn: () => admin.get<Me>("/auth/me"),
    retry: false,
    staleTime: 60_000,
  });
  const lastActivity = useRef(Date.now());
  const [warn, setWarn] = useState(false);

  const logout = useCallback(
    async (reason?: string) => {
      try {
        await admin.post("/auth/logout");
      } catch {
        /* сессия уже недействительна */
      }
      qc.clear();
      navigate("/admin/login", { replace: true, state: { reason, from: location.pathname } });
    },
    [qc, navigate, location.pathname],
  );

  useEffect(() => {
    const onExpired = () => {
      qc.removeQueries({ queryKey: ["admin-me"] });
      navigate("/admin/login", { replace: true, state: { reason: "Сессия завершена. Войдите снова.", from: location.pathname } });
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired);
  }, [navigate, qc, location.pathname]);

  const idleMs = (me.data?.idle_minutes ?? 30) * 60_000;
  useEffect(() => {
    if (!me.data) return;
    const bump = () => {
      lastActivity.current = Date.now();
      setWarn(false);
    };
    ACTIVITY_EVENTS.forEach((e) => window.addEventListener(e, bump, { passive: true }));
    const timer = window.setInterval(() => {
      const idle = Date.now() - lastActivity.current;
      if (idle >= idleMs) void logout("Автоматический выход после периода неактивности.");
      else setWarn(idle >= idleMs - 60_000);
    }, 5_000);
    return () => {
      ACTIVITY_EVENTS.forEach((e) => window.removeEventListener(e, bump));
      window.clearInterval(timer);
    };
  }, [me.data, idleMs, logout]);

  if (me.isLoading) return <Loading />;
  if (me.isError) {
    if (me.error instanceof ApiError && me.error.status === 401)
      return <Navigate to="/admin/login" replace state={{ from: location.pathname }} />;
    return <p className="p-8 text-danger">Админ-панель недоступна: {(me.error as Error).message}</p>;
  }
  const value: AuthValue = { me: me.data!, can: (p) => me.data!.permissions.includes(p), logout };
  return (
    <AuthContext.Provider value={value}>
      {warn && (
        <div role="alert" className="fixed inset-x-0 top-0 z-50 bg-warn px-4 py-2 text-center text-sm font-medium text-bg">
          Сессия завершится через минуту из-за неактивности. Пошевелите мышью или нажмите клавишу, чтобы продолжить.
        </div>
      )}
      {children}
    </AuthContext.Provider>
  );
}
