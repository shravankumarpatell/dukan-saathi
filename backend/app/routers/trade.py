from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..deps import Ctx, get_ctx, require
from ..models import PURCHASE_DOC_TYPES, SALES_DOC_TYPES, Bill, Company, Party, TradeDocument, TradeLine
from ..schemas import ConvertIn, TradeDocIn, TradeDocListOut, TradeDocOut
from ..services import trade as T
from ..services.common import ZERO, audit, money

router = APIRouter(prefix="/trade", tags=["trade"])
ALL_TYPES = SALES_DOC_TYPES + PURCHASE_DOC_TYPES


def _perm(doc_type: str, action: str) -> str:
    module = "sales" if doc_type in SALES_DOC_TYPES else "purchase"
    return f"{module}.{action}"


def _check_type(doc_type: str) -> None:
    if doc_type not in ALL_TYPES:
        raise HTTPException(404, f"Unknown document type '{doc_type}'")


async def _get(db: AsyncSession, ctx: Ctx, doc_id: uuid.UUID) -> TradeDocument:
    d = await db.get(TradeDocument, doc_id)
    if not d or d.company_id != ctx.company_id:
        raise HTTPException(404, "Document not found")
    return d


async def _out(db: AsyncSession, d: TradeDocument) -> TradeDocOut:
    o = TradeDocOut.model_validate(d)
    o.balance_due = await T.doc_balance(db, d)
    return o


@router.get("/types")
async def doc_types(ctx: Ctx = Depends(get_ctx)):
    return {"sales": list(SALES_DOC_TYPES), "purchase": list(PURCHASE_DOC_TYPES), "conversions": T.CONVERSIONS}


