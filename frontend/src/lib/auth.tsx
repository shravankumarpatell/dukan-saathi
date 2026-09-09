"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { BRANCH_KEY, COMPANY_KEY, REFRESH_KEY, TOKEN_KEY, api, get, post, storage } from "./api";
import type { MeOut, TokenOut } from "./types";

interface AuthCtx {
  ready: boolean;
  authenticated: boolean;
  me: MeOut | undefined;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  switchCompany: (companyId: string, branchId?: string | null) => Promise<void>;
  can: (perm: string) => boolean;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const qc = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    setAuthenticated(!!storage.get(TOKEN_KEY));
    setReady(true);
  }, []);

  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: () => get<MeOut>("/auth/me"),
    enabled: ready && authenticated,
    staleTime: 5 * 60_000,
  });

  useEffect(() => {
    if (meQuery.data) {
      if (!storage.get(COMPANY_KEY) && meQuery.data.current_company_id) storage.set(COMPANY_KEY, meQuery.data.current_company_id);
      if (!storage.get(BRANCH_KEY) && meQuery.data.current_branch_id) storage.set(BRANCH_KEY, meQuery.data.current_branch_id);
    }
  }, [meQuery.data]);

  useEffect(() => {
    if (!ready) return;
    const isPublic = pathname === "/login";
    if (!authenticated && !isPublic) router.replace("/login");
    if (authenticated && isPublic) router.replace("/dashboard");
  }, [ready, authenticated, pathname, router]);

  const login = useCallback(
    async (email: string, password: string) => {
      const t = await post<TokenOut>("/auth/login", { email, password, device_id: deviceId() });
      storage.set(TOKEN_KEY, t.access_token);
      storage.set(REFRESH_KEY, t.refresh_token);
      storage.set(COMPANY_KEY, null);
      storage.set(BRANCH_KEY, null);
      setAuthenticated(true);
      await qc.invalidateQueries();
      router.replace("/dashboard");
    },
    [qc, router],
  );

  const logout = useCallback(async () => {
    const rt = storage.get(REFRESH_KEY);
    try {
      if (rt) await api.post("/auth/logout", { refresh_token: rt });
    } catch {
      /* ignore */
    }
    storage.set(TOKEN_KEY, null);
    storage.set(REFRESH_KEY, null);
    storage.set(COMPANY_KEY, null);
    storage.set(BRANCH_KEY, null);
    setAuthenticated(false);
    qc.clear();
    router.replace("/login");
  }, [qc, router]);

  const switchCompany = useCallback(
    async (companyId: string, branchId?: string | null) => {
      const t = await post<TokenOut>("/auth/switch", undefined, { company_id: companyId, branch_id: branchId ?? undefined });
      storage.set(TOKEN_KEY, t.access_token);
      storage.set(REFRESH_KEY, t.refresh_token);
      storage.set(COMPANY_KEY, companyId);
      storage.set(BRANCH_KEY, branchId ?? null);
      await qc.invalidateQueries();
      await qc.refetchQueries({ queryKey: ["me"] });
    },
    [qc],
  );

  const can = useCallback(
    (perm: string) => {
      const perms = meQuery.data?.permissions ?? [];
      if (perms.includes("*") || perms.includes(perm)) return true;
      const mod = perm.split(".")[0];
      return perms.includes(`${mod}.*`);
    },
    [meQuery.data],
  );

  const value = useMemo<AuthCtx>(
    () => ({ ready, authenticated, me: meQuery.data, loading: meQuery.isLoading, login, logout, switchCompany, can }),
    [ready, authenticated, meQuery.data, meQuery.isLoading, login, logout, switchCompany, can],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth outside AuthProvider");
  return c;
}

function deviceId(): string {
  const k = "tileos.device";
  let v = storage.get(k);
  if (!v) {
    v = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : Math.random().toString(36).slice(2);
    storage.set(k, v);
  }
  return v;
}
