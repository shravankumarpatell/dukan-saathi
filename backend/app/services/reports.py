"""Financial, inventory, GST and dashboard reports (all computed from posted vouchers / movements)."""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AccountGroup, Bill, BillSettlement, Ledger, Party, Product, StockMovement, TradeDocument, TradeLine, Voucher, VoucherLine
from .common import ZERO, money


def signed_opening(l: Ledger) -> Decimal:
    return l.opening_balance if l.opening_type == "dr" else -l.opening_balance


async def ledger_movements(db: AsyncSession, company_id: uuid.UUID, upto: date | None = None, from_: date | None = None) -> dict[uuid.UUID, tuple[Decimal, Decimal]]:
    stmt = select(VoucherLine.ledger_id, func.coalesce(func.sum(VoucherLine.debit), 0), func.coalesce(func.sum(VoucherLine.credit), 0)).join(Voucher, Voucher.id == VoucherLine.voucher_id).where(Voucher.company_id == company_id)
    if upto:
        stmt = stmt.where(Voucher.date <= upto)
    if from_:
        stmt = stmt.where(Voucher.date >= from_)
    stmt = stmt.group_by(VoucherLine.ledger_id)
    return {r[0]: (Decimal(r[1]), Decimal(r[2])) for r in (await db.execute(stmt)).all()}


async def all_ledgers(db: AsyncSession, company_id: uuid.UUID) -> list[Ledger]:
    return list((await db.execute(select(Ledger).where(Ledger.company_id == company_id).order_by(Ledger.name))).scalars().all())


async def all_groups(db: AsyncSession, company_id: uuid.UUID) -> dict[uuid.UUID, AccountGroup]:
    return {g.id: g for g in (await db.execute(select(AccountGroup).where(AccountGroup.company_id == company_id))).scalars().all()}


def group_path(groups: dict[uuid.UUID, AccountGroup], gid: uuid.UUID) -> list[str]:
    path = []
    g = groups.get(gid)
    while g:
        path.insert(0, g.name)
        g = groups.get(g.parent_id) if g.parent_id else None
    return path


async def trial_balance(db: AsyncSession, company_id: uuid.UUID, from_: date, to: date) -> dict:
    ledgers = await all_ledgers(db, company_id)
    groups = await all_groups(db, company_id)
    before = await ledger_movements(db, company_id, upto=from_ - timedelta(days=1))
    period = await ledger_movements(db, company_id, upto=to, from_=from_)
    rows = []
    tot_open_dr = tot_open_cr = tot_dr = tot_cr = tot_close_dr = tot_close_cr = ZERO
    for l in ledgers:
        bd, bc = before.get(l.id, (ZERO, ZERO))
        pd, pc = period.get(l.id, (ZERO, ZERO))
        opening = signed_opening(l) + bd - bc
        closing = opening + pd - pc
        if opening == ZERO and pd == ZERO and pc == ZERO and closing == ZERO:
            continue
        rows.append(
            {
                "ledger_id": l.id,
                "ledger": l.name,
                "group": groups[l.group_id].name if l.group_id in groups else None,
                "group_path": " > ".join(group_path(groups, l.group_id)),
                "nature": groups[l.group_id].nature if l.group_id in groups else None,
                "opening_dr": money(opening) if opening > 0 else ZERO,
                "opening_cr": money(-opening) if opening < 0 else ZERO,
                "debit": money(pd),
                "credit": money(pc),
                "closing_dr": money(closing) if closing > 0 else ZERO,
                "closing_cr": money(-closing) if closing < 0 else ZERO,
            }
        )
        tot_open_dr += rows[-1]["opening_dr"]
        tot_open_cr += rows[-1]["opening_cr"]
        tot_dr += money(pd)
        tot_cr += money(pc)
        tot_close_dr += rows[-1]["closing_dr"]
        tot_close_cr += rows[-1]["closing_cr"]
    rows.sort(key=lambda r: (r["group_path"], r["ledger"]))
    return {
        "from": from_,
        "to": to,
        "rows": rows,
        "totals": {"opening_dr": money(tot_open_dr), "opening_cr": money(tot_open_cr), "debit": money(tot_dr), "credit": money(tot_cr), "closing_dr": money(tot_close_dr), "closing_cr": money(tot_close_cr)},
        "balanced": money(tot_close_dr) == money(tot_close_cr) and money(tot_dr) == money(tot_cr),
    }


