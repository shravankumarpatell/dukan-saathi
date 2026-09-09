from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..deps import Ctx, get_ctx, require
from ..models import Batch, Brand, Category, Godown, Product, SampleIssue, StockJournal, StockMovement, StockReservation, Unit
from ..schemas import BatchIn, BatchOut, BrandOut, CategoryIn, CategoryOut, GodownIn, GodownOut, NamedIn, ProductIn, ProductOut, ReservationIn, ReservationOut, SampleIn, SampleOut, StockJournalIn, StockJournalOut, UnitConvertIn, UnitIn, UnitOut
from ..services import stock as S
from ..services.common import ZERO, assert_period_open, audit, get_fiscal_year, jsonable, money, next_number, qty
from ..services.posting import LineSpec, get_system_ledger, post_voucher
from ..services.tile import convert_units

router = APIRouter(prefix="/inventory", tags=["inventory"])


def product_out(p: Product, stock_qty: Decimal | None = None, stock_value: Decimal | None = None) -> ProductOut:
    o = ProductOut.model_validate(p)
    o.unit_symbol = p.stock_unit.symbol if p.stock_unit else None
    o.brand_name = p.brand.name if p.brand else None
    o.category_name = p.category.name if p.category else None
    o.stock_qty = stock_qty
    o.stock_value = stock_value
    return o


# ------------------------------------------------------------------ units / brands / categories / godowns
@router.get("/units", response_model=list[UnitOut])
async def list_units(ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(Unit).where(Unit.company_id == ctx.company_id).order_by(Unit.name))).scalars().all()


@router.post("/units", response_model=UnitOut, status_code=201)
async def create_unit(data: UnitIn, ctx: Ctx = Depends(require("inventory.manage")), db: AsyncSession = Depends(get_db)):
    u = Unit(tenant_id=ctx.tenant_id, company_id=ctx.company_id, **data.model_dump())
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@router.get("/brands", response_model=list[BrandOut])
async def list_brands(ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(Brand).where(Brand.company_id == ctx.company_id).order_by(Brand.name))).scalars().all()


@router.post("/brands", response_model=BrandOut, status_code=201)
async def create_brand(data: NamedIn, ctx: Ctx = Depends(require("inventory.manage")), db: AsyncSession = Depends(get_db)):
    existing = (await db.execute(select(Brand).where(Brand.company_id == ctx.company_id, func.lower(Brand.name) == data.name.lower()))).scalar_one_or_none()
    if existing:
        return existing
    b = Brand(tenant_id=ctx.tenant_id, company_id=ctx.company_id, name=data.name)
    db.add(b)
    await db.commit()
    await db.refresh(b)
    return b


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(Category).where(Category.company_id == ctx.company_id).order_by(Category.name))).scalars().all()


@router.post("/categories", response_model=CategoryOut, status_code=201)
async def create_category(data: CategoryIn, ctx: Ctx = Depends(require("inventory.manage")), db: AsyncSession = Depends(get_db)):
    c = Category(tenant_id=ctx.tenant_id, company_id=ctx.company_id, **data.model_dump())
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


@router.get("/godowns", response_model=list[GodownOut])
async def list_godowns(ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(Godown).where(Godown.company_id == ctx.company_id, Godown.is_active.is_(True)).order_by(Godown.is_default.desc(), Godown.name))).scalars().all()


@router.post("/godowns", response_model=GodownOut, status_code=201)
async def create_godown(data: GodownIn, ctx: Ctx = Depends(require("inventory.manage")), db: AsyncSession = Depends(get_db)):
    g = Godown(tenant_id=ctx.tenant_id, company_id=ctx.company_id, **data.model_dump())
    if g.branch_id is None:
        g.branch_id = ctx.branch_id
    db.add(g)
    await audit(db, ctx, "create", "godown", None, f"Godown {g.name} created")
    await db.commit()
    await db.refresh(g)
    return g


@router.put("/godowns/{godown_id}", response_model=GodownOut)
async def update_godown(godown_id: uuid.UUID, data: GodownIn, ctx: Ctx = Depends(require("inventory.manage")), db: AsyncSession = Depends(get_db)):
    g = await db.get(Godown, godown_id)
    if not g or g.company_id != ctx.company_id:
        raise HTTPException(404, "Godown not found")
    for k, v in data.model_dump().items():
        setattr(g, k, v)
    await db.commit()
    await db.refresh(g)
    return g


