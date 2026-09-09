"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Building2, Package, Receipt, Users, Zap } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList, CommandSeparator } from "@/components/ui/command";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { get } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { money } from "@/lib/format";
import { ACTIONS, NAV } from "@/lib/nav";
import type { Paged, PartyOut, ProductOut, TradeDocListOut } from "@/lib/types";
import { Shortcut } from "./shortcut";

export function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const router = useRouter();
  const { can } = useAuth();
  const [q, setQ] = useState("");

  useEffect(() => {
    if (!open) setQ("");
  }, [open]);

  const live = q.trim().length >= 2;
  const parties = useQuery({ queryKey: ["palette", "parties", q], queryFn: () => get<PartyOut[]>("/parties", { q, limit: 6 }), enabled: open && live, staleTime: 10_000 });
  const products = useQuery({ queryKey: ["palette", "products", q], queryFn: () => get<ProductOut[]>("/inventory/products", { q, limit: 6 }), enabled: open && live, staleTime: 10_000 });
  const invoices = useQuery({ queryKey: ["palette", "invoices", q], queryFn: () => get<Paged<TradeDocListOut>>("/trade/sales_invoice", { q, page_size: 5 }), enabled: open && live, staleTime: 10_000 });

  const go = (href: string) => {
    onOpenChange(false);
    router.push(href);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[720px] max-w-[92vw] overflow-hidden p-0 shadow-2xl shadow-black/10 dark:shadow-black/40" showCloseButton={false} data-testid="command-palette">
        <DialogTitle className="sr-only">Command palette</DialogTitle>
        <Command shouldFilter={true} className="rounded-xl">
          <CommandInput placeholder="Type a command, page, customer, product or invoice number..." value={q} onValueChange={setQ} data-testid="command-palette-input" className="h-11 text-sm" />
          <CommandList className="max-h-[420px]">
            <CommandEmpty>No results. Try &ldquo;new sale&rdquo;, &ldquo;trial balance&rdquo; or a customer name.</CommandEmpty>
            <CommandGroup heading="Actions">
              {ACTIONS.filter((a) => !a.perm || can(a.perm)).map((a) => (
                <CommandItem key={a.href} value={`${a.label} ${(a.keywords ?? []).join(" ")}`} onSelect={() => go(a.href)} className="h-10" data-testid={`palette-action-${a.label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}>
                  <Zap className="size-4 text-primary" />
                  <span className="flex-1">{a.label}</span>
                  {a.shortcut && <Shortcut keys={a.shortcut} />}
                </CommandItem>
              ))}
            </CommandGroup>
            <CommandSeparator />
            <CommandGroup heading="Go to">
              {NAV.flatMap((g) => g.items)
                .filter((i) => !i.perm || can(i.perm))
                .map((i) => (
                  <CommandItem key={i.href} value={`${i.label} ${(i.keywords ?? []).join(" ")}`} onSelect={() => go(i.href)} className="h-10">
                    {i.icon ? <i.icon className="size-4 text-muted-foreground" /> : <ArrowRight className="size-4" />}
                    <span className="flex-1">{i.label}</span>
                    {i.chord && <Shortcut keys={i.chord} />}
                  </CommandItem>
                ))}
            </CommandGroup>
            {live && (
              <>
                <CommandSeparator />
                {!!parties.data?.length && (
                  <CommandGroup heading="Parties">
                    {parties.data.map((p) => (
                      <CommandItem key={p.id} value={`party ${p.name} ${p.phone ?? ""} ${p.gstin ?? ""}`} onSelect={() => go(`/parties/${p.party_type === "supplier" ? "suppliers" : "customers"}/${p.id}`)} className="h-10">
                        {p.party_type === "supplier" ? <Building2 className="size-4 text-muted-foreground" /> : <Users className="size-4 text-muted-foreground" />}
                        <span className="flex-1 truncate">{p.name}</span>
                        <span className="font-mono text-xs tabular text-muted-foreground">{money(p.outstanding)}</span>
                      </CommandItem>
                    ))}
                  </CommandGroup>
                )}
                {!!products.data?.length && (
                  <CommandGroup heading="Products">
                    {products.data.map((p) => (
                      <CommandItem key={p.id} value={`product ${p.name} ${p.sku} ${p.size ?? ""}`} onSelect={() => go(`/inventory/products/${p.id}`)} className="h-10">
                        <Package className="size-4 text-muted-foreground" />
                        <span className="flex-1 truncate">{p.name}</span>
                        <span className="font-mono text-xs tabular text-muted-foreground">
                          {p.stock_qty} {p.unit_symbol}
                        </span>
                      </CommandItem>
                    ))}
                  </CommandGroup>
                )}
                {!!invoices.data?.items.length && (
                  <CommandGroup heading="Invoices">
                    {invoices.data.items.map((d) => (
                      <CommandItem key={d.id} value={`invoice ${d.doc_no} ${d.party_name}`} onSelect={() => go(`/sales/invoices/${d.id}`)} className="h-10">
                        <Receipt className="size-4 text-muted-foreground" />
                        <span className="font-mono text-xs">{d.doc_no}</span>
                        <span className="flex-1 truncate">{d.party_name}</span>
                        <span className="font-mono text-xs tabular text-muted-foreground">{money(d.grand_total)}</span>
                      </CommandItem>
                    ))}
                  </CommandGroup>
                )}
              </>
            )}
          </CommandList>
          <div className="flex items-center justify-between border-t px-3 py-2 text-xs text-muted-foreground">
            <span>
              <Shortcut keys="↑" /> <Shortcut keys="↓" /> to navigate · <Shortcut keys="enter" /> to open · <Shortcut keys="esc" /> to close
            </span>
            <span>Press ? for all shortcuts</span>
          </div>
        </Command>
      </DialogContent>
    </Dialog>
  );
}