async def profit_loss(db: AsyncSession, company_id: uuid.UUID, from_: date, to: date) -> dict:
    ledgers = await all_ledgers(db, company_id)
    groups = await all_groups(db, company_id)
    period = await ledger_movements(db, company_id, upto=to, from_=from_)
    income, expense = [], []
    gross_income = gross_expense = ZERO
    tot_income = tot_expense = ZERO
    for l in ledgers:
        g = groups.get(l.group_id)
        if not g or g.report != "profit_loss":
            continue
        pd, pc = period.get(l.id, (ZERO, ZERO))
        if pd == ZERO and pc == ZERO:
            continue
        if g.nature == "income":
            amt = money(pc - pd)
            income.append({"ledger_id": l.id, "ledger": l.name, "group": g.name, "amount": amt, "gross": g.affects_gross_profit})
            tot_income += amt
            if g.affects_gross_profit:
                gross_income += amt
        else:
            amt = money(pd - pc)
            expense.append({"ledger_id": l.id, "ledger": l.name, "group": g.name, "amount": amt, "gross": g.affects_gross_profit})
            tot_expense += amt
            if g.affects_gross_profit:
                gross_expense += amt
    income.sort(key=lambda r: (not r["gross"], r["group"], r["ledger"]))
    expense.sort(key=lambda r: (not r["gross"], r["group"], r["ledger"]))
    return {
        "from": from_,
        "to": to,
        "income": income,
        "expense": expense,
        "total_income": money(tot_income),
        "total_expense": money(tot_expense),
        "gross_profit": money(gross_income - gross_expense),
        "net_profit": money(tot_income - tot_expense),
    }


async def balance_sheet(db: AsyncSession, company_id: uuid.UUID, as_of: date) -> dict:
    ledgers = await all_ledgers(db, company_id)
    groups = await all_groups(db, company_id)
    upto = await ledger_movements(db, company_id, upto=as_of)
    assets, liabilities, equity = [], [], []
    ta = tl = te = ZERO
    pl_net = ZERO
    for l in ledgers:
        g = groups.get(l.group_id)
        if not g:
            continue
        d, c = upto.get(l.id, (ZERO, ZERO))
        bal = signed_opening(l) + d - c
        if g.report == "profit_loss":
            pl_net += -bal  # credit balance = profit
            continue
        if bal == ZERO:
            continue
        row = {"ledger_id": l.id, "ledger": l.name, "group": g.name, "amount": money(abs(bal)), "side": "dr" if bal > 0 else "cr"}
        if g.nature == "asset":
            assets.append({**row, "amount": money(bal)})
            ta += bal
        elif g.nature == "liability":
            liabilities.append({**row, "amount": money(-bal)})
            tl += -bal
        else:
            equity.append({**row, "amount": money(-bal)})
            te += -bal
    for lst in (assets, liabilities, equity):
        lst.sort(key=lambda r: (r["group"], r["ledger"]))
    equity.append({"ledger_id": None, "ledger": "Profit & Loss (accumulated)", "group": "Reserves & Surplus", "amount": money(pl_net), "side": "cr"})
    te += pl_net
    return {
        "as_of": as_of,
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "total_assets": money(ta),
        "total_liabilities": money(tl),
        "total_equity": money(te),
        "total_liabilities_equity": money(tl + te),
        "balanced": money(ta) == money(tl + te),
    }


