"use client";

import { ChevronDown, LogOut, Moon, Search, Sun, HelpCircle, Menu, Plus } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useAuth } from "@/lib/auth";
import { useHotkeys } from "@/lib/keyboard/useHotkeys";
import { ACTIONS, NAV } from "@/lib/nav";
import { cn } from "@/lib/utils";
import { CommandPalette } from "@/components/keyboard/command-palette";
import { ShortcutCheatsheet } from "@/components/keyboard/cheatsheet";
import { Shortcut } from "@/components/keyboard/shortcut";
import { Kbd } from "@/components/ui/kbd";
import { ScrollArea } from "@/components/ui/scroll-area";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { me, logout, switchCompany, can, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const { resolvedTheme, setTheme } = useTheme();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [cheatOpen, setCheatOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const chordSpecs = useMemo(
    () =>
      NAV.flatMap((g) => g.items)
        .filter((i) => i.chord && (!i.perm || can(i.perm)))
        .map((i) => ({ keys: i.chord!, handler: () => router.push(i.href) })),
    [router, can],
  );
  const actionSpecs = useMemo(
    () =>
      ACTIONS.filter((a) => a.shortcut && (!a.perm || can(a.perm))).map((a) => ({ keys: a.shortcut!, handler: () => router.push(a.href), inInputs: true })),
    [router, can],
  );

  useHotkeys([
    { keys: "mod+k", handler: () => setPaletteOpen((o) => !o), inInputs: true },
    { keys: "?", handler: () => setCheatOpen((o) => !o) },
    { keys: "mod+d", handler: () => setTheme(resolvedTheme === "dark" ? "light" : "dark"), inInputs: true },
    ...chordSpecs,
    ...actionSpecs,
  ]);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  const company = me?.companies.find((c) => c.id === (me?.current_company_id ?? "")) ?? me?.companies[0];
  const branches = me?.branches.filter((b) => b.company_id === company?.id) ?? [];
  const branch = branches.find((b) => b.id === me?.current_branch_id) ?? branches[0];

  const sidebar = (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
      <div className="flex h-14 items-center gap-2 border-b border-sidebar-border px-4">
        <div className="grid size-8 place-items-center rounded-lg bg-primary text-primary-foreground font-heading text-sm font-bold">T</div>
        <div className="leading-tight">
          <div className="font-heading text-sm font-semibold">TileOS</div>
          <div className="text-[11px] text-muted-foreground">Business operating system</div>
        </div>
      </div>
      <div className="border-b border-sidebar-border p-3">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex w-full items-center justify-between rounded-md border bg-background px-3 py-2 text-left text-sm transition-colors duration-150 hover:bg-muted" data-testid="company-switcher">
              <span className="min-w-0">
                <span className="block truncate font-medium">{company?.name ?? (loading ? "Loading..." : "No company")}</span>
                <span className="block truncate text-xs text-muted-foreground">{branch?.name ?? "All branches"}</span>
              </span>
              <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-64" align="start">
            <DropdownMenuLabel>Companies</DropdownMenuLabel>
            {me?.companies.map((c) => (
              <DropdownMenuItem key={c.id} onSelect={() => switchCompany(c.id).then(() => toast.success(`Switched to ${c.name}`))} data-testid={`switch-company-${c.id}`}>
                <span className={cn("flex-1 truncate", c.id === company?.id && "font-semibold")}>{c.name}</span>
                {c.id === company?.id && <span className="text-xs text-primary">current</span>}
              </DropdownMenuItem>
            ))}
            {branches.length > 1 && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuLabel>Branches</DropdownMenuLabel>
                {branches.map((b) => (
                  <DropdownMenuItem key={b.id} onSelect={() => company && switchCompany(company.id, b.id).then(() => toast.success(`Branch: ${b.name}`))}>
                    <span className={cn("flex-1 truncate", b.id === branch?.id && "font-semibold")}>{b.name}</span>
                  </DropdownMenuItem>
                ))}
              </>
            )}
            {can("settings.manage") && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={() => router.push("/settings/company?new=1")}>
                  <Plus className="size-4" /> Add company
                </DropdownMenuItem>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <ScrollArea className="flex-1">
        <nav className="space-y-4 p-3" aria-label="Primary">
          {NAV.map((g) => {
            const items = g.items.filter((i) => !i.perm || can(i.perm));
            if (!items.length) return null;
            return (
              <div key={g.label}>
                <div className="mb-1 px-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{g.label}</div>
                <ul className="space-y-0.5">
                  {items.map((i) => {
                    const active = pathname === i.href || (i.href !== "/dashboard" && pathname.startsWith(i.href + "/")) || (pathname.startsWith(i.href) && i.href.split("/").length > 2 && pathname.split("/").slice(0, 3).join("/") === i.href);
                    const Icon = i.icon;
                    return (
                      <li key={i.href}>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Link
                              href={i.href}
                              data-testid={`nav-${i.href.replace(/\//g, "-").replace(/^-/, "")}`}
                              aria-current={active ? "page" : undefined}
                              className={cn(
                                "flex h-9 items-center gap-2.5 rounded-md px-2 text-sm transition-colors duration-150 hover:bg-muted focus-visible:bg-muted",
                                active ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground" : "text-sidebar-foreground/90",
                              )}
                            >
                              {Icon && <Icon className={cn("size-4", active ? "text-primary" : "text-muted-foreground")} />}
                              <span className="flex-1 truncate">{i.label}</span>
                              {i.chord && <Shortcut keys={i.chord} className="opacity-0 transition-opacity duration-150 group-hover:opacity-100 [li:hover_&]:opacity-100" />}
                            </Link>
                          </TooltipTrigger>
                          {i.chord && (
                            <TooltipContent side="right">
                              {i.label} <Shortcut keys={i.chord} className="ml-2" />
                            </TooltipContent>
                          )}
                        </Tooltip>
                      </li>
                    );
                  })}
                </ul>
              </div>
            );
          })}
        </nav>
      </ScrollArea>
      <div className="border-t border-sidebar-border p-3">
        <div className="flex items-center gap-2">
          <Avatar className="size-8">
            <AvatarFallback className="bg-accent text-accent-foreground text-xs font-semibold">{initials(me?.user.full_name)}</AvatarFallback>
          </Avatar>
          <div className="min-w-0 flex-1 leading-tight">
            <div className="truncate text-sm font-medium" data-testid="current-user-name">{me?.user.full_name ?? ""}</div>
            <div className="truncate text-xs text-muted-foreground">{me?.role.name}</div>
          </div>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon-sm" onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")} aria-label="Toggle theme" data-testid="theme-toggle">
                <Sun className="size-4 dark:hidden" />
                <Moon className="hidden size-4 dark:block" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              Toggle theme <Shortcut keys="mod+d" className="ml-2" />
            </TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon-sm" onClick={() => logout()} aria-label="Sign out" data-testid="logout-button">
                <LogOut className="size-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Sign out</TooltipContent>
          </Tooltip>
        </div>
      </div>
    </div>
  );

  return (
    <div className="grid min-h-screen grid-cols-1 lg:grid-cols-[260px_1fr]">
      <aside className="hidden border-r lg:block">
        <div className="sticky top-0 h-screen">{sidebar}</div>
      </aside>
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent side="left" className="w-[280px] p-0">
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          {sidebar}
        </SheetContent>
      </Sheet>
      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-topbar/90 px-4 backdrop-blur sm:px-6">
          <Button variant="ghost" size="icon-sm" className="lg:hidden" onClick={() => setMobileOpen(true)} aria-label="Open navigation">
            <Menu className="size-4" />
          </Button>
          <Button variant="secondary" className="h-9 w-full max-w-md justify-start gap-2 text-muted-foreground" onClick={() => setPaletteOpen(true)} data-testid="command-palette-trigger">
            <Search className="size-4" />
            <span className="flex-1 text-left">Search or jump to...</span>
            <Shortcut keys="mod+k" />
          </Button>
          <div className="ml-auto flex items-center gap-2">
            {can("sales.write") && (
              <Button asChild size="default" className="hidden sm:inline-flex" data-testid="topbar-new-invoice">
                <Link href="/sales/invoices/new">
                  <Plus className="size-4" /> New invoice <Kbd className="ml-1 bg-primary-foreground/20 text-primary-foreground">Alt N</Kbd>
                </Link>
              </Button>
            )}
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon-sm" onClick={() => setCheatOpen(true)} aria-label="Keyboard shortcuts" data-testid="cheatsheet-trigger">
                  <HelpCircle className="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                Shortcuts <Shortcut keys="?" className="ml-2" />
              </TooltipContent>
            </Tooltip>
          </div>
        </header>
        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <div className="mx-auto w-full max-w-[1600px]">{children}</div>
        </main>
      </div>
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
      <ShortcutCheatsheet open={cheatOpen} onOpenChange={setCheatOpen} />
    </div>
  );
}

function initials(name?: string): string {
  if (!name) return "?";
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0]?.toUpperCase())
    .join("");
}
