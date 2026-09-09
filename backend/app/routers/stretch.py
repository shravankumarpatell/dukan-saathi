"""Stretch modules (PRD phases 8-12): sync outbox, WhatsApp (provider-agnostic), AI assistant (tool-based, read-only), BI, Tally export."""
from __future__ import annotations

import re
import uuid
from datetime import date, timedelta
from decimal import Decimal
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..deps import Ctx, get_ctx, require
from ..models import Company, Ledger, Party, Product, SyncOutbox, TradeDocument, TradeLine, Voucher, WhatsAppMessage
from ..schemas import AIQueryIn, SyncPushIn, WhatsAppSendIn
from ..services import reports as R
from ..services.common import ZERO, audit, money, now
from ..services.stock import stock_summary
from ..services.trade import party_outstanding

router = APIRouter(tags=["stretch"])


# ------------------------------------------------------------------ SYNC (offline outbox replay with idempotency)
@router.post("/sync/push")
async def sync_push(data: SyncPushIn, ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    """Accept queued client operations. Each (device_id, op_id) is applied at most once.

    Supported entity_type/operation pairs are routed to the same domain services used by the UI.
    Unknown operations are stored as 'failed' so the client can surface them.
    """
    results = []
    for op in data.operations:
        op_id = str(op.get("op_id") or "")
        if not op_id:
            results.append({"op_id": None, "status": "failed", "error": "op_id required"})
            continue
        existing = (await db.execute(select(SyncOutbox).where(SyncOutbox.tenant_id == ctx.tenant_id, SyncOutbox.device_id == data.device_id, SyncOutbox.op_id == op_id))).scalar_one_or_none()
        if existing:
            results.append({"op_id": op_id, "status": existing.status, "result": existing.result, "duplicate": True})
            continue
        row = SyncOutbox(tenant_id=ctx.tenant_id, company_id=ctx.company_id, device_id=data.device_id, op_id=op_id, entity_type=str(op.get("entity_type", "")), operation=str(op.get("operation", "")), payload=op.get("payload") or {}, created_at=now())
        db.add(row)
        await db.flush()
        try:
            result = await _apply_op(db, ctx, row, op_id)
            row.status = "applied"
            row.result = result
            row.acked_at = now()
        except HTTPException as e:
            row.status = "conflict" if e.status_code == 409 else "failed"
            row.result = {"error": e.detail}
            row.retry_count += 1
        results.append({"op_id": op_id, "status": row.status, "result": row.result})
    await db.commit()
    return {"device_id": data.device_id, "results": results, "server_time": now()}


async def _apply_op(db: AsyncSession, ctx: Ctx, row: SyncOutbox, op_id: str) -> dict:
    from ..schemas import TradeDocIn, VoucherIn
    from ..services import trade as T
    from ..services.posting import LineSpec, post_voucher

    payload = dict(row.payload)
    if row.entity_type in ("sales_invoice", "quotation", "sales_order", "purchase_bill", "purchase_order") and row.operation == "create":
        payload.setdefault("idempotency_key", f"sync:{row.device_id}:{op_id}")
        data = TradeDocIn(**payload)
        d = await T.build_document(db, ctx, row.entity_type, data)
        if data.post:
            await T.post_document(db, ctx, d)
        return {"id": str(d.id), "doc_no": d.doc_no, "status": d.status}
    if row.entity_type == "voucher" and row.operation == "create":
        payload.setdefault("idempotency_key", f"sync:{row.device_id}:{op_id}")
        data = VoucherIn(**payload)
        v = await post_voucher(db, ctx, voucher_type=data.voucher_type, on=data.date, lines=[LineSpec(l.ledger_id, l.debit, l.credit, l.narration) for l in data.lines], narration=data.narration, idempotency_key=data.idempotency_key)
        return {"id": str(v.id), "voucher_no": v.voucher_no}
    raise HTTPException(422, f"Unsupported sync operation {row.entity_type}.{row.operation}")


@router.get("/sync/status")
async def sync_status(device_id: str | None = None, ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    stmt = select(SyncOutbox.status, func.count()).where(SyncOutbox.tenant_id == ctx.tenant_id)
    if device_id:
        stmt = stmt.where(SyncOutbox.device_id == device_id)
    rows = (await db.execute(stmt.group_by(SyncOutbox.status))).all()
    recent = (await db.execute(select(SyncOutbox).where(SyncOutbox.tenant_id == ctx.tenant_id).order_by(SyncOutbox.created_at.desc()).limit(50))).scalars().all()
    return {"counts": {s: c for s, c in rows}, "recent": [{"op_id": r.op_id, "device_id": r.device_id, "entity_type": r.entity_type, "operation": r.operation, "status": r.status, "result": r.result, "created_at": r.created_at} for r in recent], "server_time": now()}


# ------------------------------------------------------------------ WHATSAPP (approved-provider interface; no provider configured => logged as not_configured)
TEMPLATES = {
    "invoice": "Dear {party}, your invoice {doc_no} dated {date} for Rs {amount} from {company} is ready. Thank you for your business.",
    "quotation": "Dear {party}, please find quotation {doc_no} dated {date} for Rs {amount} from {company}. Valid till {valid_till}.",
    "outstanding_reminder": "Dear {party}, a gentle reminder that Rs {outstanding} is outstanding with {company}. Kindly arrange payment. Reply STOP to opt out.",
    "payment_thanks": "Dear {party}, we have received your payment of Rs {amount}. Thank you! - {company}",
    "delivery_update": "Dear {party}, your order {doc_no} has been dispatched from {company}. Vehicle: {vehicle}.",
    "custom": "{body}",
}


@router.post("/whatsapp/send")
async def whatsapp_send(data: WhatsAppSendIn, ctx: Ctx = Depends(require("sales.view")), db: AsyncSession = Depends(get_db)):
    party = await db.get(Party, data.party_id)
    if not party or party.company_id != ctx.company_id:
        raise HTTPException(404, "Party not found")
    phone = party.whatsapp or party.phone
    if not phone:
        raise HTTPException(422, f"{party.name} has no WhatsApp/phone number")
    company = await db.get(Company, ctx.company_id)
    doc = await db.get(TradeDocument, data.doc_id) if data.doc_id else None
    vars_ = {
        "party": party.name,
        "company": company.name,
        "doc_no": doc.doc_no if doc else "",
        "date": doc.date.strftime("%d-%m-%Y") if doc else "",
        "amount": f"{doc.grand_total:,.2f}" if doc else "",
        "valid_till": doc.valid_till.strftime("%d-%m-%Y") if doc and doc.valid_till else "",
        "vehicle": doc.vehicle_no if doc and doc.vehicle_no else "-",
        "outstanding": f"{await party_outstanding(db, ctx.company_id, party.id, 'receivable'):,.2f}",
        "body": data.custom_body or "",
    }
    body = TEMPLATES[data.template].format(**vars_)
    msg = WhatsAppMessage(tenant_id=ctx.tenant_id, company_id=ctx.company_id, party_id=party.id, phone=phone, template=data.template, body=body, doc_type=doc.doc_type if doc else None, doc_id=doc.id if doc else None, created_at=now())
    if not party.whatsapp_opt_in and data.template == "outstanding_reminder":
        msg.status = "opted_out"
        msg.error = "Party has not opted in to reminders"
    else:
        # Provider adapter boundary: no WhatsApp Business provider credentials configured in this environment.
        msg.status = "not_configured"
        msg.error = "WhatsApp Business provider not configured. Message logged; use the wa.me link to send manually."
    db.add(msg)
    await audit(db, ctx, "whatsapp", "party", party.id, f"WhatsApp {data.template} to {phone}: {msg.status}")
    await db.commit()
    await db.refresh(msg)
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10:
        digits = "91" + digits
    from urllib.parse import quote

    return {"id": msg.id, "status": msg.status, "phone": phone, "body": body, "wa_link": f"https://wa.me/{digits}?text={quote(body)}", "error": msg.error}


@router.get("/whatsapp/messages")
async def whatsapp_messages(limit: int = Query(100, le=500), ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(WhatsAppMessage, Party.name).join(Party, Party.id == WhatsAppMessage.party_id, isouter=True).where(WhatsAppMessage.company_id == ctx.company_id).order_by(WhatsAppMessage.created_at.desc()).limit(limit))).all()
    return [{"id": m.id, "party": pn, "phone": m.phone, "template": m.template, "body": m.body, "status": m.status, "error": m.error, "created_at": m.created_at} for m, pn in rows]


# ------------------------------------------------------------------ AI assistant (deterministic intent router over domain services; read-only)
@router.post("/ai/query")
async def ai_query(data: AIQueryIn, ctx: Ctx = Depends(require("reports.view")), db: AsyncSession = Depends(get_db)):
    """Natural-language questions are mapped to domain read services. The assistant NEVER mutates data."""
    q = data.question.lower().strip()
    today = date.today()
    tools_used: list[str] = []

    def rupees(v: Decimal) -> str:
        return f"Rs {money(v):,.2f}"

    # outstanding for a party
    m = re.search(r"(outstanding|due|balance)\s+(of|for)\s+(.+)", q)
    if m:
        name = m.group(3).strip(" ?.")
        party = (await db.execute(select(Party).where(Party.company_id == ctx.company_id, Party.name.ilike(f"%{name}%")).limit(1))).scalar_one_or_none()
        if party:
            kind = "payable" if party.party_type == "supplier" else "receivable"
            amt = await party_outstanding(db, ctx.company_id, party.id, kind)
            tools_used = ["findParty", "getOutstanding"]
            return {"answer": f"{party.name} has {rupees(amt)} {kind}.", "tools": tools_used, "data": {"party_id": party.id, "outstanding": amt}, "actions": [{"label": "Open customer", "href": f"/parties/{'suppliers' if kind == 'payable' else 'customers'}/{party.id}"}]}
    if "outstanding" in q or "receivable" in q or "who owes" in q or "collect" in q:
        r = await R.outstanding(db, ctx.company_id, "receivable", today)
        top = ", ".join(f"{p['party']} ({rupees(p['balance'])})" for p in r["by_party"][:5])
        return {"answer": f"Total receivables are {rupees(r['total'])}, of which {rupees(sum((v for k, v in r['ageing'].items() if k != 'current'), ZERO))} is overdue. Top: {top}.", "tools": ["getOutstanding"], "data": r["ageing"], "actions": [{"label": "Open outstanding", "href": "/accounting/outstanding"}]}
    if "payable" in q or "we owe" in q or "supplier" in q and "due" in q:
        r = await R.outstanding(db, ctx.company_id, "payable", today)
        return {"answer": f"Total payables are {rupees(r['total'])}.", "tools": ["getOutstanding"], "data": r["ageing"], "actions": [{"label": "Open payables", "href": "/accounting/outstanding?kind=payable"}]}
    if "sales" in q or "sold" in q or "revenue" in q:
        if "today" in q:
            a, b, label = today, today, "today"
        elif "yesterday" in q:
            a = b = today - timedelta(days=1)
            label = "yesterday"
        elif "week" in q:
            a, b, label = today - timedelta(days=6), today, "in the last 7 days"
        elif "year" in q:
            a, b, label = date(today.year if today.month >= 4 else today.year - 1, 4, 1), today, "this fiscal year"
        else:
            a, b, label = today.replace(day=1), today, "this month"
        r = (await db.execute(select(func.coalesce(func.sum(TradeDocument.grand_total), 0), func.count()).where(TradeDocument.company_id == ctx.company_id, TradeDocument.doc_type == "sales_invoice", TradeDocument.status == "posted", TradeDocument.date >= a, TradeDocument.date <= b))).one()
        return {"answer": f"Sales {label}: {rupees(Decimal(r[0]))} across {r[1]} invoices.", "tools": ["getSales"], "data": {"from": a, "to": b, "amount": money(Decimal(r[0])), "count": r[1]}, "actions": [{"label": "Open invoices", "href": "/sales/invoices"}]}
    if "dead stock" in q or "not moving" in q or "slow" in q:
        rows = await R.dead_stock(db, ctx.company_id, 90)
        val = sum((r["value"] for r in rows), ZERO)
        top = ", ".join(f"{r['name']} ({r['qty'].normalize()} {r['unit']})" for r in rows[:5])
        return {"answer": f"{len(rows)} products have not sold in 90 days, worth {rupees(val)}. Top: {top or 'none'}.", "tools": ["getDeadStock"], "data": {"count": len(rows), "value": val}, "actions": [{"label": "Dead stock report", "href": "/inventory/dead-stock"}]}
    if "low stock" in q or "reorder" in q or "out of stock" in q:
        rows = await stock_summary(db, ctx.company_id, low_only=True)
        names = ", ".join(f"{r['name']} ({r['qty'].normalize()} {r['unit']})" for r in rows[:6])
        return {"answer": f"{len(rows)} products are at or below reorder level: {names or 'none'}.", "tools": ["getStockSummary"], "data": {"count": len(rows)}, "actions": [{"label": "Stock summary", "href": "/inventory/stock"}]}
    m = re.search(r"stock\s+(of|for)\s+(.+)", q)
    if m:
        name = m.group(2).strip(" ?.")
        rows = await stock_summary(db, ctx.company_id, search=name)
        if rows:
            r = rows[0]
            area = f" (~{r['area_sqft'].normalize()} sqft)" if r.get("area_sqft") else ""
            return {"answer": f"{r['name']}: {r['qty'].normalize()} {r['unit']}{area} in stock, valued at {rupees(r['value'])}.", "tools": ["findProduct", "getStock"], "data": r, "actions": [{"label": "Open product", "href": f"/inventory/products/{r['product_id']}"}]}
        return {"answer": f"I could not find a product matching '{name}'.", "tools": ["findProduct"], "data": None, "actions": []}
    if "profit" in q or "margin" in q:
        pl = await R.profit_loss(db, ctx.company_id, today.replace(day=1), today)
        return {"answer": f"This month: income {rupees(pl['total_income'])}, expenses {rupees(pl['total_expense'])}, gross profit {rupees(pl['gross_profit'])}, net profit {rupees(pl['net_profit'])}.", "tools": ["getProfitLoss"], "data": pl, "actions": [{"label": "Open P&L", "href": "/accounting/reports/profit-loss"}]}
    if "cash" in q or "bank" in q:
        d = await R.dashboard(db, ctx.company_id)
        parts = ", ".join(f"{c['name']}: {rupees(c['balance'])}" for c in d["cash_bank"])
        return {"answer": f"Cash & bank balances - {parts}.", "tools": ["getLedgerBalances"], "data": d["cash_bank"], "actions": [{"label": "Ledgers", "href": "/accounting/ledgers"}]}
    if "top customer" in q or "best customer" in q:
        rows = (await db.execute(select(TradeDocument.party_name, func.sum(TradeDocument.grand_total)).where(TradeDocument.company_id == ctx.company_id, TradeDocument.doc_type == "sales_invoice", TradeDocument.status == "posted").group_by(TradeDocument.party_name).order_by(func.sum(TradeDocument.grand_total).desc()).limit(5))).all()
        return {"answer": "Top customers: " + ", ".join(f"{n} ({rupees(Decimal(a))})" for n, a in rows), "tools": ["getTopCustomers"], "data": [{"party": n, "amount": money(Decimal(a))} for n, a in rows], "actions": []}
    if "gst" in q or "tax" in q:
        g = await R.gst_summary(db, ctx.company_id, today.replace(day=1), today)
        return {"answer": f"GST this month - output tax {rupees(g['outward']['total_tax'])}, input credit {rupees(g['inward']['total_tax'])}, net payable {rupees(g['net_payable']['total'])}.", "tools": ["getGstSummary"], "data": g["net_payable"], "actions": [{"label": "GST summary", "href": "/gst"}]}
    return {
        "answer": "I can answer questions like: 'sales today', 'outstanding of Sharma Builders', 'stock of Carrara', 'low stock', 'dead stock', 'profit this month', 'cash balance', 'top customers', 'gst this month'. I only read data - I never post transactions.",
        "tools": [],
        "data": None,
        "actions": [],
    }


# ------------------------------------------------------------------ BI
@router.get("/bi/overview")
async def bi_overview(ctx: Ctx = Depends(require("reports.view")), db: AsyncSession = Depends(get_db)):
    today = date.today()
    start = today - timedelta(days=180)
    # monthly sales & purchase
    month_col = func.date_trunc("month", TradeDocument.date).label("m")
    rows = (await db.execute(select(month_col, TradeDocument.doc_type, func.sum(TradeDocument.grand_total)).where(TradeDocument.company_id == ctx.company_id, TradeDocument.status == "posted", TradeDocument.doc_type.in_(("sales_invoice", "purchase_bill")), TradeDocument.date >= start).group_by(month_col, TradeDocument.doc_type))).all()
    months: dict[str, dict] = {}
    for m, t, v in rows:
        key = m.strftime("%Y-%m")
        months.setdefault(key, {"month": key, "sales": ZERO, "purchase": ZERO})
        months[key]["sales" if t == "sales_invoice" else "purchase"] += Decimal(v)
    # customer scoring: revenue, invoices, avg days to pay (approx via overdue)
    cust = (await db.execute(select(TradeDocument.party_id, TradeDocument.party_name, func.sum(TradeDocument.grand_total), func.count()).where(TradeDocument.company_id == ctx.company_id, TradeDocument.status == "posted", TradeDocument.doc_type == "sales_invoice").group_by(TradeDocument.party_id, TradeDocument.party_name).order_by(func.sum(TradeDocument.grand_total).desc()).limit(10))).all()
    recv = await R.outstanding(db, ctx.company_id, "receivable", today)
    overdue_by_party = {p["party_id"]: p["overdue"] for p in recv["by_party"]}
    customers = []
    for pid, name, total, cnt in cust:
        total = Decimal(total)
        overdue = overdue_by_party.get(pid, ZERO)
        score = max(0, min(100, int(70 + min(total / Decimal("100000"), 20) - (overdue / total * 50 if total else 0))))
        customers.append({"party_id": pid, "party": name, "revenue": money(total), "invoices": cnt, "overdue": money(overdue), "score": score})
    # demand forecast per product: avg monthly qty last 90d * 1
    dem = (await db.execute(select(TradeLine.product_id, Product.name, func.sum(TradeLine.qty)).join(TradeDocument, TradeDocument.id == TradeLine.document_id).join(Product, Product.id == TradeLine.product_id).where(TradeDocument.company_id == ctx.company_id, TradeDocument.status == "posted", TradeDocument.doc_type == "sales_invoice", TradeDocument.date >= today - timedelta(days=90)).group_by(TradeLine.product_id, Product.name).order_by(func.sum(TradeLine.qty).desc()).limit(10))).all()
    stock = {s["product_id"]: s for s in await stock_summary(db, ctx.company_id)}
    forecast = []
    for pid, name, q in dem:
        monthly = (Decimal(q) / 3).quantize(Decimal("0.01"))
        onhand = stock.get(pid, {}).get("qty", ZERO)
        cover = (onhand / monthly * 30).quantize(Decimal("1")) if monthly else None
        forecast.append({"product_id": pid, "name": name, "sold_90d": Decimal(q), "forecast_monthly": monthly, "on_hand": onhand, "days_of_cover": cover, "suggest_reorder": bool(cover is not None and cover < 30)})
    # margin per product (sales vs cogs) last 90d
    margin_rows = (await db.execute(select(Product.name, func.sum(TradeLine.taxable_amount), func.sum(TradeLine.qty * TradeLine.cost_rate)).join(TradeDocument, TradeDocument.id == TradeLine.document_id).join(Product, Product.id == TradeLine.product_id).where(TradeDocument.company_id == ctx.company_id, TradeDocument.status == "posted", TradeDocument.doc_type == "sales_invoice", TradeDocument.date >= today - timedelta(days=90)).group_by(Product.name).order_by(func.sum(TradeLine.taxable_amount).desc()).limit(10))).all()
    margins = [{"name": n, "revenue": money(Decimal(r)), "cost": money(Decimal(c)), "margin": money(Decimal(r) - Decimal(c)), "margin_pct": (money((Decimal(r) - Decimal(c)) / Decimal(r) * 100) if Decimal(r) else ZERO)} for n, r, c in margin_rows]
    # cash-flow projection: receivables due next 30 days minus payables due
    def due_within(rep, days):
        return money(sum((r["balance"] for r in rep["rows"] if r["balance"] > 0 and r["due_date"] <= today + timedelta(days=days)), ZERO))

    pay = await R.outstanding(db, ctx.company_id, "payable", today)
    return {
        "monthly": sorted(({**v, "sales": money(v["sales"]), "purchase": money(v["purchase"])} for v in months.values()), key=lambda r: r["month"]),
        "customer_scores": customers,
        "demand_forecast": forecast,
        "margins": margins,
        "cashflow": {"inflow_30d": due_within(recv, 30), "outflow_30d": due_within(pay, 30), "inflow_60d": due_within(recv, 60), "outflow_60d": due_within(pay, 60)},
    }


# ------------------------------------------------------------------ TALLY export (XML, masters + vouchers)
@router.get("/tally/export")
async def tally_export(from_date: date | None = None, to_date: date | None = None, what: str = Query("vouchers", pattern="^(vouchers|ledgers)$"), ctx: Ctx = Depends(require("accounting.view")), db: AsyncSession = Depends(get_db)):
    company = await db.get(Company, ctx.company_id)
    to_date = to_date or date.today()
    from_date = from_date or to_date.replace(day=1)
    parts = [f'<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER><BODY><IMPORTDATA><REQUESTDESC><REPORTNAME>{"All Masters" if what == "ledgers" else "Vouchers"}</REPORTNAME><STATICVARIABLES><SVCURRENTCOMPANY>{escape(company.name)}</SVCURRENTCOMPANY></STATICVARIABLES></REQUESTDESC><REQUESTDATA>']
    if what == "ledgers":
        for l in (await db.execute(select(Ledger).where(Ledger.company_id == ctx.company_id))).scalars().all():
            ob = l.opening_balance if l.opening_type == "cr" else -l.opening_balance  # Tally: positive = credit
            parts.append(f'<TALLYMESSAGE xmlns:UDF="TallyUDF"><LEDGER NAME="{escape(l.name)}" ACTION="Create"><NAME.LIST><NAME>{escape(l.name)}</NAME></NAME.LIST><PARENT>{escape(l.group.name if l.group else "")}</PARENT><OPENINGBALANCE>{ob}</OPENINGBALANCE></LEDGER></TALLYMESSAGE>')
    else:
        vtype_map = {"sales": "Sales", "purchase": "Purchase", "receipt": "Receipt", "payment": "Payment", "contra": "Contra", "journal": "Journal", "credit_note": "Credit Note", "debit_note": "Debit Note"}
        vs = (await db.execute(select(Voucher).where(Voucher.company_id == ctx.company_id, Voucher.date >= from_date, Voucher.date <= to_date).order_by(Voucher.date))).scalars().all()
        for v in vs:
            lines = "".join(f'<ALLLEDGERENTRIES.LIST><LEDGERNAME>{escape(l.ledger.name)}</LEDGERNAME><ISDEEMEDPOSITIVE>{"Yes" if l.debit else "No"}</ISDEEMEDPOSITIVE><AMOUNT>{(-l.debit) if l.debit else l.credit}</AMOUNT></ALLLEDGERENTRIES.LIST>' for l in v.lines)
            parts.append(f'<TALLYMESSAGE xmlns:UDF="TallyUDF"><VOUCHER VCHTYPE="{vtype_map.get(v.voucher_type, "Journal")}" ACTION="Create"><DATE>{v.date.strftime("%Y%m%d")}</DATE><VOUCHERTYPENAME>{vtype_map.get(v.voucher_type, "Journal")}</VOUCHERTYPENAME><VOUCHERNUMBER>{escape(v.voucher_no)}</VOUCHERNUMBER><NARRATION>{escape(v.narration or "")}</NARRATION>{lines}</VOUCHER></TALLYMESSAGE>')
    parts.append("</REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>")
    await audit(db, ctx, "export", "tally", None, f"Tally {what} export {from_date}..{to_date}")
    await db.commit()
    return Response(content="".join(parts), media_type="application/xml", headers={"Content-Disposition": f'attachment; filename="tally_{what}_{from_date}_{to_date}.xml"'})