async def ledger_statement(db: AsyncSession, company_id: uuid.UUID, ledger_id: uuid.UUID, from_: date, to: date) -> dict:
    ledger = await db.get(Ledger, ledger_id)
    if not ledger or ledger.company_id != company_id:
        return {"rows": [], "opening": ZERO}
    before = await ledger_movements(db, company_id, upto=from_ - timedelta(days=1))
    bd, bc = before.get(ledger.id, (ZERO, ZERO))
    opening = signed_opening(ledger) + bd - bc
    stmt = (
        select(VoucherLine, Voucher)
        .join(Voucher, Voucher.id == VoucherLine.voucher_id)
        .where(Voucher.company_id == company_id, VoucherLine.ledger_id == ledger_id, Voucher.date >= from_, Voucher.date <= to)
        .order_by(Voucher.date, Voucher.posted_at, VoucherLine.line_no)
    )
    rows = []
    running = opening
    tot_dr = tot_cr = ZERO
    for line, v in (await db.execute(stmt)).all():
        running += line.debit - line.credit
        tot_dr += line.debit
        tot_cr += line.credit
        # counter ledgers (other side of the entry)
        others = [ol.ledger.name for ol in v.lines if ol.ledger_id != ledger_id]
        rows.append(
            {
                "voucher_id": v.id,
                "date": v.date,
                "voucher_type": v.voucher_type,
                "voucher_no": v.voucher_no,
                "narration": line.narration or v.narration,
                "particulars": ", ".join(dict.fromkeys(others))[:120],
                "debit": line.debit,
                "credit": line.credit,
                "balance": money(abs(running)),
                "balance_type": "dr" if running >= 0 else "cr",
                "status": v.status,
                "reference_type": v.reference_type,
                "reference_id": v.reference_id,
            }
        )
    return {
        "ledger": {"id": ledger.id, "name": ledger.name, "group": ledger.group.name if ledger.group else None},
        "from": from_,
        "to": to,
        "opening": money(abs(opening)),
        "opening_type": "dr" if opening >= 0 else "cr",
        "rows": rows,
        "total_debit": money(tot_dr),
        "total_credit": money(tot_cr),
        "closing": money(abs(running)),
        "closing_type": "dr" if running >= 0 else "cr",
    }


async def day_book(db: AsyncSession, company_id: uuid.UUID, from_: date, to: date, voucher_type: str | None = None) -> list[dict]:
    stmt = select(Voucher).where(Voucher.company_id == company_id, Voucher.date >= from_, Voucher.date <= to)
    if voucher_type:
        stmt = stmt.where(Voucher.voucher_type == voucher_type)
    stmt = stmt.order_by(Voucher.date.desc(), Voucher.posted_at.desc())
    out = []
    for v in (await db.execute(stmt)).scalars().all():
        dr = [l for l in v.lines if l.debit]
        cr = [l for l in v.lines if l.credit]
        out.append(
            {
                "id": v.id,
                "date": v.date,
                "voucher_type": v.voucher_type,
                "voucher_no": v.voucher_no,
                "narration": v.narration,
                "debit_ledgers": ", ".join(dict.fromkeys(l.ledger.name for l in dr)),
                "credit_ledgers": ", ".join(dict.fromkeys(l.ledger.name for l in cr)),
                "amount": v.total_debit,
                "status": v.status,
                "reference_type": v.reference_type,
                "reference_id": v.reference_id,
            }
        )
    return out


