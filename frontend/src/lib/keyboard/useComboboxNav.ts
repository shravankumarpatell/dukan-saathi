"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export interface ComboOption<T> {
  value: string;
  label: string;
  hint?: string;
  meta?: string;
  item: T;
}

export interface UseComboboxNavArgs<T> {
  options: ComboOption<T>[];
  onSelect: (opt: ComboOption<T>) => void;
  onCreate?: (query: string) => void;
  value?: string | null;
  query: string;
  setQuery: (q: string) => void;
  open: boolean;
  setOpen: (o: boolean) => void;
  minChars?: number;
}

/**
 * Shared keyboard behaviour for every type-ahead picker (customers, products, ledgers, godowns, batches).
 * Opens on first keystroke, arrow keys move the highlight, Enter/Tab selects, Esc closes and restores the label.
 * State (query/open) is controlled by the caller so async option loading can key off the query.
 */
export function useComboboxNav<T>({ options, onSelect, onCreate, value, query, setQuery, open, setOpen, minChars = 0 }: UseComboboxNavArgs<T>) {
  const [highlight, setHighlight] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const listRef = useRef<HTMLUListElement | null>(null);

  const selected = useMemo(() => options.find((o) => o.value === value) ?? null, [options, value]);

  useEffect(() => {
    setHighlight(0);
  }, [query, options.length]);

  useEffect(() => {
    if (!open || !listRef.current) return;
    const el = listRef.current.querySelector<HTMLElement>(`[data-index="${highlight}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }, [highlight, open]);

  const choose = useCallback(
    (opt: ComboOption<T>) => {
      onSelect(opt);
      setOpen(false);
      setQuery("");
    },
    [onSelect, setOpen, setQuery],
  );

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      const canCreate = !!onCreate && query.trim().length > 0;
      const total = options.length + (canCreate ? 1 : 0);
      if (!open && ["ArrowDown", "ArrowUp"].includes(e.key)) {
        e.preventDefault();
        setOpen(true);
        return;
      }
      if (!open) return;
      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          e.stopPropagation();
          setHighlight((h) => (total ? (h + 1) % total : 0));
          break;
        case "ArrowUp":
          e.preventDefault();
          e.stopPropagation();
          setHighlight((h) => (total ? (h - 1 + total) % total : 0));
          break;
        case "Enter":
        case "Tab": {
          if (!total) {
            if (e.key === "Enter") {
              e.preventDefault();
              e.stopPropagation();
            }
            setOpen(false);
            setQuery("");
            return;
          }
          const opt = options[highlight];
          if (opt) {
            e.preventDefault();
            e.stopPropagation();
            choose(opt);
          } else if (canCreate && highlight === options.length) {
            e.preventDefault();
            e.stopPropagation();
            onCreate?.(query.trim());
            setOpen(false);
            setQuery("");
          }
          break;
        }
        case "Escape":
          e.preventDefault();
          e.stopPropagation();
          setOpen(false);
          setQuery("");
          break;
        default:
          break;
      }
    },
    [open, options, highlight, choose, onCreate, query, setOpen, setQuery],
  );

  const onChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setQuery(e.target.value);
      if (e.target.value.length >= minChars) setOpen(true);
    },
    [minChars, setOpen, setQuery],
  );

  return { highlight, setHighlight, inputRef, listRef, selected, choose, onKeyDown, onChange };
}
