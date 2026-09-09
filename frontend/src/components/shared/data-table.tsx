"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { useHotkeys } from "@/lib/keyboard/useHotkeys";
import { EmptyState, TableSkeleton } from "./page";

export interface Column<T> {
  key: string;
  header: React.ReactNode;
  cell: (row: T, index: number) => React.ReactNode;
  className?: string;
  align?: "left" | "right" | "center";
  width?: string;
}

export interface DataTableProps<T> {
  rows: T[] | undefined;
  columns: Column<T>[];
  rowKey: (row: T) => string;
  loading?: boolean;
  onOpen?: (row: T) => void;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: React.ReactNode;
  footer?: React.ReactNode;
  compact?: boolean;
  className?: string;
  maxHeight?: string;
  testId?: string;
  /** enable j/k/Enter keyboard row navigation (default true) */
  keyboard?: boolean;
}

/**
 * Dense data table with sticky header and keyboard row navigation (j/k or arrows, Enter to open).
 */
export function DataTable<T>({ rows, columns, rowKey, loading, onOpen, emptyTitle = "Nothing here yet", emptyDescription, emptyAction, footer, compact, className, maxHeight, testId, keyboard = true }: DataTableProps<T>) {
  const [active, setActive] = useState<number>(-1);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setActive(-1);
  }, [rows]);

  const move = useCallback(
    (d: number) => {
      if (!rows?.length) return;
      setActive((a) => {
        const next = Math.max(0, Math.min(rows.length - 1, (a < 0 ? (d > 0 ? -1 : rows.length) : a) + d));
        const el = ref.current?.querySelector<HTMLElement>(`[data-row-index="${next}"]`);
        el?.scrollIntoView({ block: "nearest" });
        el?.focus({ preventScroll: true });
        return next;
      });
    },
    [rows],
  );

  useHotkeys([
    { keys: "j", handler: () => move(1), enabled: keyboard },
    { keys: "k", handler: () => move(-1), enabled: keyboard },
  ]);

  if (loading && !rows) return <TableSkeleton cols={columns.length} />;
  if (!rows?.length) return <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} />;

  return (
    <div ref={ref} className={cn("overflow-auto rounded-lg border", className)} style={maxHeight ? { maxHeight } : undefined} data-testid={testId}>
      <Table className="table-sticky">
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            {columns.map((c) => (
              <TableHead key={c.key} className={cn("h-9 text-xs font-semibold uppercase tracking-wide text-muted-foreground", c.align === "right" && "text-right", c.align === "center" && "text-center", c.className)} style={c.width ? { width: c.width } : undefined}>
                {c.header}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r, i) => (
            <TableRow
              key={rowKey(r)}
              data-row-index={i}
              data-testid={`table-row-${i}`}
              tabIndex={onOpen ? 0 : -1}
              aria-selected={active === i}
              onFocus={() => setActive(i)}
              onClick={() => onOpen?.(r)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && onOpen) {
                  e.preventDefault();
                  onOpen(r);
                } else if (e.key === "ArrowDown") {
                  e.preventDefault();
                  move(1);
                } else if (e.key === "ArrowUp") {
                  e.preventDefault();
                  move(-1);
                }
              }}
              className={cn("transition-colors duration-150 focus:outline-none", onOpen && "cursor-pointer", active === i ? "bg-row-selected" : "hover:bg-row-hover", compact ? "h-[var(--row-h-compact)]" : "h-[var(--row-h)]")}
            >
              {columns.map((c) => (
                <TableCell key={c.key} className={cn("py-1.5", c.align === "right" && "text-right font-mono tabular", c.align === "center" && "text-center", c.className)}>
                  {c.cell(r, i)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
        {footer}
      </Table>
    </div>
  );
}
