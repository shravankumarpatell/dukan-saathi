from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..deps import PERMISSIONS, Ctx, get_ctx, require
from ..models import AuditLog, Branch, Company, FiscalYear, Role, Setting, User
from ..schemas import AuditOut, BranchIn, BranchOut, CompanyIn, CompanyOut, FiscalYearIn, FiscalYearOut, LockPeriodIn, RoleIn, RoleOut, SettingIn, UserIn, UserOut
from ..security import hash_password
from ..services.coa import setup_company_defaults
from ..services.common import audit, jsonable

router = APIRouter(prefix="/settings", tags=["settings"])


# ------------------------------------------------------------------ company
@router.get("/company", response_model=CompanyOut)
async def get_company(ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    return await db.get(Company, ctx.company_id)


@router.put("/company", response_model=CompanyOut)
async def update_company(data: CompanyIn, ctx: Ctx = Depends(require("settings.manage")), db: AsyncSession = Depends(get_db)):
    c = await db.get(Company, ctx.company_id)
    before = jsonable(c)
    for k, v in data.model_dump().items():
        setattr(c, k, v)
    await audit(db, ctx, "update", "company", c.id, f"Company {c.name} updated", before=before, after=c)
    await db.commit()
    await db.refresh(c)
    return c


@router.post("/companies", response_model=CompanyOut, status_code=201)
async def create_company(data: CompanyIn, ctx: Ctx = Depends(require("settings.manage")), db: AsyncSession = Depends(get_db)):
    c = Company(tenant_id=ctx.tenant_id, **data.model_dump())
    db.add(c)
    await db.flush()
    b = Branch(tenant_id=ctx.tenant_id, company_id=c.id, name="Head Office", code="HO", is_default=True, state_code=c.state_code, gstin=c.gstin)
    db.add(b)
    await db.flush()
    await setup_company_defaults(db, ctx.tenant_id, c.id, b.id, c.fy_start_month)
    await audit(db, ctx, "create", "company", c.id, f"Company {c.name} created")
    await db.commit()
    await db.refresh(c)
    return c


# ------------------------------------------------------------------ branches
@router.get("/branches", response_model=list[BranchOut])
async def list_branches(ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(Branch).where(Branch.company_id == ctx.company_id).order_by(Branch.is_default.desc(), Branch.name))).scalars().all()


@router.post("/branches", response_model=BranchOut, status_code=201)
async def create_branch(data: BranchIn, ctx: Ctx = Depends(require("settings.manage")), db: AsyncSession = Depends(get_db)):
    b = Branch(tenant_id=ctx.tenant_id, company_id=ctx.company_id, **data.model_dump())
    db.add(b)
    await audit(db, ctx, "create", "branch", None, f"Branch {b.name} created")
    await db.commit()
    await db.refresh(b)
    return b


@router.put("/branches/{branch_id}", response_model=BranchOut)
async def update_branch(branch_id: uuid.UUID, data: BranchIn, ctx: Ctx = Depends(require("settings.manage")), db: AsyncSession = Depends(get_db)):
    b = await db.get(Branch, branch_id)
    if not b or b.company_id != ctx.company_id:
        raise HTTPException(404, "Branch not found")
    for k, v in data.model_dump().items():
        setattr(b, k, v)
    await audit(db, ctx, "update", "branch", b.id, f"Branch {b.name} updated")
    await db.commit()
    await db.refresh(b)
    return b


# ------------------------------------------------------------------ roles / permissions
@router.get("/permissions")
async def list_permissions(ctx: Ctx = Depends(get_ctx)):
    return [{"key": k, "label": v} for k, v in PERMISSIONS.items()]


@router.get("/roles", response_model=list[RoleOut])
async def list_roles(ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(Role).where(Role.tenant_id == ctx.tenant_id).order_by(Role.name))).scalars().all()


