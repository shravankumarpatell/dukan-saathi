"use client";

import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";

const BASE = (process.env.NEXT_PUBLIC_BACKEND_URL || "").replace(/\/$/, "");

export const TOKEN_KEY = "tileos.access";
export const REFRESH_KEY = "tileos.refresh";
export const COMPANY_KEY = "tileos.company";
export const BRANCH_KEY = "tileos.branch";

export const storage = {
  get(k: string) {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(k);
  },
  set(k: string, v: string | null) {
    if (typeof window === "undefined") return;
    if (v === null) window.localStorage.removeItem(k);
    else window.localStorage.setItem(k, v);
  },
};

export const api = axios.create({ baseURL: `${BASE}/api`, timeout: 30_000 });

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = storage.get(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  const company = storage.get(COMPANY_KEY);
  if (company) config.headers["X-Company-Id"] = company;
  const branch = storage.get(BRANCH_KEY);
  if (branch) config.headers["X-Branch-Id"] = branch;
  return config;
});

let refreshing: Promise<string | null> | null = null;

async function refreshToken(): Promise<string | null> {
  const rt = storage.get(REFRESH_KEY);
  if (!rt) return null;
  try {
    const res = await axios.post(`${BASE}/api/auth/refresh`, { refresh_token: rt });
    storage.set(TOKEN_KEY, res.data.access_token);
    storage.set(REFRESH_KEY, res.data.refresh_token);
    return res.data.access_token as string;
  } catch {
    storage.set(TOKEN_KEY, null);
    storage.set(REFRESH_KEY, null);
    return null;
  }
}

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;
    if (error.response?.status === 401 && original && !original._retry && !original.url?.includes("/auth/login")) {
      original._retry = true;
      refreshing = refreshing ?? refreshToken();
      const token = await refreshing;
      refreshing = null;
      if (token) {
        original.headers.Authorization = `Bearer ${token}`;
        return api(original);
      }
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  },
);

export function errorMessage(e: unknown): string {
  if (axios.isAxiosError(e)) {
    const d = e.response?.data as { detail?: unknown } | undefined;
    if (d?.detail) return typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail);
    if (e.code === "ECONNABORTED") return "Request timed out";
    if (!e.response) return "Cannot reach the server";
    return `${e.response.status} ${e.response.statusText}`;
  }
  if (e instanceof Error) return e.message;
  return "Something went wrong";
}

export async function get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const res = await api.get<T>(url, { params });
  return res.data;
}
export async function post<T>(url: string, body?: unknown, params?: Record<string, unknown>): Promise<T> {
  const res = await api.post<T>(url, body, { params });
  return res.data;
}
export async function put<T>(url: string, body?: unknown): Promise<T> {
  const res = await api.put<T>(url, body);
  return res.data;
}
export async function del<T>(url: string): Promise<T> {
  const res = await api.delete<T>(url);
  return res.data;
}