# ------------------------------------------------------------------ products
@router.get("/products", response_model=list[ProductOut])
async def list_products(q: str | None = None, product_type: str | None = None, brand_id: uuid.UUID | None = None, category_id: uuid.UUID | None = None, include_inactive: bool = False, limit: int = Query(500, le=5000), ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    stock = (
        select(StockMovement.product_id, func.coalesce(func.sum(StockMovement.qty), 0).label("q"), func.coalesce(func.sum(StockMovement.value), 0).label("v"))
        .where(StockMovement.company_id == ctx.company_id)
        .group_by(StockMovement.product_id)
        .subquery()
    )
    stmt = select(Product, stock.c.q, stock.c.v).outerjoin(stock, stock.c.product_id == Product.id).where(Product.company_id == ctx.company_id)
    if not include_inactive:
        stmt = stmt.where(Product.is_active.is_(True))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Product.name.ilike(like) | Product.sku.ilike(like) | Product.series.ilike(like) | Product.design.ilike(like) | Product.size.ilike(like) | Product.barcode.ilike(like) | Product.hsn_code.ilike(like))
    if product_type:
        stmt = stmt.where(Product.product_type == product_type)
    if brand_id:
        stmt = stmt.where(Product.brand_id == brand_id)
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    rows = (await db.execute(stmt.order_by(Product.name).limit(limit))).all()
    return [product_out(p, Decimal(q or 0), money(Decimal(v or 0))) for p, q, v in rows]


@router.post("/products", response_model=ProductOut, status_code=201)
async def create_product(data: ProductIn, ctx: Ctx = Depends(require("inventory.manage")), db: AsyncSession = Depends(get_db)):
    dup = (await db.execute(select(Product.id).where(Product.company_id == ctx.company_id, Product.sku == data.sku))).first()
    if dup:
        raise HTTPException(409, f"SKU {data.sku} already exists")
    unit = await db.get(Unit, data.stock_unit_id)
    if not unit or unit.company_id != ctx.company_id:
        raise HTTPException(422, "Unit not found")
    p = Product(tenant_id=ctx.tenant_id, company_id=ctx.company_id, **data.model_dump())
    db.add(p)
    await audit(db, ctx, "create", "product", None, f"Product {p.sku} {p.name} created")
    await db.commit()
    await db.refresh(p)
    return product_out(p, ZERO, ZERO)


