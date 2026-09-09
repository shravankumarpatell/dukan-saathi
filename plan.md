# TileOS — Plan (POC-first → V1 → Expand)

## 1) Objectives
- Deliver a working, keyboard-first ERP MVP on **Next.js 16 + FastAPI + PostgreSQL 18** with **full multi-tenancy** and **double-entry accounting correctness**.
- Prove the **core workflow** first (hardest + most failure-prone): **post a Sales Invoice → voucher posting (balanced) → stock ledger movement → GST split → customer outstanding**.
- Build the product shell (command palette, G-chords, grid nav) early so every screen is keyboard-complete.
- Provide minimal-but-functional stubs for Phase 8–12 (sync/WhatsApp/AI/BI/Tally) + docs.

## 2) Implementation Steps

### Phase 1 — Core POC (Isolation) ✅ must pass before building the full app
**Goal:** Prove accounting+inventory+tax “effect chain” and immutability on Postgres.

**User stories (POC)**
1. As a user, I can create a tenant/company/branch and an admin user via seed so I can log in immediately.
2. As a billing operator, I can create a product with unit conversions (box↔sqft) so quantities compute safely.
3. As a billing operator, I can post a Sales Invoice and the system creates balanced voucher lines (Dr A/R, Cr Sales, Cr Output GST).
4. As an inventory manager, posting the invoice reduces stock by batch/shade/godown and writes a stock-ledger entry.
5. As an accountant, I can view customer ledger statement and outstanding after posting.

**Steps**
- Backend POC script (Python) against live DB:
  - Run `/app/scripts/ensure_pg.sh` (already) and connect via `DATABASE_URL`.
  - Create minimal tables (Alembic) for: tenant/company/branch/user, product, stock ledger, ledger/coas, voucher/voucher_line.
  - Implement `post_sales_invoice()` domain service (single transaction): validate → write invoice → write voucher + lines → write stock movements → compute GST → audit.
  - Enforce: immutable posted voucher, balanced debits=credits, money as Decimal.
- Add report queries for: trial balance, ledger statement, outstanding.
- **Test until green:** `pytest` + a standalone script that posts one invoice and asserts:
  - voucher balanced
  - inventory reduced
  - GST amounts correct
  - outstanding updated

### Phase 2 — V1 App Development (MVP, minimal bulk changes)
**Goal:** UI + API for the core modules (Accounting + Inventory + Sales) with keyboard-first UX.

**User stories (V1)**
1. As a user, I can log in and switch tenant/company/branch so I never mix data.
2. As a user, I can press **Cmd/Ctrl+K** and jump to “New Sales Invoice” from anywhere.
3. As a billing operator, I can create a Sales Invoice end-to-end with **zero mouse** (customer/product combobox, line grid, save).
4. As an accountant, I can open Trial Balance and verify it matches voucher postings.
5. As an inventory manager, I can see stock by godown/batch/shade and verify it changes after invoicing.

**Backend (FastAPI + SQLAlchemy async + Alembic)**
- Create `/app/backend/app/` package:
  - `config.py` (reads `DATABASE_URL`, JWT secrets), `db.py` (async engine/session), `migrations/` (Alembic).
  - Models: tenant/company/branch, users/roles/permissions, refresh_tokens, audit_log.
  - Accounting: fiscal_year, account_group, ledger, voucher, voucher_line, bill_allocation.
  - Inventory: unit, conversion, brand/category, product (+ tile attrs), godown, batch/shade/calibre, stock_ledger.
  - Sales/Purchase minimal: sales_invoice(+lines), purchase_bill(+lines).
- Auth (per prompt): access + refresh JWT, RBAC claims, tenant scoping middleware.
- API endpoints (minimal, typed):
  - Auth: login/refresh/logout/me
  - Masters: parties, products, ledgers, godowns, units
  - Core flows: sales invoices CRUD + **POST /sales-invoices/{id}/post**; vouchers list/view; reports (trial balance, ledger, outstanding)
- Audit log on every mutation; tenant_id on every row.

**Frontend (Next.js App Router)**
- Set `package.json` start to: `next dev -p 3000 -H 0.0.0.0` (supervisor requirement).
- Apply `/app/design_guidelines.md` tokens in `globals.css` (OKLCH, Manrope + IBM Plex Mono).
- App shell:
  - Sidebar + topbar, theme toggle, user menu.
  - Command palette (cmdk) with route/action registry.
  - Keyboard architecture primitives: `useGridNav`, `useComboboxNav`, `?` cheatsheet.
- Data layer:
  - Generate TS client from FastAPI OpenAPI (or minimal axios client first, then generate).
  - TanStack Query for all server state.
