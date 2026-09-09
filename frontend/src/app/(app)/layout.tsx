"use client";

import { AppShell } from "@/components/shell/app-shell";
import { useAuth } from "@/lib/auth";
import { Skeleton } from "@/components/ui/skeleton";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { ready, authenticated } = useAuth();
  if (!ready || !authenticated) {
    return (
      <div className="grid min-h-screen grid-cols-[260px_1fr]" data-testid="loading-state">
        <div className="border-r bg-sidebar p-4">
          <Skeleton className="mb-6 h-8 w-32" />
          {Array.from({ length: 10 }).map((_, i) => (
            <Skeleton key={i} className="mb-2 h-8 w-full" />
          ))}
        </div>
        <div className="p-8">
          <Skeleton className="mb-4 h-8 w-64" />
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    );
  }
  return <AppShell>{children}</AppShell>;
}