async def outstanding(db: AsyncSession, company_id: uuid.UUID, kind: str, as_of: date | None = None, party_id: uuid.UUID | None = None) -> dict:
    as_of = as_of or date.today()
    stmt = select(Bill, Party.name).join(Party, Party.id == Bill.party_id).where(Bill.company_id == company_id, Bill.kind == kind, Bill.bill_date <= as_of)
    if party_id:
        stmt = stmt.where(Bill.party_id == party_id)
    stmt = stmt.order_by(Party.name, Bill.bill_date)
    rows = []
    buckets = {"current": ZERO, "1_30": ZERO, "31_60": ZERO, "61_90": ZERO, "90_plus": ZERO}
    total = ZERO
    by_party: dict[uuid.UUID, dict] = {}
    for b, pname in (await db.execute(stmt)).all():
        settled = sum((s.amount for s in b.settlements if s.date <= as_of), ZERO)
        bal = money(b.amount - settled)
        if bal == ZERO:
            continue
        overdue_days = (as_of - b.due_date).days
        if bal > 0:
            bucket = "current" if overdue_days <= 0 else "1_30" if overdue_days <= 30 else "31_60" if overdue_days <= 60 else "61_90" if overdue_days <= 90 else "90_plus"
            buckets[bucket] += bal
        total += bal
        rows.append({"bill_id": b.id, "party_id": b.party_id, "party": pname, "bill_no": b.bill_no, "bill_date": b.bill_date, "due_date": b.due_date, "amount": b.amount, "balance": bal, "overdue_days": max(overdue_days, 0) if bal > 0 else 0, "doc_type": b.doc_type, "doc_id": b.doc_id})
        p = by_party.setdefault(b.party_id, {"party_id": b.party_id, "party": pname, "balance": ZERO, "overdue": ZERO, "bills": 0})
        p["balance"] += bal
        p["bills"] += 1
        if bal > 0 and overdue_days > 0:
            p["overdue"] += bal
    return {"kind": kind, "as_of": as_of, "rows": rows, "by_party": sorted(by_party.values(), key=lambda p: -p["balance"]), "total": money(total), "ageing": {k: money(v) for k, v in buckets.items()}}


async def stock_ledger(db: AsyncSession, company_id: uuid.UUID, product_id: uuid.UUID, from_: date | None, to: date | None, godown_id: uuid.UUID | None = None) -> dict:
    base = select(StockMovement).where(StockMovement.company_id == company_id, StockMovement.product_id == product_id)
    if godown_id:
        base = base.where(StockMovement.godown_id == godown_id)
    opening = ZERO
    if from_:
        opening = Decimal((await db.execute(select(func.coalesce(func.sum(StockMovement.qty), 0)).where(StockMovement.company_id == company_id, StockMovement.product_id == product_id, StockMovement.date < from_, *( [StockMovement.godown_id == godown_id] if godown_id else [])))).scalar_one())
        base = base.where(StockMovement.date >= from_)
    if to:
        base = base.where(StockMovement.date <= to)
    rows = []
    running = opening
    for m in (await db.execute(base.order_by(StockMovement.date, StockMovement.created_at))).scalars().all():
        running += m.qty
        rows.append({"id": m.id, "date": m.date, "movement_type": m.movement_type, "qty_in": m.qty if m.qty > 0 else ZERO, "qty_out": -m.qty if m.qty < 0 else ZERO, "rate": m.rate, "value": m.value, "balance": running, "godown_id": m.godown_id, "batch_id": m.batch_id, "doc_type": m.doc_type, "doc_id": m.doc_id, "narration": m.narration})
    return {"opening": opening, "rows": rows, "closing": running}


