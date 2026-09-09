from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..deps import Ctx, get_ctx, require
from ..models import AccountGroup, Bill, Ledger, Party, Voucher
from ..schemas import AccountGroupIn, AccountGroupOut, LedgerIn, LedgerOut, QuickReceiptIn, ReverseIn, VoucherIn, VoucherLineOut, VoucherOut
from ..services.common import ZERO, audit, jsonable, money
from ..services.posting import LineSpec, allocate, open_bills, post_voucher, reverse_voucher
from ..services.reports import ledger_movements, signed_opening

router = APIRouter(prefix="/accounting", tags=["accounting"])


def voucher_out(v: Voucher) -> VoucherOut:
    out = VoucherOut.model_validate(v)
    out.lines = [VoucherLineOut(id=l.id, ledger_id=l.ledger_id, ledger_name=l.ledger.name if l.ledger else None, line_no=l.line_no, debit=l.debit, credit=l.credit, narration=l.narration, cost_centre=l.cost_centre) for l in v.lines]
    return out


# ------------------------------------------------------------------ groups
@router.get("/groups", response_model=list[AccountGroupOut])
async def list_groups(ctx: Ctx = Depends(require("accounting.view")), db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(AccountGroup).where(AccountGroup.company_id == ctx.company_id).order_by(AccountGroup.sequence, AccountGroup.name))).scalars().all()


@router.post("/groups", response_model=AccountGroupOut, status_code=201)
async def create_group(data: AccountGroupIn, ctx: Ctx = Depends(require("accounting.manage")), db: AsyncSession = Depends(get_db)):
    report = "profit_loss" if data.nature in ("income", "expense") else "balance_sheet"
    g = AccountGroup(tenant_id=ctx.tenant_id, company_id=ctx.company_id, report=report, sequence=200, **data.model_dump())
    db.add(g)
    await audit(db, ctx, "create", "account_group", None, f"Group {g.name} created")
    await db.commit()
    await db.refresh(g)
    return g


# ------------------------------------------------------------------ ledgers
@router.get("/ledgers", response_model=list[LedgerOut])
async def list_ledgers(q: str | None = None, group_id: uuid.UUID | None = None, kind: str | None = Query(None, description="cash_bank | party | non_party"), with_balance: bool = True, ctx: Ctx = Depends(require("accounting.view")), db: AsyncSession = Depends(get_db)):
    stmt = select(Ledger).where(Ledger.company_id == ctx.company_id)
    if q:
        stmt = stmt.where(Ledger.name.ilike(f"%{q}%"))
    if group_id:
        stmt = stmt.where(Ledger.group_id == group_id)
    if kind == "cash_bank":
        stmt = stmt.where(Ledger.is_cash.is_(True) | Ledger.is_bank.is_(True))
    elif kind == "party":
        stmt = stmt.where(Ledger.party_id.is_not(None))
    elif kind == "non_party":
        stmt = stmt.where(Ledger.party_id.is_(None))
    ledgers = (await db.execute(stmt.order_by(Ledger.name))).scalars().all()
    mv = await ledger_movements(db, ctx.company_id) if with_balance else {}
    out = []
    for l in ledgers:
        o = LedgerOut.model_validate(l)
        o.group_name = l.group.name if l.group else None
        o.nature = l.group.nature if l.group else None
        if with_balance:
            d, c = mv.get(l.id, (ZERO, ZERO))
            bal = signed_opening(l) + d - c
            o.balance = money(abs(bal))
            o.balance_type = "dr" if bal >= 0 else "cr"
        out.append(o)
    return out


@router.post("/ledgers", response_model=LedgerOut, status_code=201)
async def create_ledger(data: LedgerIn, ctx: Ctx = Depends(require("accounting.manage")), db: AsyncSession = Depends(get_db)):
    g = await db.get(AccountGroup, data.group_id)
    if not g or g.company_id != ctx.company_id:
        raise HTTPException(422, "Group not found")
    dup = (await db.execute(select(Ledger.id).where(Ledger.company_id == ctx.company_id, Ledger.name == data.name))).first()
    if dup:
        raise HTTPException(409, "Ledger with this name already exists")
    l = Ledger(tenant_id=ctx.tenant_id, company_id=ctx.company_id, **data.model_dump())
    db.add(l)
    await audit(db, ctx, "create", "ledger", None, f"Ledger {l.name} created")
    await db.commit()
    await db.refresh(l)
    o = LedgerOut.model_validate(l)
    o.group_name = g.name
    o.nature = g.nature
    return o


@router.put("/ledgers/{ledger_id}", response_model=LedgerOut)
async def update_ledger(ledger_id: uuid.UUID, data: LedgerIn, ctx: Ctx = Depends(require("accounting.manage")), db: AsyncSession = Depends(get_db)):
    l = await db.get(Ledger, ledger_id)
    if not l or l.company_id != ctx.company_id:
        raise HTTPException(404, "Ledger not found")
    before = jsonable(l)
    payload = data.model_dump()
    if l.is_system:
        payload.pop("group_id", None)  # system ledgers keep their group
    for k, v in payload.items():
        setattr(l, k, v)
    await audit(db, ctx, "update", "ledger", l.id, f"Ledger {l.name} updated", before=before, after=l)
    await db.commit()
    await db.refresh(l)
    o = LedgerOut.model_validate(l)
    o.group_name = l.group.name if l.group else None
    o.nature = l.group.nature if l.group else None
    return o


