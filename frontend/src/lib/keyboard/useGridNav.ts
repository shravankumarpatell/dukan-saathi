"use client";

import { useCallback, useRef, useState } from "react";

export interface GridNavOptions {
  rowCount: number;
  colCount: number;
  /** Called when Enter is pressed on the last row (or Ctrl+Enter anywhere) - typically appends a row. Return true if a row was added. */
  onAppendRow?: () => boolean | void;
  /** Called when a row should be deleted (Ctrl+Backspace / Ctrl+Delete). */
  onDeleteRow?: (row: number) => void;
  /** Enter commits & moves down (default) or right. */
  enterMoves?: "down" | "right";
  /** Columns that are not editable and should be skipped when moving horizontally. */
  skipCols?: number[];
}

/**
 * Shared roving-focus grid navigation for any tabular editor (invoice lines, voucher lines, batch pickers).
 * Cells must render `{...grid.cellProps(row, col)}`; the container gets `{...grid.containerProps}`.
 * Arrow keys move, Enter commits and moves to next row (adding one at the end), Tab/Shift+Tab move fields,
 * Ctrl+Arrow jumps to edges, Esc blurs the cell.
 */
export function useGridNav(opts: GridNavOptions) {
  const { rowCount, colCount, onAppendRow, onDeleteRow, enterMoves = "down", skipCols = [] } = opts;
  const [focused, setFocused] = useState<{ r: number; c: number } | null>(null);
  const containerRef = useRef<HTMLElement | null>(null);

  const focusCell = useCallback((r: number, c: number) => {
    const root = containerRef.current;
    if (!root) return;
    const cell = root.querySelector<HTMLElement>(`[data-cell="${r}-${c}"]`);
    if (!cell) return;
    const target = cell.querySelector<HTMLElement>("input,select,textarea,button,[tabindex]") ?? cell;
    target.focus();
    if (target instanceof HTMLInputElement && target.type !== "checkbox") target.select?.();
    setFocused({ r, c });
  }, []);

  const nextCol = useCallback(
    (c: number, dir: 1 | -1) => {
      let nc = c + dir;
      while (nc >= 0 && nc < colCount && skipCols.includes(nc)) nc += dir;
      return nc;
    },
    [colCount, skipCols],
  );

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent, r: number, c: number) => {
      const el = e.target as HTMLElement;
      const isInput = el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement;
      const comboOpen = el.getAttribute("aria-expanded") === "true";
      if (comboOpen && ["ArrowDown", "ArrowUp", "Enter", "Escape"].includes(e.key)) return; // let combobox handle
      const mod = e.ctrlKey || e.metaKey;
      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          focusCell(mod ? rowCount - 1 : Math.min(rowCount - 1, r + 1), c);
          break;
        case "ArrowUp":
          e.preventDefault();
          focusCell(mod ? 0 : Math.max(0, r - 1), c);
          break;
        case "ArrowLeft": {
          if (isInput && !mod) {
            const inp = el as HTMLInputElement;
            if (inp.selectionStart !== 0 || inp.selectionEnd !== 0) return;
          }
          e.preventDefault();
          const nc = mod ? 0 : nextCol(c, -1);
          if (nc >= 0) focusCell(r, nc);
          break;
        }
        case "ArrowRight": {
          if (isInput && !mod) {
            const inp = el as HTMLInputElement;
            const len = inp.value?.length ?? 0;
            if (inp.selectionStart !== len || inp.selectionEnd !== len) return;
          }
          e.preventDefault();
          const nc = mod ? colCount - 1 : nextCol(c, 1);
          if (nc < colCount) focusCell(r, nc);
          break;
        }
        case "Enter": {
          if (el.tagName === "BUTTON") return;
          e.preventDefault();
          if (e.shiftKey) {
            focusCell(Math.max(0, r - 1), c);
            return;
          }
          if (enterMoves === "right") {
            const nc = nextCol(c, 1);
            if (nc < colCount) {
              focusCell(r, nc);
              return;
            }
          }
          if (r >= rowCount - 1 || mod) {
            const added = onAppendRow?.();
            if (added !== false) {
              // wait for the row to render
              requestAnimationFrame(() => requestAnimationFrame(() => focusCell(r + 1, enterMoves === "right" ? firstCol(skipCols, colCount) : c)));
            }
            return;
          }
          focusCell(r + 1, enterMoves === "right" ? firstCol(skipCols, colCount) : c);
          break;
        }
        case "Backspace":
        case "Delete":
          if (mod && onDeleteRow) {
            e.preventDefault();
            onDeleteRow(r);
            requestAnimationFrame(() => focusCell(Math.max(0, Math.min(r, rowCount - 2)), c));
          }
          break;
        case "Escape":
          if (!comboOpen) (el as HTMLElement).blur?.();
          break;
        default:
          break;
      }
    },
    [colCount, rowCount, focusCell, nextCol, onAppendRow, onDeleteRow, enterMoves, skipCols],
  );

  const cellProps = useCallback(
    (r: number, c: number) => ({
      "data-cell": `${r}-${c}`,
      "data-focused": focused?.r === r && focused?.c === c ? "true" : undefined,
      className: "grid-cell",
      onKeyDown: (e: React.KeyboardEvent) => onKeyDown(e, r, c),
      onFocus: () => setFocused({ r, c }),
    }),
    [focused, onKeyDown],
  );

  const rowProps = useCallback(
    (r: number) => ({ "data-row": r, "data-active": focused?.r === r ? "true" : undefined, className: "grid-row" }),
    [focused],
  );

  return { containerRef, focused, focusCell, cellProps, rowProps };
}

function firstCol(skip: number[], count: number): number {
  let c = 0;
  while (c < count && skip.includes(c)) c++;
  return c;
}