async def gst_summary(db: AsyncSession, company_id: uuid.UUID, from_: date, to: date) -> dict:
    def _agg(doc_types: tuple[str, ...]):
        return (
            select(TradeDocument, TradeLine)
            .join(TradeLine, TradeLine.document_id == TradeDocument.id)
            .where(TradeDocument.company_id == company_id, TradeDocument.status == "posted", TradeDocument.doc_type.in_(doc_types), TradeDocument.date >= from_, TradeDocument.date <= to)
        )

    out_rows = (await db.execute(_agg(("sales_invoice", "sales_return")))).all()
    in_rows = (await db.execute(_agg(("purchase_bill", "purchase_return")))).all()

    def summarize(rows, negative_types):
        by_rate: dict[str, dict] = {}
        by_hsn: dict[str, dict] = {}
        b2b = b2c = ZERO
        taxable = cgst = sgst = igst = ZERO
        docs = set()
        for d, l in rows:
            sign = -1 if d.doc_type in negative_types else 1
            docs.add(d.id)
            r = by_rate.setdefault(str(l.gst_rate.normalize()), {"gst_rate": l.gst_rate, "taxable": ZERO, "cgst": ZERO, "sgst": ZERO, "igst": ZERO})
            h = by_hsn.setdefault(l.hsn_code or "-", {"hsn": l.hsn_code or "-", "qty": ZERO, "taxable": ZERO, "cgst": ZERO, "sgst": ZERO, "igst": ZERO})
            for tgt in (r, h):
                tgt["taxable"] += sign * l.taxable_amount
                tgt["cgst"] += sign * l.cgst
                tgt["sgst"] += sign * l.sgst
                tgt["igst"] += sign * l.igst
            h["qty"] += sign * l.qty
            taxable += sign * l.taxable_amount
            cgst += sign * l.cgst
            sgst += sign * l.sgst
            igst += sign * l.igst
            if d.party_gstin:
                b2b += sign * l.total
            else:
                b2c += sign * l.total
        return {
            "documents": len(docs),
            "taxable": money(taxable),
            "cgst": money(cgst),
            "sgst": money(sgst),
            "igst": money(igst),
            "total_tax": money(cgst + sgst + igst),
            "b2b_total": money(b2b),
            "b2c_total": money(b2c),
            "by_rate": sorted(({**v, "taxable": money(v["taxable"]), "cgst": money(v["cgst"]), "sgst": money(v["sgst"]), "igst": money(v["igst"])} for v in by_rate.values()), key=lambda r: r["gst_rate"]),
            "by_hsn": sorted(({**v, "taxable": money(v["taxable"]), "cgst": money(v["cgst"]), "sgst": money(v["sgst"]), "igst": money(v["igst"])} for v in by_hsn.values()), key=lambda r: r["hsn"]),
        }

    outward = summarize(out_rows, ("sales_return",))
    inward = summarize(in_rows, ("purchase_return",))
    net = {k: money(outward[k] - inward[k]) for k in ("cgst", "sgst", "igst")}
    net["total"] = money(sum(net.values(), ZERO))
    return {"from": from_, "to": to, "outward": outward, "inward": inward, "net_payable": net}


async def dead_stock(db: AsyncSession, company_id: uuid.UUID, days: int = 90) -> list[dict]:
    cutoff = date.today() - timedelta(days=days)
    last_sale = (
        select(StockMovement.product_id, func.max(StockMovement.date).label("last_sale"))
        .where(StockMovement.company_id == company_id, StockMovement.movement_type == "sales_invoice")
        .group_by(StockMovement.product_id)
        .subquery()
    )
    agg = select(StockMovement.product_id, func.coalesce(func.sum(StockMovement.qty), 0).label("qty"), func.coalesce(func.sum(StockMovement.value), 0).label("value")).where(StockMovement.company_id == company_id).group_by(StockMovement.product_id).subquery()
    stmt = (
        select(Product, func.coalesce(agg.c.qty, 0), func.coalesce(agg.c.value, 0), last_sale.c.last_sale)
        .outerjoin(agg, agg.c.product_id == Product.id)
        .outerjoin(last_sale, last_sale.c.product_id == Product.id)
        .where(Product.company_id == company_id, Product.is_active.is_(True))
    )
    out = []
    for p, q, v, ls in (await db.execute(stmt)).all():
        q = Decimal(q)
        if q <= ZERO:
            continue
        if ls is None or ls < cutoff:
            out.append({"product_id": p.id, "sku": p.sku, "name": p.name, "brand": p.brand.name if p.brand else None, "qty": q, "unit": p.stock_unit.symbol, "value": money(Decimal(v)), "last_sale": ls, "idle_days": (date.today() - ls).days if ls else None})
    out.sort(key=lambda r: -r["value"])
    return out


