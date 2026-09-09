import { format, parseISO } from "date-fns";

const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const inrCompact = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const num = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });

export function money(v: string | number | null | undefined, opts?: { compact?: boolean }): string {
  if (v === null || v === undefined || v === "") return "-";
  const n = typeof v === "string" ? parseFloat(v) : v;
  if (Number.isNaN(n)) return "-";
  return opts?.compact ? inrCompact.format(n) : inr.format(n);
}

export function amount(v: string | number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || v === "") return "-";
  const n = typeof v === "string" ? parseFloat(v) : v;
  if (Number.isNaN(n)) return "-";
  return new Intl.NumberFormat("en-IN", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(n);
}

export function qty(v: string | number | null | undefined): string {
  if (v === null || v === undefined || v === "") return "-";
  const n = typeof v === "string" ? parseFloat(v) : v;
  if (Number.isNaN(n)) return "-";
  return num.format(n);
}

export function dateFmt(v: string | null | undefined, f = "dd MMM yyyy"): string {
  if (!v) return "-";
  try {
    return format(parseISO(v), f);
  } catch {
    return v;
  }
}

export function todayISO(): string {
  return format(new Date(), "yyyy-MM-dd");
}

export function fyStartISO(): string {
  const d = new Date();
  const y = d.getMonth() >= 3 ? d.getFullYear() : d.getFullYear() - 1;
  return `${y}-04-01`;
}

export function monthStartISO(): string {
  return format(new Date(), "yyyy-MM-01");
}

export function n(v: string | number | null | undefined): number {
  if (v === null || v === undefined || v === "") return 0;
  const x = typeof v === "string" ? parseFloat(v) : v;
  return Number.isNaN(x) ? 0 : x;
}

export function titleCase(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function uid(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : Math.random().toString(36).slice(2);
}