@router.post("/roles", response_model=RoleOut, status_code=201)
async def create_role(data: RoleIn, ctx: Ctx = Depends(require("settings.manage")), db: AsyncSession = Depends(get_db)):
    bad = [p for p in data.permissions if p not in PERMISSIONS and not p.endswith(".*")]
    if bad:
        raise HTTPException(422, f"Unknown permissions: {bad}")
    r = Role(tenant_id=ctx.tenant_id, **data.model_dump())
    db.add(r)
    await audit(db, ctx, "create", "role", None, f"Role {r.name} created")
    await db.commit()
    await db.refresh(r)
    return r


@router.put("/roles/{role_id}", response_model=RoleOut)
async def update_role(role_id: uuid.UUID, data: RoleIn, ctx: Ctx = Depends(require("settings.manage")), db: AsyncSession = Depends(get_db)):
    r = await db.get(Role, role_id)
    if not r or r.tenant_id != ctx.tenant_id:
        raise HTTPException(404, "Role not found")
    if r.is_system and r.name == "Owner":
        raise HTTPException(422, "Owner role cannot be modified")
    before = jsonable(r)
    for k, v in data.model_dump().items():
        setattr(r, k, v)
    await audit(db, ctx, "update", "role", r.id, f"Role {r.name} updated", before=before, after=r)
    await db.commit()
    await db.refresh(r)
    return r


# ------------------------------------------------------------------ users
@router.get("/users", response_model=list[UserOut])
async def list_users(ctx: Ctx = Depends(require("settings.manage")), db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(User).where(User.tenant_id == ctx.tenant_id).order_by(User.full_name))).scalars().all()


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(data: UserIn, ctx: Ctx = Depends(require("settings.manage")), db: AsyncSession = Depends(get_db)):
    if not data.password:
        raise HTTPException(422, "Password required for new users")
    role = await db.get(Role, data.role_id)
    if not role or role.tenant_id != ctx.tenant_id:
        raise HTTPException(422, "Role not found")
    exists = (await db.execute(select(User.id).where(User.tenant_id == ctx.tenant_id, User.email == data.email.lower()))).first()
    if exists:
        raise HTTPException(409, "A user with this email already exists")
    u = User(tenant_id=ctx.tenant_id, email=data.email.lower(), full_name=data.full_name, phone=data.phone, password_hash=hash_password(data.password), role_id=data.role_id, default_company_id=data.default_company_id or ctx.company_id, default_branch_id=data.default_branch_id or ctx.branch_id, is_active=data.is_active)
    db.add(u)
    await audit(db, ctx, "create", "user", None, f"User {u.email} created with role {role.name}")
    await db.commit()
    await db.refresh(u)
    return u


@router.put("/users/{user_id}", response_model=UserOut)
async def update_user(user_id: uuid.UUID, data: UserIn, ctx: Ctx = Depends(require("settings.manage")), db: AsyncSession = Depends(get_db)):
    u = await db.get(User, user_id)
    if not u or u.tenant_id != ctx.tenant_id:
        raise HTTPException(404, "User not found")
    if u.is_owner and not data.is_active:
        raise HTTPException(422, "Owner cannot be deactivated")
    u.email, u.full_name, u.phone, u.role_id, u.is_active = data.email.lower(), data.full_name, data.phone, data.role_id, data.is_active
    u.default_company_id = data.default_company_id or u.default_company_id
    u.default_branch_id = data.default_branch_id or u.default_branch_id
    if data.password:
        u.password_hash = hash_password(data.password)
    await audit(db, ctx, "update", "user", u.id, f"User {u.email} updated")
    await db.commit()
    await db.refresh(u)
    return u


# ------------------------------------------------------------------ fiscal years
@router.get("/fiscal-years", response_model=list[FiscalYearOut])
async def list_fy(ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(FiscalYear).where(FiscalYear.company_id == ctx.company_id).order_by(FiscalYear.start_date.desc()))).scalars().all()


