from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Ctx
from ..models import AuditLog, FiscalYear, NumberSequence

ZERO = Decimal("0")
CENT = Decimal("0.01")
Q4 = Decimal("0.0001")


def D(v: Any) -> Decimal:
    if v is None:
        return ZERO
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def money(v: Any) -> Decimal:
    return D(v).quantize(CENT, rounding=ROUND_HALF_UP)


def qty(v: Any) -> Decimal:
    return D(v).quantize(Q4, rounding=ROUND_HALF_UP)


def now() -> datetime:
    return datetime.now(timezone.utc)


def jsonable(obj: Any) -> Any:
    """Make ORM/Decimal/UUID/date values JSON-serialisable for audit payloads."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, (uuid.UUID,)):
        return str(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [jsonable(v) for v in obj]
    if hasattr(obj, "__table__"):
        return {c.name: jsonable(getattr(obj, c.name)) for c in obj.__table__.columns}
    return str(obj)


async def audit(db: AsyncSession, ctx: Ctx | None, action: str, entity_type: str, entity_id: Any = None, summary: str | None = None, before: Any = None, after: Any = None, tenant_id: uuid.UUID | None = None, company_id: uuid.UUID | None = None) -> None:
    log = AuditLog(
        tenant_id=ctx.tenant_id if ctx else tenant_id,
        company_id=ctx.company_id if ctx else company_id,
        user_id=ctx.user_id if ctx else None,
        user_email=ctx.user.email if ctx else "system",
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id else None,
        summary=summary,
        before=jsonable(before) if before is not None else None,
        after=jsonable(after) if after is not None else None,
        ip=ctx.ip if ctx else None,
        created_at=now(),
    )
    db.add(log)


async def get_fiscal_year(db: AsyncSession, company_id: uuid.UUID, on: date) -> FiscalYear:
    res = await db.execute(select(FiscalYear).where(FiscalYear.company_id == company_id, FiscalYear.start_date <= on, FiscalYear.end_date >= on))
    fy = res.scalar_one_or_none()
    if not fy:
        raise HTTPException(422, f"No fiscal year covers {on.isoformat()}. Create one in Settings > Fiscal years.")
    return fy


async def assert_period_open(db: AsyncSession, company_id: uuid.UUID, on: date) -> FiscalYear:
    fy = await get_fiscal_year(db, company_id, on)
    if fy.is_closed:
        raise HTTPException(422, f"Fiscal year {fy.name} is closed. Posting not allowed.")
    if fy.locked_till and on <= fy.locked_till:
        raise HTTPException(422, f"Period is locked till {fy.locked_till.isoformat()}. Posting on {on.isoformat()} not allowed.")
    return fy


DOC_PREFIX = {
    "journal": "JV",
    "payment": "PAY",
    "receipt": "RCP",
    "contra": "CTR",
    "sales": "SV",
    "purchase": "PV",
    "credit_note": "CN",
    "debit_note": "DN",
    "cogs": "COGS",
    "stock_journal": "SJ",
    "quotation": "QT",
    "sales_order": "SO",
    "delivery_challan": "DC",
    "sales_invoice": "INV",
    "sales_return": "SR",
    "purchase_order": "PO",
    "grn": "GRN",
    "purchase_bill": "PB",
    "purchase_return": "PR",
    "adjustment": "ADJ",
    "transfer": "TRF",
    "opening": "OPN",
    "physical_count": "PHY",
    "reversal": "REV",
}


async def next_number(db: AsyncSession, tenant_id: uuid.UUID, company_id: uuid.UUID, doc_type: str, fy: FiscalYear | None) -> str:
    """Atomic per-company/doc-type/fiscal-year sequence. Uses SELECT ... FOR UPDATE."""
    fy_id = fy.id if fy else None
    stmt = select(NumberSequence).where(NumberSequence.company_id == company_id, NumberSequence.doc_type == doc_type, NumberSequence.fiscal_year_id == fy_id).with_for_update()
    seq = (await db.execute(stmt)).scalar_one_or_none()
    if seq is None:
        seq = NumberSequence(tenant_id=tenant_id, company_id=company_id, doc_type=doc_type, fiscal_year_id=fy_id, prefix=DOC_PREFIX.get(doc_type, doc_type[:3].upper()), next_number=1)
        db.add(seq)
        await db.flush()
    n = seq.next_number
    seq.next_number = n + 1
    fy_tag = fy.name if fy else ""
    return f"{seq.prefix}/{fy_tag}/{n:04d}" if fy_tag else f"{seq.prefix}/{n:04d}"
