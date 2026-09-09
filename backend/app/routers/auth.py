from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import get_db
from ..deps import Ctx, get_ctx, get_current_user
from ..models import Branch, Company, RefreshToken, Tenant, User
from ..schemas import BranchOut, ChangePasswordIn, CompanyOut, LoginIn, MeOut, RefreshIn, RoleOut, TokenOut, UserOut
from ..security import create_access_token, hash_password, hash_token, new_refresh_token, verify_password
from ..services.common import audit, now

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


async def _issue_tokens(db: AsyncSession, user: User, company_id: uuid.UUID | None, branch_id: uuid.UUID | None, device_id: str | None) -> TokenOut:
    perms = ["*"] if user.is_owner else list(user.role.permissions or [])
    access = create_access_token(user_id=user.id, tenant_id=user.tenant_id, company_id=company_id, branch_id=branch_id, role=user.role.name, perms=perms, email=user.email)
    raw, h, exp = new_refresh_token()
    db.add(RefreshToken(tenant_id=user.tenant_id, user_id=user.id, token_hash=h, device_id=device_id, expires_at=exp, created_at=now()))
    return TokenOut(access_token=access, refresh_token=raw, expires_in=settings.access_token_minutes * 60)


@router.post("/login", response_model=TokenOut)
async def login(data: LoginIn, request: Request, db: AsyncSession = Depends(get_db)):
    stmt = select(User).where(User.email == data.email.lower())
    if data.tenant_slug:
        stmt = stmt.join(Tenant, Tenant.id == User.tenant_id).where(Tenant.slug == data.tenant_slug)
    users = (await db.execute(stmt)).scalars().all()
    user = next((u for u in users if verify_password(data.password, u.password_hash)), None)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User is disabled")
    tenant = await db.get(Tenant, user.tenant_id)
    if not tenant or not tenant.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Tenant is disabled")
    company_id = user.default_company_id
    if company_id is None:
        c = (await db.execute(select(Company).where(Company.tenant_id == user.tenant_id).order_by(Company.created_at).limit(1))).scalar_one_or_none()
        company_id = c.id if c else None
    branch_id = user.default_branch_id
    if branch_id is None and company_id:
        b = (await db.execute(select(Branch).where(Branch.company_id == company_id).order_by(Branch.is_default.desc()).limit(1))).scalar_one_or_none()
        branch_id = b.id if b else None
    user.last_login_at = now()
    tokens = await _issue_tokens(db, user, company_id, branch_id, data.device_id)
    await audit(db, None, "login", "user", user.id, f"{user.email} logged in", tenant_id=user.tenant_id, company_id=company_id)
    await db.commit()
    return tokens


@router.post("/refresh", response_model=TokenOut)
async def refresh(data: RefreshIn, db: AsyncSession = Depends(get_db)):
    h = hash_token(data.refresh_token)
    rt = (await db.execute(select(RefreshToken).where(RefreshToken.token_hash == h))).scalar_one_or_none()
    if not rt or rt.revoked_at or rt.expires_at < now():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token invalid or expired")
    user = await db.get(User, rt.user_id)
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User inactive")
    rt.revoked_at = now()  # rotation
    tokens = await _issue_tokens(db, user, user.default_company_id, user.default_branch_id, rt.device_id)
    await db.commit()
    return tokens


@router.post("/logout", status_code=204)
async def logout(data: RefreshIn, db: AsyncSession = Depends(get_db)):
    rt = (await db.execute(select(RefreshToken).where(RefreshToken.token_hash == hash_token(data.refresh_token)))).scalar_one_or_none()
    if rt and not rt.revoked_at:
        rt.revoked_at = now()
        await db.commit()
    return None


@router.get("/me", response_model=MeOut)
async def me(auth=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user, payload = auth
    tenant = await db.get(Tenant, user.tenant_id)
    companies = (await db.execute(select(Company).where(Company.tenant_id == user.tenant_id, Company.is_active.is_(True)).order_by(Company.name))).scalars().all()
    branches = (await db.execute(select(Branch).where(Branch.tenant_id == user.tenant_id, Branch.is_active.is_(True)).order_by(Branch.name))).scalars().all()
    perms = ["*"] if user.is_owner else list(user.role.permissions or [])
    cid = uuid.UUID(payload["cid"]) if payload.get("cid") else user.default_company_id
    bid = uuid.UUID(payload["bid"]) if payload.get("bid") else user.default_branch_id
    return MeOut(
        user=UserOut.model_validate(user),
        role=RoleOut.model_validate(user.role),
        permissions=perms,
        tenant={"id": str(tenant.id), "name": tenant.name, "slug": tenant.slug, "plan": tenant.plan},
        companies=[CompanyOut.model_validate(c) for c in companies],
        branches=[BranchOut.model_validate(b) for b in branches],
        current_company_id=cid,
        current_branch_id=bid,
    )


@router.post("/switch", response_model=TokenOut)
async def switch_context(company_id: uuid.UUID, branch_id: uuid.UUID | None = None, auth=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user, _ = auth
    company = await db.get(Company, company_id)
    if not company or company.tenant_id != user.tenant_id:
        raise HTTPException(403, "Company not accessible")
    if branch_id:
        b = await db.get(Branch, branch_id)
        if not b or b.company_id != company_id:
            raise HTTPException(403, "Branch not in company")
    else:
        b = (await db.execute(select(Branch).where(Branch.company_id == company_id).order_by(Branch.is_default.desc()).limit(1))).scalar_one_or_none()
        branch_id = b.id if b else None
    tokens = await _issue_tokens(db, user, company_id, branch_id, None)
    await db.commit()
    return tokens


@router.post("/change-password", status_code=204)
async def change_password(data: ChangePasswordIn, ctx: Ctx = Depends(get_ctx), db: AsyncSession = Depends(get_db)):
    if not verify_password(data.current_password, ctx.user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    ctx.user.password_hash = hash_password(data.new_password)
    await audit(db, ctx, "update", "user", ctx.user.id, "Password changed")
    await db.commit()
    return None
