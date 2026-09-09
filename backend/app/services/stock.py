"""Stock engine: movements, balances, weighted-average valuation."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Ctx
from ..models import Batch, Company, Godown, Product, StockMovement, StockReservation
from .common import ZERO, money, now, qty


async def avg_cost(db: AsyncSession, company_id: uuid.UUID, product_id: uuid.UUID, fallback: Decimal | None = None) -> Decimal:
    """Weighted average cost from inward movements (opening/purchase/adjust-in/transfer-in/sales-return)."""
    res = await db.execute(
        select(func.coalesce(func.sum(StockMovement.qty), 0), func.coalesce(func.sum(StockMovement.value), 0)).where(
            StockMovement.company_id == company_id, StockMovement.product_id == product_id, StockMovement.qty > 0
        )
    )
    q, v = res.one()
    q, v = Decimal(q), Decimal(v)
    if q > ZERO and v > ZERO:
        return (v / q).quantize(Decimal("0.0001"))
    if fallback is not None:
        return fallback
    prod = await db.get(Product, product_id)
    return prod.purchase_price if prod else ZERO


async def balance(db: AsyncSession, company_id: uuid.UUID, product_id: uuid.UUID, godown_id: uuid.UUID | None = None, batch_id: uuid.UUID | None = None, as_of: date | None = None) -> Decimal:
    stmt = select(func.coalesce(func.sum(StockMovement.qty), 0)).where(StockMovement.company_id == company_id, StockMovement.product_id == product_id)
    if godown_id:
        stmt = stmt.where(StockMovement.godown_id == godown_id)
    if batch_id:
        stmt = stmt.where(StockMovement.batch_id == batch_id)
    if as_of:
        stmt = stmt.where(StockMovement.date <= as_of)
    return Decimal((await db.execute(stmt)).scalar_one())


async def reserved_qty(db: AsyncSession, company_id: uuid.UUID, product_id: uuid.UUID, godown_id: uuid.UUID | None = None, batch_id: uuid.UUID | None = None) -> Decimal:
    stmt = select(func.coalesce(func.sum(StockReservation.qty), 0)).where(StockReservation.company_id == company_id, StockReservation.product_id == product_id, StockReservation.status == "active")
    if godown_id:
        stmt = stmt.where(StockReservation.godown_id == godown_id)
    if batch_id:
        stmt = stmt.where(StockReservation.batch_id == batch_id)
    return Decimal((await db.execute(stmt)).scalar_one())


async def default_godown(db: AsyncSession, company_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> Godown:
    stmt = select(Godown).where(Godown.company_id == company_id, Godown.is_active.is_(True))
    if branch_id:
        res = await db.execute(stmt.where(Godown.branch_id == branch_id).order_by(Godown.is_default.desc()).limit(1))
        g = res.scalar_one_or_none()
        if g:
            return g
    res = await db.execute(stmt.order_by(Godown.is_default.desc()).limit(1))
    g = res.scalar_one_or_none()
    if not g:
        raise HTTPException(422, "No godown configured. Create one under Inventory > Godowns.")
    return g


async def add_movement(
    db: AsyncSession,
    ctx: Ctx,
    *,
    product: Product,
    godown_id: uuid.UUID,
    on: date,
    movement_type: str,
    quantity: Decimal,
    rate: Decimal,
    batch_id: uuid.UUID | None = None,
    doc_type: str | None = None,
    doc_id: uuid.UUID | None = None,
    narration: str | None = None,
    allow_negative: bool | None = None,
) -> StockMovement:
    quantity = qty(quantity)
    if quantity == ZERO:
        raise HTTPException(422, f"Zero quantity movement for {product.name}")
    if batch_id:
        b = await db.get(Batch, batch_id)
        if not b or b.product_id != product.id:
            raise HTTPException(422, f"Batch does not belong to product {product.name}")
    if quantity < ZERO:
        if allow_negative is None:
            company = await db.get(Company, ctx.company_id)
            allow_negative = bool(company and company.allow_negative_stock)
        if not allow_negative:
            available = await balance(db, ctx.company_id, product.id, godown_id, batch_id)
            if available + quantity < ZERO:
                where = f" in batch" if batch_id else ""
                raise HTTPException(422, f"Insufficient stock for {product.name}{where}: available {available.normalize()} {product.stock_unit.symbol}, required {(-quantity).normalize()}")
    mv = StockMovement(
        tenant_id=ctx.tenant_id,
        company_id=ctx.company_id,
        branch_id=ctx.branch_id,
        godown_id=godown_id,
        product_id=product.id,
        batch_id=batch_id,
        date=on,
        movement_type=movement_type,
        qty=quantity,
        rate=rate,
        value=money(quantity * rate),
        doc_type=doc_type,
        doc_id=doc_id,
        narration=narration,
        created_at=now(),
    )
    db.add(mv)
    return mv


async def stock_summary(db: AsyncSession, company_id: uuid.UUID, godown_id: uuid.UUID | None = None, as_of: date | None = None, search: str | None = None, low_only: bool = False) -> list[dict]:
    agg = select(StockMovement.product_id, func.coalesce(func.sum(StockMovement.qty), 0).label("qty"), func.coalesce(func.sum(StockMovement.value), 0).label("value")).where(StockMovement.company_id == company_id)
    if godown_id:
        agg = agg.where(StockMovement.godown_id == godown_id)
    if as_of:
        agg = agg.where(StockMovement.date <= as_of)
    agg = agg.group_by(StockMovement.product_id).subquery()
    stmt = (
        select(Product, func.coalesce(agg.c.qty, 0), func.coalesce(agg.c.value, 0))
        .outerjoin(agg, agg.c.product_id == Product.id)
        .where(Product.company_id == company_id, Product.is_active.is_(True))
        .order_by(Product.name)
    )
    if search:
        like = f"%{search}%"
        stmt = stmt.where(Product.name.ilike(like) | Product.sku.ilike(like) | Product.series.ilike(like) | Product.design.ilike(like))
    rows = (await db.execute(stmt)).all()
    out = []
    for prod, q, v in rows:
        q = Decimal(q)
        v = Decimal(v)
        # value at running average (in - out at avg): value column is signed so sum is the current stock value
        status = "out" if q <= ZERO else ("low" if prod.reorder_level and q <= prod.reorder_level else "in")
        if low_only and status == "in":
            continue
        out.append(
            {
                "product_id": prod.id,
                "sku": prod.sku,
                "name": prod.name,
                "product_type": prod.product_type,
                "brand": prod.brand.name if prod.brand else None,
                "size": prod.size,
                "unit": prod.stock_unit.symbol,
                "sqft_per_box": prod.sqft_per_box,
                "qty": q,
                "area_sqft": (q * prod.sqft_per_box) if prod.sqft_per_box else None,
                "value": money(v),
                "avg_cost": (v / q).quantize(Decimal("0.01")) if q > ZERO else ZERO,
                "reorder_level": prod.reorder_level,
                "status": status,
            }
        )
    return out


async def stock_by_godown_batch(db: AsyncSession, company_id: uuid.UUID, product_id: uuid.UUID) -> list[dict]:
    stmt = (
        select(StockMovement.godown_id, StockMovement.batch_id, func.sum(StockMovement.qty), func.sum(StockMovement.value))
        .where(StockMovement.company_id == company_id, StockMovement.product_id == product_id)
        .group_by(StockMovement.godown_id, StockMovement.batch_id)
    )
    rows = (await db.execute(stmt)).all()
    godowns = {g.id: g for g in (await db.execute(select(Godown).where(Godown.company_id == company_id))).scalars().all()}
    batches = {b.id: b for b in (await db.execute(select(Batch).where(Batch.product_id == product_id))).scalars().all()}
    out = []
    for gid, bid, q, v in rows:
        q = Decimal(q)
        if q == ZERO:
            continue
        b = batches.get(bid) if bid else None
        reserved = await reserved_qty(db, company_id, product_id, gid, bid)
        out.append(
            {
                "godown_id": gid,
                "godown": godowns[gid].name if gid in godowns else None,
                "batch_id": bid,
                "batch_no": b.batch_no if b else None,
                "shade": b.shade if b else None,
                "calibre": b.calibre if b else None,
                "qty": q,
                "reserved": reserved,
                "available": q - reserved,
                "value": money(Decimal(v)),
            }
        )
    return out
