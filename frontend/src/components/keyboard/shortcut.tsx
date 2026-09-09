"use client";

import { Kbd, KbdGroup } from "@/components/ui/kbd";
import { MOD } from "@/lib/keyboard/useHotkeys";

export function Shortcut({ keys, className }: { keys: string; className?: string }) {
  const parts = keys.split(" ").filter(Boolean);
  return (
    <KbdGroup className={className}>
      {parts.map((p, i) => (
        <span key={i} className="inline-flex items-center gap-1">
          {i > 0 && <span className="text-[10px] text-muted-foreground">then</span>}
          {p.split("+").map((k, j) => (
            <Kbd key={j} className="font-mono text-[11px]">
              {k === "mod" ? MOD : k === "shift" ? "⇧" : k === "alt" ? "Alt" : k === "enter" ? "↵" : k === "esc" ? "Esc" : k === "backspace" ? "⌫" : k.length === 1 ? k.toUpperCase() : k}
            </Kbd>
          ))}
        </span>
      ))}
    </KbdGroup>
  );
}