- Core screens:
  - Login
  - Dashboard (balances, receivables/payables, low stock)
  - Sales Invoice list + **keyboard-complete invoice editor**
  - Products + stock view
  - Accounting vouchers list + ledger statement
  - Trial balance

**Checkpoint: run testing agent**
- End-to-end: login → create invoice draft → post → verify trial balance + stock.

### Phase 3 — Expand to “full goal” (Phases 3–7 real modules)
**Goal:** Add Purchase, GST depth, and Tile domain depth; keep UX keyboard-first.

**User stories (Expansion)**
1. As a user, I can do Purchase Bill posting that increases stock and posts input GST.
2. As a user, I can do returns/credit notes and the system creates reversal vouchers.
3. As a user, I can manage batches/shades/calibres and prevent wrong-shade dispatch.
4. As a user, I can run GST summary (GSTR-1 style) by period and export.
5. As a manager, I can lock fiscal periods so posted vouchers can’t be altered.

**Steps**
- Inventory valuation (weighted average) + stock transfers/adjustments.
- Sales documents (quotation/order/delivery challan) minimally linked to invoice.
- Purchase documents (PO/GRN/Bill) minimally linked.
- GST engine v1: HSN, CGST/SGST/IGST rules, place-of-supply, round-off.
- Reports: P&L, Balance Sheet, Day Book, Ageing.
- Testing agent round: core workflows + keyboard-only tests (Playwright) for invoice flow.

### Phase 4 — Minimal-but-functional modules for Phases 8–12 (stubs + docs)
**Goal:** Deliver working scaffolds with safe boundaries and clear ADRs.

**User stories (Stretch)**
1. As a user, I can see an “Outbox” of pending operations for offline/sync (even if conflicts are manual).
2. As a user, I can send an invoice via a provider-agnostic WhatsApp stub and see delivery status logged.
3. As a user, I can ask AI for a read-only report summary (no direct financial mutation).
4. As a user, I can view BI cards (dead stock, top customers) computed from real data.
5. As a user, I can export ledgers/vouchers as Tally XML.

**Steps**
- Sync: outbox table + idempotency keys + “replay” endpoint (no real multi-device conflict resolution yet).
- WhatsApp: message templates + message_log + provider interface stub.
- AI: `/ai/query` read-only tool router; explicit denylist for mutations.
- BI: endpoints for dead stock, top customers, cashflow projection.
- Tally: XML export (ledgers + vouchers) minimal.
- Docs: ADRs (auth, tenant isolation, background tasks via FastAPI BackgroundTasks, offline mechanism deferred).

### Phase 5 — Seed data + hardening + documentation
**User stories (Hardening)**
1. As a demo user, I can log in with `admin@demo.tileos / Admin@123` and see meaningful sample data.
2. As a user, I can recover from API errors without losing my draft invoice.
3. As an admin, I can audit who posted what and when.
4. As a user, I can use keyboard shortcuts consistently across screens.
5. As an operator, I can export key reports (CSV/PDF later) reliably.

**Steps**
- Seed script: Tenant “Shree Tiles & Sanitary”, COA, ledgers, products, stock, customers, few invoices.
- Add constraints + indexes (tenant_id, dates, voucher_no).
- Final testing agent: full regression.
- Update `/docs/*` + `PROJECT_MEMORY.md`.

## 3) Next Actions (immediate)
1. Update supervisor compatibility: set frontend start script to `next dev -p 3000 -H 0.0.0.0`.
2. Finish shadcn install and apply design tokens from `/app/design_guidelines.md`.
3. Implement backend `app/` skeleton + Alembic init + `DATABASE_URL` wiring.
4. Write Phase-1 POC script + pytest: post one sales invoice and assert voucher/stock/outstanding.
5. Only after POC is green: build UI shell + invoice editor.

## 4) Success Criteria
- **Core POC passes:** sales invoice posting produces balanced double-entry + stock ledger + GST + outstanding, immutable postings.
- **Keyboard-first:** invoice creation is fully keyboard-only (Cmd+K, combobox, grid nav, Enter-to-next-row).
- **Multi-tenant safety:** tenant_id enforced everywhere; no cross-tenant leakage in tests.
- **Reports correct:** trial balance matches vouchers; ledger statement and outstanding align with postings.
- **Seeded demo works:** user can log in and run the full demo flow immediately.

## Deployment caveat (explicit)
- Postgres runs inside this dev container. For hosted deployment, set `DATABASE_URL` to an external Postgres 18 instance; code must not depend on local apt-installed Postgres beyond dev bootstrap.
