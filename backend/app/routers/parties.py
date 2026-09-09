from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..deps import Ctx, get_ctx, require
from ..models import AccountGroup, Bill, Ledger, Party, Project
from ..schemas import PartyIn, PartyOut, ProjectIn, ProjectOut
from ..services.common import ZERO, audit, jsonable, money
from ..services.trade import party_outstanding

router = APIRouter(prefix="/parties", tags=["parties"])


async def _ensure_ledger(db: AsyncSession, ctx: Ctx, party: Party, opening: PartyIn | None = None) -> Ledger:
    gcode = "CREDITORS" if party.party_type == "supplier" else "DEBTORS"
    group = (await db.execute(select(AccountGroup).where(AccountGroup.company_id == ctx.company_id, AccountGroup.code == gcode))).scalar_one()
    ledger = await db.get(Ledger, party.ledger_id) if party.ledger_id else None
    if ledger is None:
        name = party.name
        dup = (await db.execute(select(Ledger).where(Ledger.company_id == ctx.company_id, Ledger.name == name))).scalar_one_or_none()
        if dup and dup.party_id not in (None, party.id):
            name = f"{party.name} ({party.code or party.party_type})"
        ledger = Ledger(tenant_id=ctx.tenant_id, company_id=ctx.company_id, name=name, group_id=group.id, party_id=party.id)
        db.add(ledger)
        await db.flush()
        party.ledger_id = ledger.id
    else:
        ledger.name = party.name if ledger.name.startswith(party.name) or True else ledger.name
        ledger.group_id = group.id
    if opening is not None:
        ledger.opening_balance = money(opening.opening_balance)
        ledger.opening_type = opening.opening_type
    return ledger


async def _out(db: AsyncSession, ctx: Ctx, p: Party) -> PartyOut:
    o = PartyOut.model_validate(p)
    kind = "payable" if p.party_type == "supplier" else "receivable"
    o.outstanding = await party_outstanding(db, ctx.company_id, p.id, kind)
    if p.ledger_id:
        led = await db.get(Ledger, p.ledger_id)
        if led and led.opening_balance:
            sign = 1 if led.opening_type == "dr" else -1
            if kind == "payable":
                sign = -sign
            o.outstanding = money(o.outstanding + sign * led.opening_balance)
    return o


@router.get("", response_model=list[PartyOut])
async def list_parties(party_type: str | None = None, q: str | None = None, include_inactive: bool = False, limit: int = Query(500, le=2000), ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    stmt = select(Party).where(Party.company_id == ctx.company_id)
    if party_type == "customer":
        stmt = stmt.where(Party.party_type.in_(("customer", "both")))
    elif party_type == "supplier":
        stmt = stmt.where(Party.party_type.in_(("supplier", "both")))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Party.name.ilike(like) | Party.phone.ilike(like) | Party.gstin.ilike(like) | Party.city.ilike(like))
    if not include_inactive:
        stmt = stmt.where(Party.is_active.is_(True))
    rows = (await db.execute(stmt.order_by(Party.name).limit(limit))).scalars().all()
    # batch outstanding
    bills = (await db.execute(select(Bill).where(Bill.company_id == ctx.company_id))).scalars().all()
    per_party: dict[uuid.UUID, dict] = {}
    for b in bills:
        bal = b.amount - sum((s.amount for s in b.settlements), ZERO)
        per_party.setdefault(b.party_id, {"receivable": ZERO, "payable": ZERO})[b.kind] += bal
    ledgers = {l.party_id: l for l in (await db.execute(select(Ledger).where(Ledger.company_id == ctx.company_id, Ledger.party_id.is_not(None)))).scalars().all()}
    out = []
    for p in rows:
        o = PartyOut.model_validate(p)
        kind = "payable" if p.party_type == "supplier" else "receivable"
        val = per_party.get(p.id, {}).get(kind, ZERO)
        led = ledgers.get(p.id)
        if led and led.opening_balance:
            sign = 1 if led.opening_type == "dr" else -1
            if kind == "payable":
                sign = -sign
            val += sign * led.opening_balance
        o.outstanding = money(val)
        out.append(o)
    return out


@router.post("", response_model=PartyOut, status_code=201)
async def create_party(data: PartyIn, ctx: Ctx = Depends(require("parties.manage")), db: AsyncSession = Depends(get_db)):
    payload = data.model_dump(exclude={"opening_balance", "opening_type"})
    p = Party(tenant_id=ctx.tenant_id, company_id=ctx.company_id, **payload)
    db.add(p)
    await db.flush()
    await _ensure_ledger(db, ctx, p, data)
    await audit(db, ctx, "create", "party", p.id, f"{p.party_type.title()} {p.name} created")
    await db.commit()
    await db.refresh(p)
    return await _out(db, ctx, p)


@router.get("/{party_id}", response_model=PartyOut)
async def get_party(party_id: uuid.UUID, ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    p = await db.get(Party, party_id)
    if not p or p.company_id != ctx.company_id:
        raise HTTPException(404, "Party not found")
    return await _out(db, ctx, p)


@router.put("/{party_id}", response_model=PartyOut)
async def update_party(party_id: uuid.UUID, data: PartyIn, ctx: Ctx = Depends(require("parties.manage")), db: AsyncSession = Depends(get_db)):
    p = await db.get(Party, party_id)
    if not p or p.company_id != ctx.company_id:
        raise HTTPException(404, "Party not found")
    before = jsonable(p)
    for k, v in data.model_dump(exclude={"opening_balance", "opening_type"}).items():
        setattr(p, k, v)
    await _ensure_ledger(db, ctx, p, data)
    await audit(db, ctx, "update", "party", p.id, f"{p.name} updated", before=before, after=p)
    await db.commit()
    await db.refresh(p)
    return await _out(db, ctx, p)


# ------------------------------------------------------------------ projects
@router.get("/projects/all", response_model=list[ProjectOut])
async def list_projects(party_id: uuid.UUID | None = None, ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    stmt = select(Project).where(Project.company_id == ctx.company_id)
    if party_id:
        stmt = stmt.where(Project.party_id == party_id)
    return (await db.execute(stmt.order_by(Project.created_at.desc()))).scalars().all()


@router.post("/projects", response_model=ProjectOut, status_code=201)
async def create_project(data: ProjectIn, ctx: Ctx = Depends(require("parties.manage")), db: AsyncSession = Depends(get_db)):
    pr = Project(tenant_id=ctx.tenant_id, company_id=ctx.company_id, **data.model_dump())
    db.add(pr)
    await audit(db, ctx, "create", "project", None, f"Project {pr.name} created")
    await db.commit()
    await db.refresh(pr)
    return pr


@router.put("/projects/{project_id}", response_model=ProjectOut)
async def update_project(project_id: uuid.UUID, data: ProjectIn, ctx: Ctx = Depends(require("parties.manage")), db: AsyncSession = Depends(get_db)):
    pr = await db.get(Project, project_id)
    if not pr or pr.company_id != ctx.company_id:
        raise HTTPException(404, "Project not found")
    for k, v in data.model_dump().items():
        setattr(pr, k, v)
    await db.commit()
    await db.refresh(pr)
    return pr
