"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Package, Receipt, TrendingUp, Wallet } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Area, AreaChart, ResponsiveContainer, Tooltip as RTooltip, XAxis, YAxis } from "recharts";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { DataTable } from "@/components/shared/data-table";
import { ErrorState, Money, PageHeader, StatCard, StatusBadge } from "@/components/shared/page";
import { errorMessage, get } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { dateFmt, money, qty } from "@/lib/format";
import { docHref } from "@/lib/types";
import { Shortcut } from "@/components/keyboard/shortcut";

interface Dashboard {
  date: string;
  sales_today: string;
  invoices_today: number;
  sales_month: string;
  invoices_month: number;
  sales_fy: string;
  purchase_month: string;
  receivables: string;
  receivables_overdue: string;
  payables: string;
  payables_overdue: string;
  cash_bank: { ledger_id: string; name: string; balance: string; is_bank: boolean }[];
  stock_value: string;
  low_stock_count: number;
  low_stock: { product_id: string; name: string; qty: string; unit: string; reorder_level: string; status: string }[];
  trend: { date: string; amount: string }[];
  top_products: { product_id: string; name: string; qty: string; amount: string }[];
  recent_documents: { id: string; doc_type: string; doc_no: string; date: string; party_name: string; grand_total: string; status: string }[];
  gross_profit_month: string;
  net_profit_month: string;
  top_debtors: { party_id: string; party: string; balance: string; overdue: string; bills: number }[];
}

