"""Trade documents: quotations, orders, challans, invoices, returns, POs, GRNs, bills.

Effect chain on posting (per PRD Section 7):
  INPUT -> VALIDATION -> ACCOUNTING -> INVENTORY -> TAX -> OUTSTANDING -> AUDIT
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Ctx
from ..models import PURCHASE_DOC_TYPES, SALES_DOC_TYPES, Bill, BillSettlement, Company, Ledger, Party, Product, TradeDocument, TradeLine, Voucher
from ..schemas import TradeDocIn
from . import stock as stock_svc
from .common import ZERO, assert_period_open, audit, get_fiscal_year, money, next_number, now, qty
from .gst import compute_line, compute_totals
from .posting import LineSpec, allocate, get_system_ledger, post_voucher, reverse_voucher

ACCOUNTING_TYPES = {"sales_invoice", "sales_return", "purchase_bill", "purchase_return"}
STOCK_OUT_TYPES = {"sales_invoice", "purchase_return"}
STOCK_IN_TYPES = {"purchase_bill", "sales_return"}
CONVERSIONS = {
    "quotation": ["sales_order", "sales_invoice"],
    "sales_order": ["delivery_challan", "sales_invoice"],
    "delivery_challan": ["sales_invoice"],
    "sales_invoice": ["sales_return"],
    "purchase_order": ["grn", "purchase_bill"],
    "grn": ["purchase_bill"],
    "purchase_bill": ["purchase_return"],
}


def is_sales(doc_type: str) -> bool:
    return doc_type in SALES_DOC_TYPES


async def _party_ledger(db: AsyncSession, party: Party) -> Ledger:
    if party.ledger_id:
        led = await db.get(Ledger, party.ledger_id)
        if led:
            return led
    raise HTTPException(422, f"Party {party.name} has no ledger. Re-save the party.")


def _price_for(product: Product, party: Party, doc_type: str) -> Decimal:
    if not is_sales(doc_type):
        return product.purchase_price
    if party.price_tier == "dealer" and product.dealer_price > ZERO:
        return product.dealer_price
    if party.price_tier == "project" and product.project_price > ZERO:
        return product.project_price
    if product.retail_price > ZERO and party.price_tier == "retail":
        return product.retail_price
    return product.sale_price


async def build_document(db: AsyncSession, ctx: Ctx, doc_type: str, data: TradeDocIn, doc: TradeDocument | None = None) -> TradeDocument:
    """Create or update a DRAFT document with computed GST + totals."""
    if doc_type not in SALES_DOC_TYPES + PURCHASE_DOC_TYPES:
        raise HTTPException(400, f"Unknown document type {doc_type}")
    company = await db.get(Company, ctx.company_id)
    party = await db.get(Party, data.party_id)
    if not party or party.company_id != ctx.company_id:
        raise HTTPException(422, "Party not found")
    if is_sales(doc_type) and party.party_type == "supplier":
        raise HTTPException(422, "Selected party is a supplier; choose a customer")
    if not is_sales(doc_type) and party.party_type == "customer":
        raise HTTPException(422, "Selected party is a customer; choose a supplier")
    pos = data.place_of_supply or party.state_code
    interstate = pos != company.state_code
    godown_id = data.godown_id or (await stock_svc.default_godown(db, ctx.company_id, ctx.branch_id)).id

    if doc is None:
        fy = await get_fiscal_year(db, ctx.company_id, data.date)
        doc = TradeDocument(tenant_id=ctx.tenant_id, company_id=ctx.company_id, branch_id=ctx.branch_id, doc_type=doc_type, doc_no=await next_number(db, ctx.tenant_id, ctx.company_id, doc_type, fy), created_by=ctx.user_id, status="draft", idempotency_key=data.idempotency_key, lines=[])
        db.add(doc)
    elif doc.status != "draft":
        raise HTTPException(422, "Only draft documents can be edited. Cancel and re-create, or issue a return/credit note.")
    else:
        await db.refresh(doc, ["lines"])
        doc.lines.clear()
        await db.flush()

    doc.date = data.date
    doc.due_date = data.due_date or (data.date + timedelta(days=party.credit_days) if doc_type in ("sales_invoice", "purchase_bill") else None)
    doc.valid_till = data.valid_till
    doc.party_id = party.id
    doc.party_name = party.name
    doc.party_gstin = party.gstin
    doc.party_state_code = party.state_code
    doc.place_of_supply = pos
    doc.is_interstate = interstate
    doc.godown_id = godown_id
    doc.project_id = data.project_id
    doc.reference_doc_id = data.reference_doc_id
    doc.supplier_ref_no = data.supplier_ref_no
    doc.notes, doc.terms, doc.salesman = data.notes, data.terms, data.salesman
    doc.transporter, doc.vehicle_no, doc.eway_bill_no = data.transporter, data.vehicle_no, data.eway_bill_no
    doc.paid_amount = money(data.paid_amount)
    doc.payment_ledger_id = data.payment_ledger_id

    computed = []
    for i, l in enumerate(data.lines, start=1):
        product = await db.get(Product, l.product_id)
        if not product or product.company_id != ctx.company_id:
            raise HTTPException(422, f"Product on line {i} not found")
        rate = l.rate if l.rate is not None else _price_for(product, party, doc_type)
        gst_rate = l.gst_rate if l.gst_rate is not None else product.gst_rate
        c = compute_line(qty(l.qty), rate, l.discount_pct, gst_rate, interstate)
        computed.append(c)
        area = l.area_sqft if l.area_sqft is not None else (qty(l.qty * product.sqft_per_box) if product.sqft_per_box else None)
        doc.lines.append(
            TradeLine(
                tenant_id=ctx.tenant_id,
                line_no=i,
                product_id=product.id,
                description=l.description or product.name,
                hsn_code=l.hsn_code or product.hsn_code,
                batch_id=l.batch_id,
                godown_id=l.godown_id or godown_id,
                qty=qty(l.qty),
                unit_symbol=l.unit_symbol or product.stock_unit.symbol,
                area_sqft=area,
                rate=rate,
                discount_pct=l.discount_pct,
                discount_amount=c["discount_amount"],
                taxable_amount=c["taxable_amount"],
                gst_rate=gst_rate,
                cgst=c["cgst"],
                sgst=c["sgst"],
                igst=c["igst"],
                total=c["total"],
            )
        )
    totals = compute_totals(computed, data.round_off_enabled)
    for k, v in totals.items():
        setattr(doc, k, v)
    if doc.paid_amount > doc.grand_total:
        raise HTTPException(422, "Paid amount cannot exceed grand total")
    if doc.paid_amount > ZERO and not doc.payment_ledger_id:
        raise HTTPException(422, "Select a cash/bank ledger for the received/paid amount")
    await db.flush()
    return doc


async def post_document(db: AsyncSession, ctx: Ctx, doc: TradeDocument) -> TradeDocument:
    if doc.company_id != ctx.company_id:
        raise HTTPException(404, "Document not found")
    if doc.status != "draft":
        raise HTTPException(422, f"Document is already {doc.status}")
    party = await db.get(Party, doc.party_id)
    if doc.doc_type not in ACCOUNTING_TYPES:
        doc.status = "posted"
        doc.posted_at = now()
        await audit(db, ctx, "confirm", doc.doc_type, doc.id, f"{doc.doc_no} confirmed for {doc.party_name} {doc.grand_total}")
        return doc

    await assert_period_open(db, ctx.company_id, doc.date)
    if party.credit_limit > ZERO and doc.doc_type == "sales_invoice":
        outstanding = await party_outstanding(db, ctx.company_id, party.id, "receivable")
        if outstanding + doc.grand_total - doc.paid_amount > party.credit_limit:
            raise HTTPException(422, f"Credit limit exceeded for {party.name}: outstanding {outstanding} + {doc.grand_total - doc.paid_amount} > limit {party.credit_limit}")

    party_ledger = await _party_ledger(db, party)
    sk = lambda k: get_system_ledger(db, ctx.company_id, k)  # noqa: E731
    tax_prefix = "output" if is_sales(doc.doc_type) else "input"
    tax_ledgers = {"cgst": await sk(f"{tax_prefix}_cgst"), "sgst": await sk(f"{tax_prefix}_sgst"), "igst": await sk(f"{tax_prefix}_igst")}
    round_led = await sk("round_off")
    inventory_led = await sk("inventory")

    # ---------------- INVENTORY EFFECT (also fixes cost rates for COGS)
    cost_total = ZERO
    for line in doc.lines:
        product = await db.get(Product, line.product_id)
        if doc.doc_type in STOCK_OUT_TYPES:
            if doc.doc_type == "sales_invoice":
                cost = await stock_svc.avg_cost(db, ctx.company_id, product.id)
            else:  # purchase return: cost = the purchase rate net of discount
                cost = (line.taxable_amount / line.qty).quantize(Decimal("0.0001")) if line.qty else ZERO
            line.cost_rate = cost
            await stock_svc.add_movement(db, ctx, product=product, godown_id=line.godown_id or doc.godown_id, on=doc.date, movement_type=doc.doc_type, quantity=-line.qty, rate=cost, batch_id=line.batch_id, doc_type=doc.doc_type, doc_id=doc.id, narration=f"{doc.doc_no} {doc.party_name}")
            cost_total += money(line.qty * cost)
        elif doc.doc_type in STOCK_IN_TYPES:
            if doc.doc_type == "purchase_bill":
                cost = (line.taxable_amount / line.qty).quantize(Decimal("0.0001")) if line.qty else ZERO
            else:  # sales return: bring back at original cost if reference known, else avg
                cost = await _reference_cost(db, doc, line) or await stock_svc.avg_cost(db, ctx.company_id, product.id)
            line.cost_rate = cost
            await stock_svc.add_movement(db, ctx, product=product, godown_id=line.godown_id or doc.godown_id, on=doc.date, movement_type=doc.doc_type, quantity=line.qty, rate=cost, batch_id=line.batch_id, doc_type=doc.doc_type, doc_id=doc.id, narration=f"{doc.doc_no} {doc.party_name}")
            cost_total += money(line.qty * cost)

    # ---------------- ACCOUNTING + TAX EFFECT
    lines: list[LineSpec] = []
    if doc.doc_type == "sales_invoice":
        sales_led = await sk("sales")
        lines.append(LineSpec(party_ledger.id, debit=doc.grand_total, narration=doc.doc_no))
        lines.append(LineSpec(sales_led.id, credit=doc.taxable_total))
        for k in ("cgst", "sgst", "igst"):
            amt = getattr(doc, f"{k}_total")
            if amt:
                lines.append(LineSpec(tax_ledgers[k].id, credit=amt))
        if doc.round_off > ZERO:
            lines.append(LineSpec(round_led.id, credit=doc.round_off))
        elif doc.round_off < ZERO:
            lines.append(LineSpec(round_led.id, debit=-doc.round_off))
        vtype, ntype, bill_kind, bill_sign = "sales", "sales", "receivable", 1
    elif doc.doc_type == "sales_return":
        ret_led = await sk("sales_return")
        lines.append(LineSpec(ret_led.id, debit=doc.taxable_total))
        for k in ("cgst", "sgst", "igst"):
            amt = getattr(doc, f"{k}_total")
            if amt:
                lines.append(LineSpec(tax_ledgers[k].id, debit=amt))
        lines.append(LineSpec(party_ledger.id, credit=doc.grand_total, narration=doc.doc_no))
        if doc.round_off > ZERO:
            lines.append(LineSpec(round_led.id, debit=doc.round_off))
        elif doc.round_off < ZERO:
            lines.append(LineSpec(round_led.id, credit=-doc.round_off))
        vtype, ntype, bill_kind, bill_sign = "credit_note", "credit_note", "receivable", -1
    elif doc.doc_type == "purchase_bill":
        lines.append(LineSpec(inventory_led.id, debit=doc.taxable_total, narration=doc.doc_no))
        for k in ("cgst", "sgst", "igst"):
            amt = getattr(doc, f"{k}_total")
            if amt:
                lines.append(LineSpec(tax_ledgers[k].id, debit=amt))
        lines.append(LineSpec(party_ledger.id, credit=doc.grand_total, narration=doc.supplier_ref_no or doc.doc_no))
        if doc.round_off > ZERO:
            lines.append(LineSpec(round_led.id, debit=doc.round_off))
        elif doc.round_off < ZERO:
            lines.append(LineSpec(round_led.id, credit=-doc.round_off))
        vtype, ntype, bill_kind, bill_sign = "purchase", "purchase", "payable", 1
    else:  # purchase_return
        lines.append(LineSpec(party_ledger.id, debit=doc.grand_total, narration=doc.doc_no))
        lines.append(LineSpec(inventory_led.id, credit=doc.taxable_total))
        for k in ("cgst", "sgst", "igst"):
            amt = getattr(doc, f"{k}_total")
            if amt:
                lines.append(LineSpec(tax_ledgers[k].id, credit=amt))
        if doc.round_off > ZERO:
            lines.append(LineSpec(round_led.id, credit=doc.round_off))
        elif doc.round_off < ZERO:
            lines.append(LineSpec(round_led.id, debit=-doc.round_off))
        vtype, ntype, bill_kind, bill_sign = "debit_note", "debit_note", "payable", -1

    voucher = await post_voucher(db, ctx, voucher_type=vtype, on=doc.date, lines=lines, narration=f"{doc.doc_type.replace('_', ' ').title()} {doc.doc_no} - {doc.party_name}", reference_type="trade_document", reference_id=doc.id, party_id=party.id, number_type=ntype)
    doc.voucher_id = voucher.id

    # COGS voucher for sales (perpetual inventory)
    if doc.doc_type in ("sales_invoice", "sales_return") and cost_total > ZERO:
        cogs_led = await sk("cogs")
        if doc.doc_type == "sales_invoice":
            cogs_lines = [LineSpec(cogs_led.id, debit=cost_total), LineSpec(inventory_led.id, credit=cost_total)]
        else:
            cogs_lines = [LineSpec(inventory_led.id, debit=cost_total), LineSpec(cogs_led.id, credit=cost_total)]
        cv = await post_voucher(db, ctx, voucher_type="journal", on=doc.date, lines=cogs_lines, narration=f"COGS for {doc.doc_no}", reference_type="trade_document", reference_id=doc.id, number_type="cogs")
        doc.cogs_voucher_id = cv.id

    # ---------------- OUTSTANDING EFFECT (bill-wise)
    if bill_sign == 1:
        bill = Bill(tenant_id=ctx.tenant_id, company_id=ctx.company_id, party_id=party.id, ledger_id=party_ledger.id, kind=bill_kind, bill_no=doc.doc_no, bill_date=doc.date, due_date=doc.due_date or doc.date, amount=doc.grand_total, doc_type=doc.doc_type, doc_id=doc.id, voucher_id=voucher.id)
        db.add(bill)
        await db.flush()
        if doc.paid_amount > ZERO:
            pay_led = await db.get(Ledger, doc.payment_ledger_id)
            if not pay_led or pay_led.company_id != ctx.company_id or not (pay_led.is_cash or pay_led.is_bank):
                raise HTTPException(422, "Payment ledger must be a cash or bank ledger")
            if bill_kind == "receivable":
                rl = [LineSpec(pay_led.id, debit=doc.paid_amount), LineSpec(party_ledger.id, credit=doc.paid_amount)]
                rtype = "receipt"
            else:
                rl = [LineSpec(party_ledger.id, debit=doc.paid_amount), LineSpec(pay_led.id, credit=doc.paid_amount)]
                rtype = "payment"
            rv = await post_voucher(db, ctx, voucher_type=rtype, on=doc.date, lines=rl, narration=f"{'Received' if rtype == 'receipt' else 'Paid'} against {doc.doc_no}", reference_type="trade_document", reference_id=doc.id, party_id=party.id)
            doc.receipt_voucher_id = rv.id
            db.add(BillSettlement(tenant_id=ctx.tenant_id, bill_id=bill.id, voucher_id=rv.id, amount=doc.paid_amount, date=doc.date))
    else:
        # return/credit: settle against the referenced bill if any, remainder becomes credit balance
        remaining = doc.grand_total
        if doc.reference_doc_id:
            ref_bill = (await db.execute(select(Bill).where(Bill.doc_id == doc.reference_doc_id, Bill.company_id == ctx.company_id))).scalar_one_or_none()
            if ref_bill:
                settled = sum((s.amount for s in ref_bill.settlements), ZERO)
                bal = money(ref_bill.amount - settled)
                take = min(bal, remaining)
                if take > ZERO:
                    db.add(BillSettlement(tenant_id=ctx.tenant_id, bill_id=ref_bill.id, voucher_id=voucher.id, amount=take, date=doc.date))
                    remaining -= take
        if remaining > ZERO:
            db.add(Bill(tenant_id=ctx.tenant_id, company_id=ctx.company_id, party_id=party.id, ledger_id=party_ledger.id, kind=bill_kind, bill_no=doc.doc_no, bill_date=doc.date, due_date=doc.date, amount=-remaining, doc_type=doc.doc_type, doc_id=doc.id, voucher_id=voucher.id))

    if doc.reference_doc_id and doc.doc_type in ("sales_invoice", "purchase_bill"):
        ref = await db.get(TradeDocument, doc.reference_doc_id)
        if ref and ref.status == "posted" and ref.doc_type not in ACCOUNTING_TYPES:
            ref.status = "converted"

    doc.status = "posted"
    doc.posted_at = now()
    # ---------------- AUDIT EFFECT
    await audit(db, ctx, "post", doc.doc_type, doc.id, f"{doc.doc_no} posted for {doc.party_name}: {doc.grand_total}", after={"doc_no": doc.doc_no, "grand_total": doc.grand_total, "voucher_id": doc.voucher_id, "cogs": cost_total})
    return doc


async def _reference_cost(db: AsyncSession, doc: TradeDocument, line: TradeLine) -> Decimal | None:
    if not doc.reference_doc_id:
        return None
    res = await db.execute(select(TradeLine).where(TradeLine.document_id == doc.reference_doc_id, TradeLine.product_id == line.product_id).limit(1))
    ref = res.scalar_one_or_none()
    return ref.cost_rate if ref and ref.cost_rate else None


async def cancel_document(db: AsyncSession, ctx: Ctx, doc: TradeDocument, reason: str | None) -> TradeDocument:
    if doc.company_id != ctx.company_id:
        raise HTTPException(404, "Document not found")
    if doc.status == "cancelled":
        raise HTTPException(422, "Already cancelled")
    today = date.today()
    if doc.status == "posted" and doc.doc_type in ACCOUNTING_TYPES:
        await assert_period_open(db, ctx.company_id, max(today, doc.date))
        # bills that have settlements from other vouchers cannot be cancelled
        res = await db.execute(select(Bill).where(Bill.doc_id == doc.id))
        for b in res.scalars().all():
            for s in b.settlements:
                if s.voucher_id not in (doc.voucher_id, doc.receipt_voucher_id):
                    raise HTTPException(422, f"{doc.doc_no} has receipts/payments allocated against it. Reverse those first.")
        for vid in (doc.receipt_voucher_id, doc.cogs_voucher_id, doc.voucher_id):
            if vid:
                v = await db.get(Voucher, vid)
                if v and v.status == "posted":
                    await reverse_voucher(db, ctx, v, on=max(today, doc.date), narration=f"Cancellation of {doc.doc_no}: {reason or ''}")
        # counter stock movements
        for line in doc.lines:
            product = await db.get(Product, line.product_id)
            sign = 1 if doc.doc_type in STOCK_OUT_TYPES else -1
            await stock_svc.add_movement(db, ctx, product=product, godown_id=line.godown_id or doc.godown_id, on=max(today, doc.date), movement_type=f"cancel_{doc.doc_type}", quantity=sign * line.qty, rate=line.cost_rate, batch_id=line.batch_id, doc_type=doc.doc_type, doc_id=doc.id, narration=f"Cancel {doc.doc_no}", allow_negative=True)
    doc.status = "cancelled"
    doc.notes = f"{doc.notes or ''}\nCANCELLED: {reason or ''}".strip()
    await audit(db, ctx, "cancel", doc.doc_type, doc.id, f"{doc.doc_no} cancelled. {reason or ''}")
    return doc


async def convert_document(db: AsyncSession, ctx: Ctx, source: TradeDocument, target_type: str, on: date | None) -> TradeDocument:
    if source.company_id != ctx.company_id:
        raise HTTPException(404, "Document not found")
    if target_type not in CONVERSIONS.get(source.doc_type, []):
        raise HTTPException(422, f"Cannot convert {source.doc_type} to {target_type}")
    if source.status == "cancelled":
        raise HTTPException(422, "Cannot convert a cancelled document")
    from ..schemas import TradeLineIn

    data = TradeDocIn(
        date=on or date.today(),
        party_id=source.party_id,
        place_of_supply=source.place_of_supply,
        godown_id=source.godown_id,
        project_id=source.project_id,
        reference_doc_id=source.id,
        notes=source.notes,
        terms=source.terms,
        salesman=source.salesman,
        lines=[TradeLineIn(product_id=l.product_id, description=l.description, batch_id=l.batch_id, godown_id=l.godown_id, qty=l.qty, unit_symbol=l.unit_symbol, area_sqft=l.area_sqft, rate=l.rate, discount_pct=l.discount_pct, gst_rate=l.gst_rate, hsn_code=l.hsn_code) for l in source.lines],
    )
    new_doc = await build_document(db, ctx, target_type, data)
    if source.doc_type not in ACCOUNTING_TYPES and source.status in ("draft", "posted") and target_type not in ("sales_return", "purchase_return"):
        source.status = "converted"
    await audit(db, ctx, "convert", source.doc_type, source.id, f"{source.doc_no} converted to {target_type} {new_doc.doc_no}")
    return new_doc


async def party_outstanding(db: AsyncSession, company_id: uuid.UUID, party_id: uuid.UUID, kind: str | None = None) -> Decimal:
    stmt = select(Bill).where(Bill.company_id == company_id, Bill.party_id == party_id)
    if kind:
        stmt = stmt.where(Bill.kind == kind)
    total = ZERO
    for b in (await db.execute(stmt)).scalars().all():
        total += b.amount - sum((s.amount for s in b.settlements), ZERO)
    return money(total)


async def doc_balance(db: AsyncSession, doc: TradeDocument) -> Decimal:
    if doc.doc_type not in ACCOUNTING_TYPES or doc.status != "posted":
        return ZERO
    res = await db.execute(select(Bill).where(Bill.doc_id == doc.id, Bill.amount > 0))
    b = res.scalar_one_or_none()
    if not b:
        return ZERO
    return money(b.amount - sum((s.amount for s in b.settlements), ZERO))
