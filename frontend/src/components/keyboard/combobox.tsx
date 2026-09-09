"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronsUpDown, Plus } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { type ComboOption, useComboboxNav } from "@/lib/keyboard/useComboboxNav";
import { cn } from "@/lib/utils";

export type { ComboOption };

export interface ComboboxProps<T> {
  value: string | null | undefined;
  onChange: (value: string | null, item: T | null) => void;
  /** Static options OR a fetcher for async search. */
  options?: ComboOption<T>[];
  fetchOptions?: (q: string) => Promise<ComboOption<T>[]>;
  queryKey?: readonly unknown[];
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  inputClassName?: string;
  autoFocus?: boolean;
  onCreate?: (query: string) => void;
  createLabel?: string;
  /** Called after a selection is made (e.g. move focus to next field). */
  onSelected?: (item: T) => void;
  "data-testid"?: string;
  compact?: boolean;
  emptyText?: string;
  /** Label to show when the selected value is not in `options` (async mode). */
  displayValue?: string;
  id?: string;
}

/**
 * Keyboard-native type-ahead picker built on useComboboxNav. Opens on first keystroke; never requires a mouse.
 */
export function Combobox<T>(props: ComboboxProps<T>) {
  const { value, onChange, options, fetchOptions, queryKey, placeholder, disabled, className, inputClassName, autoFocus, onCreate, createLabel, onSelected, compact, emptyText, displayValue } = props;
  const autoId = useId();
  const id = props.id ?? autoId;
  const wrapRef = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);

  const asyncQ = useQuery({
    queryKey: [...(queryKey ?? ["combo", id]), query],
    queryFn: () => fetchOptions!(query),
    enabled: !!fetchOptions && open,
    staleTime: 10_000,
    placeholderData: (prev) => prev,
  });

  const filtered = useMemo<ComboOption<T>[]>(() => {
    if (fetchOptions) return asyncQ.data ?? [];
    const q = query.trim().toLowerCase();
    const list = options ?? [];
    if (!q) return list.slice(0, 200);
    return list.filter((o) => `${o.label} ${o.hint ?? ""} ${o.meta ?? ""}`.toLowerCase().includes(q)).slice(0, 200);
  }, [fetchOptions, asyncQ.data, options, query]);

  const nav = useComboboxNav<T>({
    options: filtered,
    value,
    query,
    setQuery,
    open,
    setOpen,
    onSelect: (opt) => {
      onChange(opt.value, opt.item);
      onSelected?.(opt.item);
    },
    onCreate,
  });

  const staticLabel = useMemo(() => (options ?? []).find((o) => o.value === value)?.label, [options, value]);
  const selectedLabel = displayValue ?? staticLabel ?? nav.selected?.label ?? "";

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const listId = `${id}-list`;
  const showCreate = !!onCreate && query.trim().length > 0;

  return (
    <div ref={wrapRef} className={cn("relative", className)}>
      <div className="relative">
        <input
          id={id}
          ref={nav.inputRef}
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          autoComplete="off"
          data-testid={props["data-testid"]}
          disabled={disabled}
          autoFocus={autoFocus}
          placeholder={placeholder}
          value={open ? query : selectedLabel}
          onChange={nav.onChange}
          onKeyDown={nav.onKeyDown}
          onFocus={(e) => e.target.select()}
          onClick={() => !disabled && setOpen(true)}
          className={cn(
            "w-full rounded-md border border-input bg-background pr-8 text-sm outline-none transition-colors duration-150 placeholder:text-muted-foreground focus-visible:border-ring disabled:opacity-60",
            compact ? "h-8 px-2" : "h-9 px-3",
            inputClassName,
          )}
        />
        <ChevronsUpDown className="pointer-events-none absolute right-2 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden />
      </div>
      {open && (
        <ul
          id={listId}
          ref={nav.listRef}
          role="listbox"
          data-testid={props["data-testid"] ? `${props["data-testid"]}-list` : undefined}
          className="absolute left-0 z-[100] mt-1 max-h-72 w-full min-w-[300px] overflow-auto rounded-lg border bg-popover p-1 text-popover-foreground shadow-2xl shadow-black/10 dark:shadow-black/40"
        >
          {asyncQ.isLoading && <li className="px-3 py-2 text-xs text-muted-foreground">Searching...</li>}
          {!asyncQ.isLoading && filtered.length === 0 && !showCreate && <li className="px-3 py-2 text-xs text-muted-foreground">{emptyText ?? "No matches"}</li>}
          {filtered.map((o, i) => (
            <li
              key={o.value}
              role="option"
              aria-selected={i === nav.highlight}
              data-index={i}
              data-testid={props["data-testid"] ? `${props["data-testid"]}-option-${i}` : undefined}
              onMouseDown={(e) => {
                e.preventDefault();
                nav.choose(o);
              }}
              onMouseEnter={() => nav.setHighlight(i)}
              className={cn("flex cursor-default items-center justify-between gap-3 rounded-md px-3 py-2 text-sm", i === nav.highlight ? "bg-accent text-accent-foreground" : "")}
            >
              <span className="flex min-w-0 flex-col">
                <span className="truncate font-medium">{o.label}</span>
                {o.hint && <span className="truncate text-xs text-muted-foreground">{o.hint}</span>}
              </span>
              {o.meta && <span className="shrink-0 font-mono text-xs tabular text-muted-foreground">{o.meta}</span>}
            </li>
          ))}
          {showCreate && (
            <li
              role="option"
              aria-selected={nav.highlight === filtered.length}
              data-index={filtered.length}
              onMouseDown={(e) => {
                e.preventDefault();
                onCreate?.(query.trim());
                setOpen(false);
                setQuery("");
              }}
              className={cn("flex items-center gap-2 rounded-md px-3 py-2 text-sm", nav.highlight === filtered.length ? "bg-accent text-accent-foreground" : "text-primary")}
            >
              <Plus className="size-4" /> {createLabel ?? "Create"} &ldquo;{query.trim()}&rdquo;
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
