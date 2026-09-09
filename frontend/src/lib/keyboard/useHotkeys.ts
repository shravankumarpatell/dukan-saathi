"use client";

import { useEffect, useRef } from "react";

/** True when the event target is a text-editing element (so single-key shortcuts must not fire). */
export function isEditable(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el) return false;
  const tag = el.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  if (el.isContentEditable) return true;
  if (el.closest?.("[role=dialog]") && (el.closest("[cmdk-root]") || el.closest("[data-slot=command]"))) return true;
  return false;
}

export type HotkeyHandler = (e: KeyboardEvent) => void;

export interface HotkeySpec {
  /** e.g. "mod+k", "?", "g s" (chord), "escape", "mod+enter", "alt+n" */
  keys: string;
  handler: HotkeyHandler;
  /** allow firing while typing in inputs (default false for plain keys, true for mod combos) */
  inInputs?: boolean;
  enabled?: boolean;
}

function normalizeKey(e: KeyboardEvent): string {
  const k = e.key.toLowerCase();
  if (k === " ") return "space";
  return k;
}

function matchCombo(spec: string, e: KeyboardEvent): boolean {
  const parts = spec.toLowerCase().split("+");
  const key = parts[parts.length - 1];
  const wantMod = parts.includes("mod");
  const wantShift = parts.includes("shift");
  const wantAlt = parts.includes("alt");
  const hasMod = e.metaKey || e.ctrlKey;
  if (wantMod !== hasMod) return false;
  if (wantAlt !== e.altKey) return false;
  if (key !== "?" && wantShift !== e.shiftKey) return false;
  const nk = normalizeKey(e);
  if (key === "?") return e.key === "?";
  return nk === key || (key === "esc" && nk === "escape");
}

/**
 * Global hotkeys with two-key chord support ("g s").
 * Plain keys / chords never fire while typing in inputs.
 */
export function useHotkeys(specs: HotkeySpec[]) {
  const ref = useRef(specs);
  ref.current = specs;
  const pending = useRef<{ key: string; at: number } | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const editing = isEditable(e.target);
      const now = Date.now();
      const nk = normalizeKey(e);
      const hasMod = e.metaKey || e.ctrlKey || e.altKey;

      // chords
      if (!editing && !hasMod) {
        if (pending.current && now - pending.current.at < 1200) {
          const chord = `${pending.current.key} ${nk}`;
          pending.current = null;
          const s = ref.current.find((x) => x.enabled !== false && x.keys.toLowerCase() === chord);
          if (s) {
            e.preventDefault();
            s.handler(e);
            return;
          }
        }
        const starts = ref.current.some((x) => x.enabled !== false && x.keys.toLowerCase().startsWith(`${nk} `));
        if (starts) {
          pending.current = { key: nk, at: now };
          e.preventDefault();
          return;
        }
      }
      for (const s of ref.current) {
        if (s.enabled === false || s.keys.includes(" ")) continue;
        const modCombo = s.keys.includes("+");
        const allowed = s.inInputs ?? modCombo;
        if (editing && !allowed) continue;
        if (matchCombo(s.keys, e)) {
          e.preventDefault();
          s.handler(e);
          return;
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}

export const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
export const MOD = isMac ? "\u2318" : "Ctrl";