@router.get("/{doc_type}")
async def list_docs(
    doc_type: str,
    status: str | None = None,
    party_id: uuid.UUID | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = Query(50, le=500),
    ctx: Ctx = Depends(get_ctx),
    db: AsyncSession = Depends(get_db),
):
    _check_type(doc_type)
    if not ctx.has(_perm(doc_type, "view")):
        raise HTTPException(403, f"Missing permission: {_perm(doc_type, 'view')}")
    stmt = select(TradeDocument).where(TradeDocument.company_id == ctx.company_id, TradeDocument.doc_type == doc_type)
    if status:
        stmt = stmt.where(TradeDocument.status == status)
    if party_id:
        stmt = stmt.where(TradeDocument.party_id == party_id)
    if from_date:
        stmt = stmt.where(TradeDocument.date >= from_date)
    if to_date:
        stmt = stmt.where(TradeDocument.date <= to_date)
    if q:
        stmt = stmt.where(TradeDocument.doc_no.ilike(f"%{q}%") | TradeDocument.party_name.ilike(f"%{q}%") | TradeDocument.supplier_ref_no.ilike(f"%{q}%"))
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    docs = (await db.execute(stmt.order_by(TradeDocument.date.desc(), TradeDocument.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    # balances in one query
    ids = [d.id for d in docs]
    bills = (await db.execute(select(Bill).where(Bill.doc_id.in_(ids), Bill.amount > 0))).scalars().all() if ids else []
    bal = {b.doc_id: money(b.amount - sum((s.amount for s in b.settlements), ZERO)) for b in bills}
    items = [
        TradeDocListOut(id=d.id, doc_type=d.doc_type, doc_no=d.doc_no, date=d.date, due_date=d.due_date, party_id=d.party_id, party_name=d.party_name, status=d.status, taxable_total=d.taxable_total, grand_total=d.grand_total, paid_amount=d.paid_amount, balance_due=bal.get(d.id, ZERO), line_count=len(d.lines))
        for d in docs
    ]
    sum_total = (await db.execute(select(func.coalesce(func.sum(TradeDocument.grand_total), 0)).select_from(stmt.subquery()))).scalar_one()
    return {"items": items, "total": total, "page": page, "page_size": page_size, "sum_grand_total": money(sum_total)}


@router.post("/{doc_type}", response_model=TradeDocOut, status_code=201)
async def create_doc(doc_type: str, data: TradeDocIn, ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    _check_type(doc_type)
    if not ctx.has(_perm(doc_type, "write")):
        raise HTTPException(403, f"Missing permission: {_perm(doc_type, 'write')}")
    if data.idempotency_key:
        existing = (await db.execute(select(TradeDocument).where(TradeDocument.company_id == ctx.company_id, TradeDocument.idempotency_key == data.idempotency_key))).scalar_one_or_none()
        if existing:
            return await _out(db, existing)
    d = await T.build_document(db, ctx, doc_type, data)
    await audit(db, ctx, "create", doc_type, d.id, f"{d.doc_no} draft created for {d.party_name} ({d.grand_total})")
    if data.post:
        if not ctx.has(_perm(doc_type, "post")):
            raise HTTPException(403, f"Missing permission: {_perm(doc_type, 'post')}")
        await T.post_document(db, ctx, d)
    await db.commit()
    await db.refresh(d)
    return await _out(db, d)


@router.get("/{doc_type}/{doc_id}", response_model=TradeDocOut)
async def get_doc(doc_type: str, doc_id: uuid.UUID, ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    _check_type(doc_type)
    d = await _get(db, ctx, doc_id)
    return await _out(db, d)


@router.put("/{doc_type}/{doc_id}", response_model=TradeDocOut)
async def update_doc(doc_type: str, doc_id: uuid.UUID, data: TradeDocIn, ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    _check_type(doc_type)
    if not ctx.has(_perm(doc_type, "write")):
        raise HTTPException(403, f"Missing permission: {_perm(doc_type, 'write')}")
    d = await _get(db, ctx, doc_id)
    d = await T.build_document(db, ctx, doc_type, data, d)
    await audit(db, ctx, "update", doc_type, d.id, f"{d.doc_no} draft updated ({d.grand_total})")
    if data.post:
        if not ctx.has(_perm(doc_type, "post")):
            raise HTTPException(403, f"Missing permission: {_perm(doc_type, 'post')}")
        await T.post_document(db, ctx, d)
    await db.commit()
    await db.refresh(d)
    return await _out(db, d)


@router.post("/{doc_type}/{doc_id}/post", response_model=TradeDocOut)
async def post_doc(doc_type: str, doc_id: uuid.UUID, ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    _check_type(doc_type)
    if not ctx.has(_perm(doc_type, "post")):
        raise HTTPException(403, f"Missing permission: {_perm(doc_type, 'post')}")
    d = await _get(db, ctx, doc_id)
    await T.post_document(db, ctx, d)
    await db.commit()
    await db.refresh(d)
    return await _out(db, d)


@router.post("/{doc_type}/{doc_id}/cancel", response_model=TradeDocOut)
async def cancel_doc(doc_type: str, doc_id: uuid.UUID, reason: str | None = None, ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    _check_type(doc_type)
    if not ctx.has(_perm(doc_type, "post")):
        raise HTTPException(403, f"Missing permission: {_perm(doc_type, 'post')}")
    d = await _get(db, ctx, doc_id)
    await T.cancel_document(db, ctx, d, reason)
    await db.commit()
    await db.refresh(d)
    return await _out(db, d)


@router.post("/{doc_type}/{doc_id}/convert", response_model=TradeDocOut, status_code=201)
async def convert_doc(doc_type: str, doc_id: uuid.UUID, data: ConvertIn, ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    _check_type(doc_type)
    _check_type(data.target_doc_type)
    if not ctx.has(_perm(data.target_doc_type, "write")):
        raise HTTPException(403, f"Missing permission: {_perm(data.target_doc_type, 'write')}")
    src = await _get(db, ctx, doc_id)
    new = await T.convert_document(db, ctx, src, data.target_doc_type, data.date)
    if data.post:
        if not ctx.has(_perm(data.target_doc_type, "post")):
            raise HTTPException(403, f"Missing permission: {_perm(data.target_doc_type, 'post')}")
        await T.post_document(db, ctx, new)
    await db.commit()
    await db.refresh(new)
    return await _out(db, new)


@router.get("/{doc_type}/{doc_id}/print")
async def print_payload(doc_type: str, doc_id: uuid.UUID, ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    """All data needed to render a printable invoice/quotation (frontend renders + window.print)."""
    _check_type(doc_type)
    d = await _get(db, ctx, doc_id)
    company = await db.get(Company, ctx.company_id)
    party = await db.get(Party, d.party_id)
    from ..services.gst import INDIAN_STATES

    return {
        "company": {"name": company.name, "legal_name": company.legal_name, "gstin": company.gstin, "address": ", ".join(x for x in [company.address_line1, company.address_line2, company.city, company.state, company.pincode] if x), "phone": company.phone, "email": company.email, "state": INDIAN_STATES.get(company.state_code, company.state_code), "state_code": company.state_code},
        "party": {"name": party.name, "gstin": party.gstin, "address": party.billing_address, "shipping_address": party.shipping_address, "phone": party.phone, "state": INDIAN_STATES.get(party.state_code, party.state_code), "state_code": party.state_code},
        "document": await _out(db, d),
        "place_of_supply": INDIAN_STATES.get(d.place_of_supply, d.place_of_supply),
        "amount_in_words": amount_in_words(d.grand_total),
    }


def amount_in_words(amount) -> str:
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def words(n: int) -> str:
        if n < 20:
            return ones[n]
        if n < 100:
            return tens[n // 10] + (" " + ones[n % 10] if n % 10 else "")
        if n < 1000:
            return ones[n // 100] + " Hundred" + (" " + words(n % 100) if n % 100 else "")
        if n < 100000:
            return words(n // 1000) + " Thousand" + (" " + words(n % 1000) if n % 1000 else "")
        if n < 10000000:
            return words(n // 100000) + " Lakh" + (" " + words(n % 100000) if n % 100000 else "")
        return words(n // 10000000) + " Crore" + (" " + words(n % 10000000) if n % 10000000 else "")

    rupees = int(amount)
    paise = int(round((amount - rupees) * 100))
    s = f"Rupees {words(rupees) if rupees else 'Zero'}"
    if paise:
        s += f" and {words(paise)} Paise"
    return s + " Only"
