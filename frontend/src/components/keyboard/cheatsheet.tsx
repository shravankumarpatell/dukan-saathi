"use client";

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { GLOBAL_SHORTCUTS, GRID_SHORTCUTS, NAV } from "@/lib/nav";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Shortcut } from "./shortcut";
import { Input } from "@/components/ui/input";
import { useMemo, useState } from "react";

export function ShortcutCheatsheet({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const [q, setQ] = useState("");
  const nav = useMemo(() => NAV.flatMap((g) => g.items.filter((i) => i.chord).map((i) => ({ keys: i.chord!, label: `Go to ${i.label}` }))), []);
  const sections = [
    { title: "Global", rows: GLOBAL_SHORTCUTS },
    { title: "Navigation chords", rows: nav },
    { title: "Line-item grids", rows: GRID_SHORTCUTS },
  ];
  const filter = (rows: { keys: string; label: string }[]) => rows.filter((r) => !q || `${r.keys} ${r.label}`.toLowerCase().includes(q.toLowerCase()));
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl p-0" data-testid="shortcut-cheatsheet-dialog">
        <DialogHeader className="border-b px-6 pt-6 pb-4">
          <DialogTitle>Keyboard shortcuts</DialogTitle>
          <DialogDescription>Every action in TileOS is reachable without a mouse. Press ? anywhere to open this list.</DialogDescription>
          <Input autoFocus placeholder="Filter shortcuts..." value={q} onChange={(e) => setQ(e.target.value)} className="mt-3" data-testid="cheatsheet-filter-input" />
        </DialogHeader>
        <ScrollArea className="max-h-[60vh]">
          <div className="grid gap-6 p-6 sm:grid-cols-2">
            {sections.map((s) => {
              const rows = filter(s.rows);
              if (!rows.length) return null;
              return (
                <div key={s.title} className={s.title === "Navigation chords" ? "sm:row-span-2" : ""}>
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{s.title}</h3>
                  <ul className="space-y-1.5">
                    {rows.map((r) => (
                      <li key={r.keys + r.label} className="flex items-center justify-between gap-4 text-sm">
                        <span>{r.label}</span>
                        <Shortcut keys={r.keys} />
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}