@router.post("/fiscal-years", response_model=FiscalYearOut, status_code=201)
async def create_fy(data: FiscalYearIn, ctx: Ctx = Depends(require("settings.manage")), db: AsyncSession = Depends(get_db)):
    if data.end_date <= data.start_date:
        raise HTTPException(422, "End date must be after start date")
    overlap = (await db.execute(select(FiscalYear).where(FiscalYear.company_id == ctx.company_id, FiscalYear.start_date <= data.end_date, FiscalYear.end_date >= data.start_date))).first()
    if overlap:
        raise HTTPException(422, "Overlaps an existing fiscal year")
    fy = FiscalYear(tenant_id=ctx.tenant_id, company_id=ctx.company_id, **data.model_dump())
    db.add(fy)
    await audit(db, ctx, "create", "fiscal_year", None, f"Fiscal year {fy.name} created")
    await db.commit()
    await db.refresh(fy)
    return fy


@router.post("/fiscal-years/{fy_id}/lock", response_model=FiscalYearOut)
async def lock_period(fy_id: uuid.UUID, data: LockPeriodIn, ctx: Ctx = Depends(require("settings.manage")), db: AsyncSession = Depends(get_db)):
    fy = await db.get(FiscalYear, fy_id)
    if not fy or fy.company_id != ctx.company_id:
        raise HTTPException(404, "Fiscal year not found")
    if data.locked_till and not (fy.start_date <= data.locked_till <= fy.end_date):
        raise HTTPException(422, "Lock date must be within the fiscal year")
    fy.locked_till = data.locked_till
    await audit(db, ctx, "lock", "fiscal_year", fy.id, f"{fy.name} locked till {data.locked_till}")
    await db.commit()
    await db.refresh(fy)
    return fy


@router.post("/fiscal-years/{fy_id}/close", response_model=FiscalYearOut)
async def close_fy(fy_id: uuid.UUID, reopen: bool = False, ctx: Ctx = Depends(require("settings.manage")), db: AsyncSession = Depends(get_db)):
    fy = await db.get(FiscalYear, fy_id)
    if not fy or fy.company_id != ctx.company_id:
        raise HTTPException(404, "Fiscal year not found")
    fy.is_closed = not reopen
    await audit(db, ctx, "reopen" if reopen else "close", "fiscal_year", fy.id, f"{fy.name} {'reopened' if reopen else 'closed'}")
    await db.commit()
    await db.refresh(fy)
    return fy


# ------------------------------------------------------------------ audit log
@router.get("/audit-log")
async def audit_log(page: int = 1, page_size: int = Query(50, le=200), entity_type: str | None = None, action: str | None = None, q: str | None = None, ctx: Ctx = Depends(require("audit.view")), db: AsyncSession = Depends(get_db)):
    stmt = select(AuditLog).where(AuditLog.tenant_id == ctx.tenant_id, (AuditLog.company_id == ctx.company_id) | (AuditLog.company_id.is_(None)))
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if q:
        stmt = stmt.where(AuditLog.summary.ilike(f"%{q}%") | AuditLog.user_email.ilike(f"%{q}%"))
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await db.execute(stmt.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return {"items": [AuditOut.model_validate(r) for r in rows], "total": total, "page": page, "page_size": page_size}


# ------------------------------------------------------------------ key/value settings
@router.get("/kv")
async def list_settings(ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Setting).where(Setting.company_id == ctx.company_id))).scalars().all()
    return {r.key: r.value for r in rows}


@router.put("/kv")
async def put_setting(data: SettingIn, ctx: Ctx = Depends(require("settings.manage")), db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(Setting).where(Setting.company_id == ctx.company_id, Setting.key == data.key))).scalar_one_or_none()
    if row:
        row.value = data.value
    else:
        db.add(Setting(tenant_id=ctx.tenant_id, company_id=ctx.company_id, key=data.key, value=data.value))
    await audit(db, ctx, "update", "setting", data.key, f"Setting {data.key} updated")
    await db.commit()
    return {"ok": True}
