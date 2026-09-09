"use client";

import { AlertCircle, Inbox, RefreshCw } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from "@/components/ui/breadcrumb";
import { money } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Fragment } from "react";

export function PageHeader({ title, description, crumbs, actions, children }: { title: string; description?: string; crumbs?: { label: string; href?: string }[]; actions?: React.ReactNode; children?: React.ReactNode }) {
  return (
    <div className="mb-6 space-y-3">
      {crumbs && (
        <Breadcrumb>
          <BreadcrumbList>
            {crumbs.map((c, i) => (
              <Fragment key={i}>
                <BreadcrumbItem>{c.href ? <BreadcrumbLink asChild><Link href={c.href}>{c.label}</Link></BreadcrumbLink> : <BreadcrumbPage>{c.label}</BreadcrumbPage>}</BreadcrumbItem>
                {i < crumbs.length - 1 && <BreadcrumbSeparator />}
              </Fragment>
            ))}
          </BreadcrumbList>
        </Breadcrumb>
      )}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl font-semibold tracking-tight" data-testid="page-title">{title}</h1>
          {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {children}
    </div>
  );
}

export function StatCard({ label, value, hint, tone, href, testId }: { label: string; value: React.ReactNode; hint?: React.ReactNode; tone?: "default" | "success" | "warning" | "danger" | "info"; href?: string; testId?: string }) {
  const toneCls = { default: "", success: "text-success", warning: "text-warning", danger: "text-destructive", info: "text-info" }[tone ?? "default"];
  const body = (
    <Card className={cn("h-full transition-colors duration-150", href && "hover:bg-muted/50")} data-testid={testId}>
      <CardContent className="p-4">
        <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</div>
        <div className={cn("mt-1 font-mono text-2xl font-semibold tabular", toneCls)}>{value}</div>
        {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
      </CardContent>
    </Card>
  );
  return href ? <Link href={href} className="block rounded-xl focus-visible:ring-focus">{body}</Link> : body;
}

export function Money({ value, className, signed, compact }: { value: string | number | null | undefined; className?: string; signed?: boolean; compact?: boolean }) {
  const num = typeof value === "string" ? parseFloat(value) : (value ?? 0);
  return <span className={cn("font-mono tabular", signed && num < 0 && "text-debit", signed && num > 0 && "text-credit", className)}>{money(value, { compact })}</span>;
}

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const map: Record<string, string> = {
    draft: "bg-muted text-muted-foreground",
    posted: "bg-success/15 text-success",
    confirmed: "bg-success/15 text-success",
    converted: "bg-info/15 text-info",
    cancelled: "bg-destructive/15 text-destructive",
    reversed: "bg-warning/20 text-warning",
    reversal: "bg-info/15 text-info",
    active: "bg-success/15 text-success",
    released: "bg-muted text-muted-foreground",
    consumed: "bg-info/15 text-info",
    issued: "bg-warning/20 text-warning",
    returned: "bg-success/15 text-success",
    lost: "bg-destructive/15 text-destructive",
    in: "bg-stock-in/15 text-stock-in",
    low: "bg-stock-low/20 text-stock-low",
    out: "bg-stock-out/15 text-stock-out",
    applied: "bg-success/15 text-success",
    pending: "bg-warning/20 text-warning",
    failed: "bg-destructive/15 text-destructive",
    conflict: "bg-destructive/15 text-destructive",
    not_configured: "bg-muted text-muted-foreground",
    opted_out: "bg-warning/20 text-warning",
    sent: "bg-success/15 text-success",
    queued: "bg-info/15 text-info",
  };
  return (
    <Badge variant="secondary" className={cn("rounded-md border-0 font-medium capitalize", map[status] ?? "", className)} data-testid={`status-${status}`}>
      {status.replace(/_/g, " ")}
    </Badge>
  );
}

export function EmptyState({ title, description, action, icon: Icon = Inbox }: { title: string; description?: string; action?: React.ReactNode; icon?: React.ComponentType<{ className?: string }> }) {
  return (
    <div className="grain relative flex flex-col items-center justify-center rounded-xl border border-dashed bg-muted/30 px-6 py-14 text-center" data-testid="empty-state">
      <div className="mb-3 grid size-12 place-items-center rounded-full bg-background shadow-sm">
        <Icon className="size-5 text-muted-foreground" />
      </div>
      <h3 className="font-heading text-base font-semibold">{title}</h3>
      {description && <p className="mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm" role="alert" data-testid="error-state">
      <AlertCircle className="mt-0.5 size-4 shrink-0 text-destructive" />
      <div className="flex-1">
        <div className="font-medium text-destructive">Something went wrong</div>
        <div className="text-muted-foreground">{message}</div>
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry} data-testid="error-retry-button">
          <RefreshCw className="size-3.5" /> Retry
        </Button>
      )}
    </div>
  );
}

export function TableSkeleton({ rows = 8, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div className="space-y-2" data-testid="loading-state">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="grid gap-3" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}>
          {Array.from({ length: cols }).map((_, j) => (
            <Skeleton key={j} className="h-8" />
          ))}
        </div>
      ))}
    </div>
  );
}

export function Field({ label, htmlFor, children, hint, className, required }: { label: string; htmlFor?: string; children: React.ReactNode; hint?: string; className?: string; required?: boolean }) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <label htmlFor={htmlFor} className="text-xs font-medium text-muted-foreground">
        {label}
        {required && <span className="text-destructive"> *</span>}
      </label>
      {children}
      {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  );
}
