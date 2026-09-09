from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..deps import Ctx, require
from ..services import reports as R
from ..services.stock import stock_summary

router = APIRouter(prefix="/reports", tags=["reports"])


def _fy_start(today: date) -> date:
    return date(today.year if today.month >= 4 else today.year - 1, 4, 1)


@router.get("/dashboard")
async def dashboard(ctx: Ctx = Depends(require("reports.view")), db: AsyncSession = Depends(get_db)):
    return await R.dashboard(db, ctx.company_id)


@router.get("/trial-balance")
async def trial_balance(from_date: date | None = None, to_date: date | None = None, ctx: Ctx = Depends(require("reports.view")), db: AsyncSession = Depends(get_db)):
    to_date = to_date or date.today()
    from_date = from_date or _fy_start(to_date)
    return await R.trial_balance(db, ctx.company_id, from_date, to_date)


@router.get("/profit-loss")
async def profit_loss(from_date: date | None = None, to_date: date | None = None, ctx: Ctx = Depends(require("reports.view")), db: AsyncSession = Depends(get_db)):
    to_date = to_date or date.today()
    from_date = from_date or _fy_start(to_date)
    return await R.profit_loss(db, ctx.company_id, from_date, to_date)


@router.get("/balance-sheet")
async def balance_sheet(as_of: date | None = None, ctx: Ctx = Depends(require("reports.view")), db: AsyncSession = Depends(get_db)):
    return await R.balance_sheet(db, ctx.company_id, as_of or date.today())


@router.get("/ledger/{ledger_id}")
async def ledger_statement(ledger_id: uuid.UUID, from_date: date | None = None, to_date: date | None = None, ctx: Ctx = Depends(require("accounting.view")), db: AsyncSession = Depends(get_db)):
    to_date = to_date or date.today()
    from_date = from_date or _fy_start(to_date)
    return await R.ledger_statement(db, ctx.company_id, ledger_id, from_date, to_date)


@router.get("/day-book")
async def day_book(from_date: date | None = None, to_date: date | None = None, voucher_type: str | None = None, ctx: Ctx = Depends(require("accounting.view")), db: AsyncSession = Depends(get_db)):
    to_date = to_date or date.today()
    from_date = from_date or to_date
    return await R.day_book(db, ctx.company_id, from_date, to_date, voucher_type)


@router.get("/outstanding")
async def outstanding(kind: str = Query("receivable", pattern="^(receivable|payable)$"), as_of: date | None = None, party_id: uuid.UUID | None = None, ctx: Ctx = Depends(require("reports.view")), db: AsyncSession = Depends(get_db)):
    return await R.outstanding(db, ctx.company_id, kind, as_of, party_id)


@router.get("/stock-summary")
async def stock_summary_report(godown_id: uuid.UUID | None = None, as_of: date | None = None, q: str | None = None, low_only: bool = False, ctx: Ctx = Depends(require("inventory.view")), db: AsyncSession = Depends(get_db)):
    return await stock_summary(db, ctx.company_id, godown_id, as_of, q, low_only)


@router.get("/stock-ledger/{product_id}")
async def stock_ledger(product_id: uuid.UUID, from_date: date | None = None, to_date: date | None = None, godown_id: uuid.UUID | None = None, ctx: Ctx = Depends(require("inventory.view")), db: AsyncSession = Depends(get_db)):
    return await R.stock_ledger(db, ctx.company_id, product_id, from_date, to_date, godown_id)


@router.get("/gst-summary")
async def gst_summary(from_date: date | None = None, to_date: date | None = None, ctx: Ctx = Depends(require("gst.view")), db: AsyncSession = Depends(get_db)):
    to_date = to_date or date.today()
    from_date = from_date or to_date.replace(day=1)
    return await R.gst_summary(db, ctx.company_id, from_date, to_date)


@router.get("/dead-stock")
async def dead_stock(days: int = Query(90, ge=7, le=730), ctx: Ctx = Depends(require("inventory.view")), db: AsyncSession = Depends(get_db)):
    return await R.dead_stock(db, ctx.company_id, days)