@router.get("/products/{product_id}", response_model=ProductOut)
async def get_product(product_id: uuid.UUID, ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    p = await db.get(Product, product_id)
    if not p or p.company_id != ctx.company_id:
        raise HTTPException(404, "Product not found")
    q = await S.balance(db, ctx.company_id, p.id)
    v = Decimal((await db.execute(select(func.coalesce(func.sum(StockMovement.value), 0)).where(StockMovement.product_id == p.id))).scalar_one())
    return product_out(p, q, money(v))


@router.put("/products/{product_id}", response_model=ProductOut)
async def update_product(product_id: uuid.UUID, data: ProductIn, ctx: Ctx = Depends(require("inventory.manage")), db: AsyncSession = Depends(get_db)):
    p = await db.get(Product, product_id)
    if not p or p.company_id != ctx.company_id:
        raise HTTPException(404, "Product not found")
    before = jsonable(p)
    for k, v in data.model_dump().items():
        setattr(p, k, v)
    await audit(db, ctx, "update", "product", p.id, f"Product {p.sku} updated", before=before, after=p)
    await db.commit()
    await db.refresh(p)
    q = await S.balance(db, ctx.company_id, p.id)
    return product_out(p, q, None)


@router.get("/products/{product_id}/stock")
async def product_stock(product_id: uuid.UUID, ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    p = await db.get(Product, product_id)
    if not p or p.company_id != ctx.company_id:
        raise HTTPException(404, "Product not found")
    rows = await S.stock_by_godown_batch(db, ctx.company_id, product_id)
    total = sum((r["qty"] for r in rows), ZERO)
    return {"product_id": product_id, "total_qty": total, "avg_cost": await S.avg_cost(db, ctx.company_id, product_id), "rows": rows}


@router.post("/convert-units")
async def convert(data: UnitConvertIn, ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    p = await db.get(Product, data.product_id)
    if not p or p.company_id != ctx.company_id:
        raise HTTPException(404, "Product not found")
    return {"qty": convert_units(p, data.qty, data.from_unit, data.to_unit), "from_unit": data.from_unit, "to_unit": data.to_unit}


# ------------------------------------------------------------------ batches
@router.get("/batches", response_model=list[BatchOut])
async def list_batches(product_id: uuid.UUID, godown_id: uuid.UUID | None = None, ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Batch).where(Batch.company_id == ctx.company_id, Batch.product_id == product_id).order_by(Batch.batch_no))).scalars().all()
    out = []
    for b in rows:
        o = BatchOut.model_validate(b)
        o.qty = await S.balance(db, ctx.company_id, product_id, godown_id, b.id)
        out.append(o)
    return out


@router.post("/batches", response_model=BatchOut, status_code=201)
async def create_batch(data: BatchIn, ctx: Ctx = Depends(require("inventory.manage")), db: AsyncSession = Depends(get_db)):
    p = await db.get(Product, data.product_id)
    if not p or p.company_id != ctx.company_id:
        raise HTTPException(404, "Product not found")
    existing = (await db.execute(select(Batch).where(Batch.product_id == data.product_id, Batch.batch_no == data.batch_no, Batch.shade == data.shade, Batch.calibre == data.calibre))).scalar_one_or_none()
    if existing:
        o = BatchOut.model_validate(existing)
        o.qty = await S.balance(db, ctx.company_id, p.id, None, existing.id)
        return o
    b = Batch(tenant_id=ctx.tenant_id, company_id=ctx.company_id, **data.model_dump())
    db.add(b)
    await db.commit()
    await db.refresh(b)
    o = BatchOut.model_validate(b)
    o.qty = ZERO
    return o


# ------------------------------------------------------------------ stock journals (adjustment / transfer / opening)
@router.get("/stock-journals", response_model=list[StockJournalOut])
async def list_journals(journal_type: str | None = None, limit: int = Query(100, le=500), ctx: Ctx = Depends(require("inventory.view")), db: AsyncSession = Depends(get_db)):
    stmt = select(StockJournal).where(StockJournal.company_id == ctx.company_id)
    if journal_type:
        stmt = stmt.where(StockJournal.journal_type == journal_type)
    return (await db.execute(stmt.order_by(StockJournal.date.desc(), StockJournal.created_at.desc()).limit(limit))).scalars().all()


@router.post("/stock-journals", response_model=StockJournalOut, status_code=201)
async def create_journal(data: StockJournalIn, ctx: Ctx = Depends(require("inventory.post")), db: AsyncSession = Depends(get_db)):
    if data.idempotency_key:
        pass
    fy = await get_fiscal_year(db, ctx.company_id, data.date)
    if data.journal_type == "transfer":
        if not data.from_godown_id or not data.to_godown_id or data.from_godown_id == data.to_godown_id:
            raise HTTPException(422, "Transfer needs distinct source and destination godowns")
    default_g = await S.default_godown(db, ctx.company_id, ctx.branch_id)
    j = StockJournal(tenant_id=ctx.tenant_id, company_id=ctx.company_id, branch_id=ctx.branch_id, journal_type=data.journal_type, doc_no=await next_number(db, ctx.tenant_id, ctx.company_id, data.journal_type, fy), date=data.date, from_godown_id=data.from_godown_id, to_godown_id=data.to_godown_id, reason=data.reason, created_by=ctx.user_id, lines=[])
    db.add(j)
    await db.flush()
    total_value = ZERO
    stored_lines = []
    for l in data.lines:
        p = await db.get(Product, l.product_id)
        if not p or p.company_id != ctx.company_id:
            raise HTTPException(422, "Product not found")
        if data.journal_type == "transfer":
            if l.qty <= ZERO:
                raise HTTPException(422, "Transfer quantities must be positive")
            rate = await S.avg_cost(db, ctx.company_id, p.id)
            await S.add_movement(db, ctx, product=p, godown_id=data.from_godown_id, on=data.date, movement_type="transfer_out", quantity=-l.qty, rate=rate, batch_id=l.batch_id, doc_type="stock_journal", doc_id=j.id, narration=f"{j.doc_no} {l.narration or ''}")
            await S.add_movement(db, ctx, product=p, godown_id=data.to_godown_id, on=data.date, movement_type="transfer_in", quantity=l.qty, rate=rate, batch_id=l.batch_id, doc_type="stock_journal", doc_id=j.id, narration=f"{j.doc_no} {l.narration or ''}")
            value = money(l.qty * rate)
        else:
            gid = l.godown_id or data.to_godown_id or data.from_godown_id or default_g.id
            if l.qty == ZERO:
                raise HTTPException(422, "Quantity cannot be zero")
            if l.qty > ZERO:
                rate = l.rate if l.rate is not None else (p.purchase_price or await S.avg_cost(db, ctx.company_id, p.id))
                mtype = "opening" if data.journal_type == "opening" else "adjustment_in"
            else:
                rate = await S.avg_cost(db, ctx.company_id, p.id)
                mtype = "adjustment_out"
            await S.add_movement(db, ctx, product=p, godown_id=gid, on=data.date, movement_type=mtype, quantity=l.qty, rate=rate, batch_id=l.batch_id, doc_type="stock_journal", doc_id=j.id, narration=f"{j.doc_no} {data.reason or ''}")
            value = money(l.qty * rate)
            total_value += value
        stored_lines.append({"product_id": str(p.id), "product_name": p.name, "sku": p.sku, "batch_id": str(l.batch_id) if l.batch_id else None, "godown_id": str(l.godown_id) if l.godown_id else None, "qty": str(qty(l.qty)), "unit": p.stock_unit.symbol, "rate": str(rate), "value": str(value), "narration": l.narration})
    j.lines = stored_lines
    j.total_value = money(total_value)
    # accounting effect for adjustments/opening (transfers have none)
    if data.journal_type != "transfer" and total_value != ZERO:
        await assert_period_open(db, ctx.company_id, data.date)
        inv = await get_system_ledger(db, ctx.company_id, "inventory")
        counter = await get_system_ledger(db, ctx.company_id, "capital" if data.journal_type == "opening" else "stock_adjustment")
        if total_value > ZERO:
            lines = [LineSpec(inv.id, debit=total_value), LineSpec(counter.id, credit=total_value)]
        else:
            lines = [LineSpec(counter.id, debit=-total_value), LineSpec(inv.id, credit=-total_value)]
        v = await post_voucher(db, ctx, voucher_type="journal", on=data.date, lines=lines, narration=f"Stock {data.journal_type} {j.doc_no}: {data.reason or ''}", reference_type="stock_journal", reference_id=j.id, number_type="stock_journal")
        j.voucher_id = v.id
    await audit(db, ctx, "post", "stock_journal", j.id, f"{data.journal_type} {j.doc_no} posted ({len(stored_lines)} lines, value {j.total_value})")
    await db.commit()
    await db.refresh(j)
    return j


# ------------------------------------------------------------------ reservations & samples
@router.get("/reservations", response_model=list[ReservationOut])
async def list_reservations(product_id: uuid.UUID | None = None, status: str = "active", ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    stmt = select(StockReservation).where(StockReservation.company_id == ctx.company_id)
    if product_id:
        stmt = stmt.where(StockReservation.product_id == product_id)
    if status:
        stmt = stmt.where(StockReservation.status == status)
    return (await db.execute(stmt.order_by(StockReservation.created_at.desc()))).scalars().all()


@router.post("/reservations", response_model=ReservationOut, status_code=201)
async def create_reservation(data: ReservationIn, ctx: Ctx = Depends(require("inventory.post")), db: AsyncSession = Depends(get_db)):
    available = await S.balance(db, ctx.company_id, data.product_id, data.godown_id, data.batch_id)
    reserved = await S.reserved_qty(db, ctx.company_id, data.product_id, data.godown_id, data.batch_id)
    if data.qty > available - reserved:
        raise HTTPException(422, f"Only {(available - reserved).normalize()} available to reserve")
    r = StockReservation(tenant_id=ctx.tenant_id, company_id=ctx.company_id, **data.model_dump())
    db.add(r)
    await audit(db, ctx, "create", "reservation", None, f"Reserved {data.qty} for {data.reference or 'party'}")
    await db.commit()
    await db.refresh(r)
    return r


@router.post("/reservations/{res_id}/release", response_model=ReservationOut)
async def release_reservation(res_id: uuid.UUID, consumed: bool = False, ctx: Ctx = Depends(require("inventory.post")), db: AsyncSession = Depends(get_db)):
    r = await db.get(StockReservation, res_id)
    if not r or r.company_id != ctx.company_id:
        raise HTTPException(404, "Reservation not found")
    r.status = "consumed" if consumed else "released"
    await db.commit()
    await db.refresh(r)
    return r


@router.get("/samples", response_model=list[SampleOut])
async def list_samples(status: str | None = None, ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    stmt = select(SampleIssue).where(SampleIssue.company_id == ctx.company_id)
    if status:
        stmt = stmt.where(SampleIssue.status == status)
    return (await db.execute(stmt.order_by(SampleIssue.issued_on.desc()))).scalars().all()


@router.post("/samples", response_model=SampleOut, status_code=201)
async def issue_sample(data: SampleIn, ctx: Ctx = Depends(require("inventory.post")), db: AsyncSession = Depends(get_db)):
    s = SampleIssue(tenant_id=ctx.tenant_id, company_id=ctx.company_id, **data.model_dump())
    db.add(s)
    await audit(db, ctx, "create", "sample", None, f"Sample issued qty {data.qty}")
    await db.commit()
    await db.refresh(s)
    return s


@router.post("/samples/{sample_id}/status", response_model=SampleOut)
async def sample_status(sample_id: uuid.UUID, status: str = Query(pattern="^(returned|lost|converted)$"), ctx: Ctx = Depends(require("inventory.post")), db: AsyncSession = Depends(get_db)):
    from datetime import date as _d

    s = await db.get(SampleIssue, sample_id)
    if not s or s.company_id != ctx.company_id:
        raise HTTPException(404, "Sample not found")
    s.status = status
    if status == "returned":
        s.returned_on = _d.today()
    await db.commit()
    await db.refresh(s)
    return s
