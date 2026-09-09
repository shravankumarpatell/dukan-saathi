"use client";

import { Input } from "@/components/ui/input";
import { Field } from "./page";

export function DateRange({ from, to, onChange, className }: { from: string; to: string; onChange: (from: string, to: string) => void; className?: string }) {
  return (
    <div className={`flex flex-wrap items-end gap-2 ${className ?? ""}`}>
      <Field label="From" htmlFor="from-date">
        <Input id="from-date" type="date" value={from} onChange={(e) => onChange(e.target.value, to)} className="h-9 w-40" data-testid="filter-from-date" />
      </Field>
      <Field label="To" htmlFor="to-date">
        <Input id="to-date" type="date" value={to} onChange={(e) => onChange(from, e.target.value)} className="h-9 w-40" data-testid="filter-to-date" />
      </Field>
    </div>
  );
}