async def dashboard(db: AsyncSession, company_id: uuid.UUID) -> dict:
    today = date.today()
    month_start = today.replace(day=1)
    fy_start = date(today.year if today.month >= 4 else today.year - 1, 4, 1)

    async def sales_between(a: date, b: date, doc_type: str = "sales_invoice") -> tuple[Decimal, int]:
        r = (await db.execute(select(func.coalesce(func.sum(TradeDocument.grand_total), 0), func.count()).where(TradeDocument.company_id == company_id, TradeDocument.doc_type == doc_type, TradeDocument.status == "posted", TradeDocument.date >= a, TradeDocument.date <= b))).one()
        return money(Decimal(r[0])), int(r[1])

    sales_today, count_today = await sales_between(today, today)
    sales_month, count_month = await sales_between(month_start, today)
    sales_fy, _ = await sales_between(fy_start, today)
    purchase_month, _ = await sales_between(month_start, today, "purchase_bill")

    recv = await outstanding(db, company_id, "receivable", today)
    pay = await outstanding(db, company_id, "payable", today)

    # cash & bank
    ledgers = await all_ledgers(db, company_id)
    mv = await ledger_movements(db, company_id, upto=today)
    cash_bank = []
    for l in ledgers:
        if l.is_cash or l.is_bank:
            d, c = mv.get(l.id, (ZERO, ZERO))
            cash_bank.append({"ledger_id": l.id, "name": l.name, "balance": money(signed_opening(l) + d - c), "is_bank": l.is_bank})

    # 30-day trend
    trend_rows = (
        await db.execute(
            select(TradeDocument.date, func.sum(TradeDocument.grand_total)).where(TradeDocument.company_id == company_id, TradeDocument.doc_type == "sales_invoice", TradeDocument.status == "posted", TradeDocument.date >= today - timedelta(days=29)).group_by(TradeDocument.date)
        )
    ).all()
    by_day = {d: Decimal(v) for d, v in trend_rows}
    trend = [{"date": (today - timedelta(days=i)), "amount": money(by_day.get(today - timedelta(days=i), ZERO))} for i in range(29, -1, -1)]

    # low stock
    from .stock import stock_summary

    summary = await stock_summary(db, company_id)
    low = [s for s in summary if s["status"] in ("low", "out")]
    stock_value = money(sum((s["value"] for s in summary), ZERO))

    # top products this month
    top_rows = (
        await db.execute(
            select(TradeLine.product_id, Product.name, func.sum(TradeLine.qty), func.sum(TradeLine.taxable_amount))
            .join(TradeDocument, TradeDocument.id == TradeLine.document_id)
            .join(Product, Product.id == TradeLine.product_id)
            .where(TradeDocument.company_id == company_id, TradeDocument.doc_type == "sales_invoice", TradeDocument.status == "posted", TradeDocument.date >= month_start)
            .group_by(TradeLine.product_id, Product.name)
            .order_by(func.sum(TradeLine.taxable_amount).desc())
            .limit(5)
        )
    ).all()
    recent = (await db.execute(select(TradeDocument).where(TradeDocument.company_id == company_id, TradeDocument.doc_type.in_(("sales_invoice", "purchase_bill", "quotation"))).order_by(TradeDocument.created_at.desc()).limit(8))).scalars().all()
    pl = await profit_loss(db, company_id, month_start, today)
    return {
        "date": today,
        "sales_today": sales_today,
        "invoices_today": count_today,
        "sales_month": sales_month,
        "invoices_month": count_month,
        "sales_fy": sales_fy,
        "purchase_month": purchase_month,
        "receivables": recv["total"],
        "receivables_overdue": money(sum((v for k, v in recv["ageing"].items() if k != "current"), ZERO)),
        "payables": pay["total"],
        "payables_overdue": money(sum((v for k, v in pay["ageing"].items() if k != "current"), ZERO)),
        "cash_bank": cash_bank,
        "stock_value": stock_value,
        "low_stock_count": len(low),
        "low_stock": low[:6],
        "trend": trend,
        "top_products": [{"product_id": pid, "name": n, "qty": q, "amount": money(Decimal(a))} for pid, n, q, a in top_rows],
        "recent_documents": [{"id": d.id, "doc_type": d.doc_type, "doc_no": d.doc_no, "date": d.date, "party_name": d.party_name, "grand_total": d.grand_total, "status": d.status} for d in recent],
        "gross_profit_month": pl["gross_profit"],
        "net_profit_month": pl["net_profit"],
        "top_debtors": recv["by_party"][:5],
    }
