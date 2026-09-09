from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_db
from .models import Branch, Company, User
from .security import decode_token

bearer = HTTPBearer(auto_error=False)


@dataclass
class Ctx:
    user: User
    tenant_id: uuid.UUID
    company_id: uuid.UUID
    branch_id: uuid.UUID | None
    perms: list[str] = field(default_factory=list)
    ip: str | None = None

    @property
    def user_id(self) -> uuid.UUID:
        return self.user.id

    def has(self, perm: str) -> bool:
        if "*" in self.perms:
            return True
        if perm in self.perms:
            return True
        module = perm.split(".")[0]
        return f"{module}.*" in self.perms


async def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: AsyncSession = Depends(get_db)) -> tuple[User, dict]:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = decode_token(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token type")
    user = await db.get(User, uuid.UUID(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User inactive")
    return user, payload


async def get_ctx(
    request: Request,
    auth: tuple[User, dict] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    x_company_id: str | None = Header(default=None, alias="X-Company-Id"),
    x_branch_id: str | None = Header(default=None, alias="X-Branch-Id"),
) -> Ctx:
    user, payload = auth
    tenant_id = user.tenant_id
    company_id: uuid.UUID | None = None
    if x_company_id:
        try:
            company_id = uuid.UUID(x_company_id)
        except ValueError:
            raise HTTPException(400, "Invalid X-Company-Id")
    elif payload.get("cid"):
        company_id = uuid.UUID(payload["cid"])
    else:
        company_id = user.default_company_id
    if company_id is None:
        raise HTTPException(400, "No company selected")
    company = await db.get(Company, company_id)
    if not company or company.tenant_id != tenant_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Company not accessible")
    branch_id: uuid.UUID | None = None
    if x_branch_id:
        try:
            branch_id = uuid.UUID(x_branch_id)
        except ValueError:
            raise HTTPException(400, "Invalid X-Branch-Id")
    elif payload.get("bid"):
        branch_id = uuid.UUID(payload["bid"])
    else:
        branch_id = user.default_branch_id
    if branch_id is not None:
        branch = await db.get(Branch, branch_id)
        if not branch or branch.company_id != company_id:
            # fall back to default branch of this company
            res = await db.execute(select(Branch).where(Branch.company_id == company_id).order_by(Branch.is_default.desc()).limit(1))
            b = res.scalar_one_or_none()
            branch_id = b.id if b else None
    perms = list(user.role.permissions or []) if user.role else []
    if user.is_owner:
        perms = ["*"]
    ip = request.client.host if request.client else None
    return Ctx(user=user, tenant_id=tenant_id, company_id=company_id, branch_id=branch_id, perms=perms, ip=ip)


def require(perm: str):
    async def _dep(ctx: Ctx = Depends(get_ctx)) -> Ctx:
        if not ctx.has(perm):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Missing permission: {perm}")
        return ctx

    return _dep


PERMISSIONS: dict[str, str] = {
    "*": "Everything (owner)",
    "settings.manage": "Manage company, branches, users, roles, fiscal years",
    "accounting.view": "View ledgers, vouchers and reports",
    "accounting.post": "Post journal/payment/receipt/contra vouchers",
    "accounting.reverse": "Reverse posted vouchers",
    "accounting.manage": "Manage chart of accounts",
    "inventory.view": "View products and stock",
    "inventory.manage": "Manage products, godowns, batches",
    "inventory.post": "Post stock adjustments and transfers",
    "sales.view": "View sales documents",
    "sales.write": "Create/edit sales drafts",
    "sales.post": "Post sales invoices and returns",
    "purchase.view": "View purchase documents",
    "purchase.write": "Create/edit purchase drafts",
    "purchase.post": "Post purchase bills and returns",
    "parties.manage": "Manage customers and suppliers",
    "reports.view": "View reports and dashboards",
    "gst.view": "View GST reports",
    "audit.view": "View audit log",
}
