"""Double-entry posting engine.

Rules:
- Every voucher must balance (sum debit == sum credit > 0).
- Posting date must fall in an open fiscal year and after any period lock.
- Posted vouchers are immutable; corrections are reversing vouchers with their own audit trail.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Ctx
from ..models import Bill, BillSettlement, Ledger, Voucher, VoucherLine
from .common import ZERO, assert_period_open, audit, money, next_number, now


class LineSpec:
    __slots__ = ("ledger_id", "debit", "credit", "narration", "cost_centre")

    def __init__(self, ledger_id: uuid.UUID, debit: Decimal = ZERO, credit: Decimal = ZERO, narration: str | None = None, cost_centre: str | None = None):
        self.ledger_id = ledger_id
        self.debit = money(debit)
        self.credit = money(credit)
        self.narration = narration
        self.cost_centre = cost_centre


async def get_system_ledger(db: AsyncSession, company_id: uuid.UUID, key: str) -> Ledger:
    res = await db.execute(select(Ledger).where(Ledger.company_id == company_id, Ledger.system_key == key))
    led = res.scalar_one_or_none()
    if not led:
        raise HTTPException(500, f"System ledger '{key}' missing for company. Re-run chart of accounts setup.")
    return led


async def post_voucher(
    db: AsyncSession,
    ctx: Ctx,
    *,
    voucher_type: str,
    on: date,
    lines: list[LineSpec],
    narration: str | None = None,
    reference_type: str | None = None,
    reference_id: uuid.UUID | None = None,
    party_id: uuid.UUID | None = None,
    status: str = "posted",
    reverses_id: uuid.UUID | None = None,
    idempotency_key: str | None = None,
    number_type: str | None = None,
) -> Voucher:
    # drop zero lines, validate
    lines = [l for l in lines if l.debit != ZERO or l.credit != ZERO]
    if len(lines) < 2:
        raise HTTPException(422, "A voucher needs at least two non-zero lines")
    for l in lines:
        if l.debit and l.credit:
            raise HTTPException(422, "A line cannot have both debit and credit")
        if l.debit < 0 or l.credit < 0:
            raise HTTPException(422, "Negative amounts are not allowed")
    total_dr = money(sum((l.debit for l in lines), ZERO))
    total_cr = money(sum((l.credit for l in lines), ZERO))
    if total_dr != total_cr:
        raise HTTPException(422, f"Voucher does not balance: debit {total_dr} != credit {total_cr}")
    if total_dr == ZERO:
        raise HTTPException(422, "Voucher total cannot be zero")

    fy = await assert_period_open(db, ctx.company_id, on)

    # ledger validation (tenant/company isolation)
    ledger_ids = {l.ledger_id for l in lines}
    res = await db.execute(select(Ledger.id).where(Ledger.company_id == ctx.company_id, Ledger.id.in_(ledger_ids), Ledger.is_active.is_(True)))
    found = {r[0] for r in res.all()}
    missing = ledger_ids - found
    if missing:
        raise HTTPException(422, f"Unknown or inactive ledger(s): {', '.join(str(m) for m in missing)}")

    if idempotency_key:
        existing = (await db.execute(select(Voucher).where(Voucher.company_id == ctx.company_id, Voucher.idempotency_key == idempotency_key))).scalar_one_or_none()
        if existing:
            return existing

    voucher_no = await next_number(db, ctx.tenant_id, ctx.company_id, number_type or voucher_type, fy)
    v = Voucher(
        tenant_id=ctx.tenant_id,
        company_id=ctx.company_id,
        branch_id=ctx.branch_id,
        fiscal_year_id=fy.id,
        voucher_type=voucher_type,
        voucher_no=voucher_no,
        date=on,
        narration=narration,
        reference_type=reference_type,
        reference_id=reference_id,
        party_id=party_id,
        total_debit=total_dr,
        total_credit=total_cr,
        status=status,
        reverses_id=reverses_id,
        posted_by=ctx.user_id,
        posted_at=now(),
        idempotency_key=idempotency_key,
    )
    for i, l in enumerate(lines, start=1):
        v.lines.append(VoucherLine(tenant_id=ctx.tenant_id, ledger_id=l.ledger_id, line_no=i, debit=l.debit, credit=l.credit, narration=l.narration, cost_centre=l.cost_centre))
    db.add(v)
    await db.flush()
    await audit(db, ctx, "post", "voucher", v.id, f"{voucher_type} {voucher_no} posted for {total_dr}", after={"voucher_no": voucher_no, "type": voucher_type, "date": on, "total": total_dr, "lines": [{"ledger_id": l.ledger_id, "dr": l.debit, "cr": l.credit} for l in lines]})
    return v


async def reverse_voucher(db: AsyncSession, ctx: Ctx, voucher: Voucher, on: date | None = None, narration: str | None = None) -> Voucher:
    if voucher.company_id != ctx.company_id:
        raise HTTPException(404, "Voucher not found")
    if voucher.status == "reversed":
        raise HTTPException(422, "Voucher already reversed")
    if voucher.status == "reversal":
        raise HTTPException(422, "A reversal voucher cannot itself be reversed; post a fresh voucher instead")
    on = on or voucher.date
    if on < voucher.date:
        raise HTTPException(422, "Reversal date cannot be before the original voucher date")
    lines = [LineSpec(l.ledger_id, debit=l.credit, credit=l.debit, narration=l.narration) for l in voucher.lines]
    rev = await post_voucher(
        db,
        ctx,
        voucher_type=voucher.voucher_type,
        on=on,
        lines=lines,
        narration=narration or f"Reversal of {voucher.voucher_no}",
        reference_type=voucher.reference_type,
        reference_id=voucher.reference_id,
        party_id=voucher.party_id,
        status="reversal",
        reverses_id=voucher.id,
        number_type="reversal",
    )
    voucher.status = "reversed"
    voucher.reversed_by_id = rev.id
    # reverse settlements tied to the original voucher
    res = await db.execute(select(BillSettlement).where(BillSettlement.voucher_id == voucher.id))
    for s in res.scalars().all():
        db.add(BillSettlement(tenant_id=ctx.tenant_id, bill_id=s.bill_id, voucher_id=rev.id, amount=-s.amount, date=on))
    # bills created by this voucher get an offsetting bill
    res = await db.execute(select(Bill).where(Bill.voucher_id == voucher.id))
    for b in res.scalars().all():
        db.add(Bill(tenant_id=ctx.tenant_id, company_id=ctx.company_id, party_id=b.party_id, ledger_id=b.ledger_id, kind=b.kind, bill_no=f"REV-{b.bill_no}", bill_date=on, due_date=on, amount=-b.amount, doc_type="reversal", doc_id=voucher.id, voucher_id=rev.id))
    await audit(db, ctx, "reverse", "voucher", voucher.id, f"{voucher.voucher_no} reversed by {rev.voucher_no}")
    return rev


async def open_bills(db: AsyncSession, company_id: uuid.UUID, party_id: uuid.UUID, kind: str) -> list[tuple[Bill, Decimal]]:
    res = await db.execute(select(Bill).where(Bill.company_id == company_id, Bill.party_id == party_id, Bill.kind == kind).order_by(Bill.bill_date, Bill.created_at))
    out: list[tuple[Bill, Decimal]] = []
    for b in res.scalars().all():
        settled = sum((s.amount for s in b.settlements), ZERO)
        bal = money(b.amount - settled)
        if bal > ZERO:
            out.append((b, bal))
    return out


async def allocate(db: AsyncSession, ctx: Ctx, voucher: Voucher, party_id: uuid.UUID, kind: str, amount: Decimal, explicit: list[tuple[uuid.UUID, Decimal]] | None, auto: bool) -> Decimal:
    """Allocate a receipt/payment amount against open bills. Returns unallocated remainder (kept as on-account credit)."""
    remaining = money(amount)
    if explicit:
        for bill_id, amt in explicit:
            bill = await db.get(Bill, bill_id)
            if not bill or bill.company_id != ctx.company_id or bill.party_id != party_id:
                raise HTTPException(422, f"Bill {bill_id} not found for party")
            settled = sum((s.amount for s in bill.settlements), ZERO)
            bal = money(bill.amount - settled)
            amt = money(amt)
            if amt <= ZERO or amt > bal:
                raise HTTPException(422, f"Allocation {amt} exceeds bill {bill.bill_no} balance {bal}")
            if amt > remaining:
                raise HTTPException(422, "Allocations exceed voucher amount")
            db.add(BillSettlement(tenant_id=ctx.tenant_id, bill_id=bill.id, voucher_id=voucher.id, amount=amt, date=voucher.date))
            remaining -= amt
    if auto and remaining > ZERO:
        for bill, bal in await open_bills(db, ctx.company_id, party_id, kind):
            if remaining <= ZERO:
                break
            take = min(bal, remaining)
            db.add(BillSettlement(tenant_id=ctx.tenant_id, bill_id=bill.id, voucher_id=voucher.id, amount=take, date=voucher.date))
            remaining -= take
    if remaining > ZERO:
        # on-account: negative bill so the party's net outstanding reflects the advance
        party_ledger = (await db.execute(select(Ledger.id).where(Ledger.company_id == ctx.company_id, Ledger.party_id == party_id))).scalar_one_or_none()
        db.add(Bill(tenant_id=ctx.tenant_id, company_id=ctx.company_id, party_id=party_id, ledger_id=party_ledger, kind=kind, bill_no=f"ADV-{voucher.voucher_no}", bill_date=voucher.date, due_date=voucher.date, amount=-remaining, doc_type="advance", doc_id=voucher.id, voucher_id=voucher.id))
    return remaining