export default function DashboardPage() {
  const { me } = useAuth();
  const router = useRouter();
  const q = useQuery({ queryKey: ["dashboard"], queryFn: () => get<Dashboard>("/reports/dashboard"), refetchInterval: 60_000 });
  const d = q.data;
  const company = me?.companies.find((c) => c.id === me.current_company_id) ?? me?.companies[0];

  return (
    <div data-testid="dashboard-page">
      <PageHeader
        title={`Good ${greeting()}, ${me?.user.full_name.split(" ")[0] ?? ""}`}
        description={`${company?.name ?? ""} · ${dateFmt(d?.date ?? new Date().toISOString().slice(0, 10), "EEEE, dd MMMM yyyy")}`}
        actions={
          <>
            <Button asChild variant="outline">
              <Link href="/accounting/vouchers/new?type=receipt">
                Receive payment <Shortcut keys="alt+r" className="ml-1" />
              </Link>
            </Button>
            <Button asChild>
              <Link href="/sales/invoices/new" data-testid="dashboard-new-invoice">
                New invoice <Shortcut keys="alt+n" className="ml-1" />
              </Link>
            </Button>
          </>
        }
      />
      {q.isError && <ErrorState message={errorMessage(q.error)} onRetry={() => q.refetch()} />}
      {q.isLoading && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" data-testid="loading-state">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      )}
      {d && (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Sales today" value={money(d.sales_today, { compact: true })} hint={`${d.invoices_today} invoice${d.invoices_today === 1 ? "" : "s"}`} href="/sales/invoices" testId="stat-sales-today" />
            <StatCard label="Sales this month" value={money(d.sales_month, { compact: true })} hint={`${d.invoices_month} invoices · FY ${money(d.sales_fy, { compact: true })}`} href="/sales/invoices" testId="stat-sales-month" />
            <StatCard label="Receivables" value={money(d.receivables, { compact: true })} hint={<span className={parseFloat(d.receivables_overdue) > 0 ? "text-destructive" : ""}>{money(d.receivables_overdue, { compact: true })} overdue</span>} tone={parseFloat(d.receivables_overdue) > 0 ? "warning" : "default"} href="/accounting/outstanding" testId="stat-receivables" />
            <StatCard label="Payables" value={money(d.payables, { compact: true })} hint={`${money(d.payables_overdue, { compact: true })} overdue`} href="/accounting/outstanding?kind=payable" testId="stat-payables" />
            <StatCard label="Gross profit (month)" value={money(d.gross_profit_month, { compact: true })} hint={`Net ${money(d.net_profit_month, { compact: true })}`} tone={parseFloat(d.net_profit_month) >= 0 ? "success" : "danger"} href="/accounting/reports/profit-loss" testId="stat-gross-profit" />
            <StatCard label="Stock value" value={money(d.stock_value, { compact: true })} hint={`${d.low_stock_count} item${d.low_stock_count === 1 ? "" : "s"} at/below reorder level`} tone={d.low_stock_count ? "warning" : "default"} href="/inventory/stock" testId="stat-stock-value" />
            <StatCard label="Purchases this month" value={money(d.purchase_month, { compact: true })} href="/purchase/bills" testId="stat-purchases" />
            <Card className="h-full" data-testid="stat-cash-bank">
              <CardContent className="p-4">
                <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Cash & bank</div>
                <ul className="mt-1 space-y-0.5">
                  {d.cash_bank.map((c) => (
                    <li key={c.ledger_id} className="flex items-center justify-between text-sm">
                      <Link href={`/accounting/ledgers/${c.ledger_id}`} className="truncate text-muted-foreground hover:text-foreground">
                        {c.name}
                      </Link>
                      <Money value={c.balance} className="font-medium" />
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 xl:grid-cols-3">
            <Card className="xl:col-span-2">
              <CardHeader className="flex-row items-center justify-between pb-2">
                <CardTitle className="flex items-center gap-2 text-base">
                  <TrendingUp className="size-4 text-primary" /> Sales - last 30 days
                </CardTitle>
                <span className="text-xs text-muted-foreground">Posted invoices</span>
              </CardHeader>
              <CardContent className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={d.trend.map((t) => ({ ...t, amount: parseFloat(t.amount), label: dateFmt(t.date, "dd MMM") }))} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
                    <defs>
                      <linearGradient id="salesFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.35} />
                        <stop offset="100%" stopColor="var(--primary)" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="label" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} tickLine={false} axisLine={false} interval={4} />
                    <YAxis tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} tickLine={false} axisLine={false} width={64} tickFormatter={(v) => money(v, { compact: true })} />
                    <RTooltip contentStyle={{ background: "var(--popover)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }} formatter={(v) => [money(v as number), "Sales"]} labelStyle={{ color: "var(--muted-foreground)" }} />
                    <Area type="monotone" dataKey="amount" stroke="var(--primary)" strokeWidth={2} fill="url(#salesFill)" />
                  </AreaChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex-row items-center justify-between pb-2">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Wallet className="size-4 text-primary" /> Top debtors
                </CardTitle>
                <Button asChild variant="ghost" size="sm">
                  <Link href="/accounting/outstanding">
                    All <ArrowRight className="size-3.5" />
                  </Link>
                </Button>
              </CardHeader>
              <CardContent>
                <ul className="divide-y">
                  {d.top_debtors.map((p) => (
                    <li key={p.party_id} className="flex items-center justify-between py-2 text-sm">
                      <Link href={`/parties/customers/${p.party_id}`} className="min-w-0 truncate hover:underline">
                        {p.party}
                      </Link>
                      <div className="text-right">
                        <Money value={p.balance} className="font-medium" />
                        {parseFloat(p.overdue) > 0 && <div className="text-xs text-destructive">{money(p.overdue, { compact: true })} overdue</div>}
                      </div>
                    </li>
                  ))}
                  {!d.top_debtors.length && <li className="py-6 text-center text-sm text-muted-foreground">No receivables. Nice.</li>}
                </ul>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 xl:grid-cols-3">
            <Card className="xl:col-span-2">
              <CardHeader className="flex-row items-center justify-between pb-2">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Receipt className="size-4 text-primary" /> Recent documents
                </CardTitle>
                <span className="text-xs text-muted-foreground">
                  <Shortcut keys="j" /> <Shortcut keys="k" /> to move · <Shortcut keys="enter" /> to open
                </span>
              </CardHeader>
              <CardContent>
                <DataTable
                  rows={d.recent_documents}
                  rowKey={(r) => r.id}
                  compact
                  keyboard={false}
                  testId="recent-documents-table"
                  onOpen={(r) => router.push(docHref(r.doc_type, r.id))}
                  columns={[
                    { key: "no", header: "Number", cell: (r) => <span className="font-mono text-xs">{r.doc_no}</span> },
                    { key: "type", header: "Type", cell: (r) => <span className="capitalize text-muted-foreground">{r.doc_type.replace(/_/g, " ")}</span> },
                    { key: "date", header: "Date", cell: (r) => dateFmt(r.date) },
                    { key: "party", header: "Party", cell: (r) => <span className="truncate">{r.party_name}</span> },
                    { key: "amount", header: "Amount", align: "right", cell: (r) => money(r.grand_total) },
                    { key: "status", header: "Status", cell: (r) => <StatusBadge status={r.status} /> },
                  ]}
                />
              </CardContent>
            </Card>
            <div className="space-y-4">
              <Card>
                <CardHeader className="flex-row items-center justify-between pb-2">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Package className="size-4 text-primary" /> Low stock
                  </CardTitle>
                  <Button asChild variant="ghost" size="sm">
                    <Link href="/inventory/stock?low=1">
                      All <ArrowRight className="size-3.5" />
                    </Link>
                  </Button>
                </CardHeader>
                <CardContent>
                  <ul className="divide-y">
                    {d.low_stock.map((p) => (
                      <li key={p.product_id} className="flex items-center justify-between gap-2 py-2 text-sm">
                        <Link href={`/inventory/products/${p.product_id}`} className="min-w-0 truncate hover:underline">
                          {p.name}
                        </Link>
                        <span className="flex items-center gap-2">
                          <span className="font-mono text-xs tabular">
                            {qty(p.qty)} {p.unit}
                          </span>
                          <StatusBadge status={p.status} />
                        </span>
                      </li>
                    ))}
                    {!d.low_stock.length && <li className="py-6 text-center text-sm text-muted-foreground">All products above reorder level.</li>}
                  </ul>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Top products this month</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="divide-y">
                    {d.top_products.map((p) => (
                      <li key={p.product_id} className="flex items-center justify-between gap-2 py-2 text-sm">
                        <Link href={`/inventory/products/${p.product_id}`} className="min-w-0 truncate hover:underline">
                          {p.name}
                        </Link>
                        <Money value={p.amount} className="text-muted-foreground" compact />
                      </li>
                    ))}
                    {!d.top_products.length && <li className="py-6 text-center text-sm text-muted-foreground">No sales yet this month.</li>}
                  </ul>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function greeting(): string {
  const h = new Date().getHours();
  return h < 12 ? "morning" : h < 17 ? "afternoon" : "evening";
}