# ------------------------------------------------------------------ vouchers
@router.get("/vouchers")
async def list_vouchers(
    voucher_type: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = Query(50, le=200),
    ctx: Ctx = Depends(require("accounting.view")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Voucher).where(Voucher.company_id == ctx.company_id)
    if voucher_type:
        stmt = stmt.where(Voucher.voucher_type == voucher_type)
    if from_date:
        stmt = stmt.where(Voucher.date >= from_date)
    if to_date:
        stmt = stmt.where(Voucher.date <= to_date)
    if q:
        stmt = stmt.where(Voucher.voucher_no.ilike(f"%{q}%") | Voucher.narration.ilike(f"%{q}%"))
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await db.execute(stmt.order_by(Voucher.date.desc(), Voucher.posted_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return {"items": [voucher_out(v) for v in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/vouchers/{voucher_id}", response_model=VoucherOut)
async def get_voucher(voucher_id: uuid.UUID, ctx: Ctx = Depends(require("accounting.view")), db: AsyncSession = Depends(get_db)):
    v = await db.get(Voucher, voucher_id)
    if not v or v.company_id != ctx.company_id:
        raise HTTPException(404, "Voucher not found")
    return voucher_out(v)


@router.post("/vouchers", response_model=VoucherOut, status_code=201)
async def create_voucher(data: VoucherIn, ctx: Ctx = Depends(require("accounting.post")), db: AsyncSession = Depends(get_db)):
    lines = [LineSpec(l.ledger_id, l.debit, l.credit, l.narration, l.cost_centre) for l in data.lines]
    ledger_ids = [l.ledger_id for l in data.lines]
    ledgers = {l.id: l for l in (await db.execute(select(Ledger).where(Ledger.id.in_(ledger_ids)))).scalars().all()}
    if data.voucher_type == "contra":
        if not all(ledgers[i].is_cash or ledgers[i].is_bank for i in ledger_ids if i in ledgers):
            raise HTTPException(422, "Contra vouchers can only move money between cash and bank ledgers")
    party_id = data.party_id
    if party_id is None:
        parties = [ledgers[i].party_id for i in ledger_ids if i in ledgers and ledgers[i].party_id]
        party_id = parties[0] if parties else None
    v = await post_voucher(db, ctx, voucher_type=data.voucher_type, on=data.date, lines=lines, narration=data.narration, party_id=party_id, idempotency_key=data.idempotency_key)
    if party_id and data.voucher_type in ("receipt", "payment", "journal"):
        party = await db.get(Party, party_id)
        if party:
            party_amount = ZERO
            for l in data.lines:
                if l.ledger_id in ledgers and ledgers[l.ledger_id].party_id == party_id:
                    party_amount += (l.credit - l.debit) if data.voucher_type == "receipt" else (l.debit - l.credit)
            if party_amount > ZERO:
                kind = "receivable" if data.voucher_type == "receipt" else "payable"
                await allocate(db, ctx, v, party_id, kind, party_amount, [(a.bill_id, a.amount) for a in data.allocations], data.auto_allocate)
    await db.commit()
    await db.refresh(v)
    return voucher_out(v)


@router.post("/quick-entry", response_model=VoucherOut, status_code=201)
async def quick_entry(data: QuickReceiptIn, ctx: Ctx = Depends(require("accounting.post")), db: AsyncSession = Depends(get_db)):
    """Receive from customer / pay supplier in one step (with bill allocation)."""
    party = await db.get(Party, data.party_id)
    if not party or party.company_id != ctx.company_id or not party.ledger_id:
        raise HTTPException(422, "Party not found")
    acct = await db.get(Ledger, data.account_ledger_id)
    if not acct or acct.company_id != ctx.company_id or not (acct.is_cash or acct.is_bank):
        raise HTTPException(422, "Select a cash or bank ledger")
    amt = money(data.amount)
    if data.kind == "receipt":
        lines = [LineSpec(acct.id, debit=amt), LineSpec(party.ledger_id, credit=amt)]
        kind = "receivable"
    else:
        lines = [LineSpec(party.ledger_id, debit=amt), LineSpec(acct.id, credit=amt)]
        kind = "payable"
    v = await post_voucher(db, ctx, voucher_type=data.kind, on=data.date, lines=lines, narration=data.narration or f"{'Received from' if data.kind == 'receipt' else 'Paid to'} {party.name}", party_id=party.id, idempotency_key=data.idempotency_key)
    await allocate(db, ctx, v, party.id, kind, amt, [(a.bill_id, a.amount) for a in data.allocations], data.auto_allocate)
    await db.commit()
    await db.refresh(v)
    return voucher_out(v)


@router.post("/vouchers/{voucher_id}/reverse", response_model=VoucherOut)
async def reverse(voucher_id: uuid.UUID, data: ReverseIn, ctx: Ctx = Depends(require("accounting.reverse")), db: AsyncSession = Depends(get_db)):
    v = await db.get(Voucher, voucher_id)
    if not v or v.company_id != ctx.company_id:
        raise HTTPException(404, "Voucher not found")
    if v.reference_type == "trade_document":
        raise HTTPException(422, "This voucher belongs to a sales/purchase document. Cancel the document instead.")
    rev = await reverse_voucher(db, ctx, v, data.date, data.narration)
    await db.commit()
    await db.refresh(rev)
    return voucher_out(rev)


@router.get("/bills/open")
async def list_open_bills(party_id: uuid.UUID, kind: str = "receivable", ctx: Ctx = Depends(require("accounting.view")), db: AsyncSession = Depends(get_db)):
    rows = await open_bills(db, ctx.company_id, party_id, kind)
    return [{"bill_id": b.id, "bill_no": b.bill_no, "bill_date": b.bill_date, "due_date": b.due_date, "amount": b.amount, "balance": bal, "doc_type": b.doc_type, "doc_id": b.doc_id} for b, bal in rows]
