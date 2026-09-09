"""SQLAlchemy 2.0 models for TileOS.

Tenancy: Tenant -> Company -> Branch. Every business row carries tenant_id (and usually company_id).
Money is NUMERIC(18,2), quantities NUMERIC(18,4). No floats anywhere.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, Timestamped, UUIDPk

Money = Numeric(18, 2)
Qty = Numeric(18, 4)
Rate = Numeric(18, 4)
Pct = Numeric(7, 3)


def uuid_col(fk: str | None = None, nullable: bool = False, index: bool = True):
    if fk:
        return mapped_column(PG_UUID(as_uuid=True), ForeignKey(fk, ondelete="RESTRICT"), nullable=nullable, index=index)
    return mapped_column(PG_UUID(as_uuid=True), nullable=nullable, index=index)


class TenantScoped:
    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)


class CompanyScoped(TenantScoped):
    company_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)


# ---------------------------------------------------------------------------
# Foundation
# ---------------------------------------------------------------------------
class Tenant(UUIDPk, Timestamped, Base):
    __tablename__ = "tenants"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(40), default="standard", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Company(UUIDPk, Timestamped, TenantScoped, Base):
    __tablename__ = "companies"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(200))
    gstin: Mapped[str | None] = mapped_column(String(15))
    pan: Mapped[str | None] = mapped_column(String(10))
    address_line1: Mapped[str | None] = mapped_column(String(200))
    address_line2: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    state_code: Mapped[str] = mapped_column(String(2), default="27", nullable=False)
    pincode: Mapped[str | None] = mapped_column(String(10))
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(200))
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    fy_start_month: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    allow_negative_stock: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    default_wastage_pct: Mapped[Decimal] = mapped_column(Pct, default=Decimal("7"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Branch(UUIDPk, Timestamped, CompanyScoped, Base):
    __tablename__ = "branches"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    state_code: Mapped[str | None] = mapped_column(String(2))
    gstin: Mapped[str | None] = mapped_column(String(15))
    phone: Mapped[str | None] = mapped_column(String(20))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    __table_args__ = (UniqueConstraint("company_id", "code"),)


class Role(UUIDPk, Timestamped, TenantScoped, Base):
    __tablename__ = "roles"
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(String(300))
    permissions: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)


class User(UUIDPk, Timestamped, TenantScoped, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(200), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    role_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    default_company_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"))
    default_branch_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_owner: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    role: Mapped[Role] = relationship(lazy="joined")
    __table_args__ = (UniqueConstraint("tenant_id", "email"),)


class RefreshToken(UUIDPk, Base):
    __tablename__ = "refresh_tokens"
    tenant_id: Mapped[uuid.UUID] = uuid_col("tenants.id")
    user_id: Mapped[uuid.UUID] = uuid_col("users.id")
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    device_id: Mapped[str | None] = mapped_column(String(100))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuditLog(UUIDPk, Base):
    __tablename__ = "audit_logs"
    tenant_id: Mapped[uuid.UUID] = uuid_col("tenants.id")
    company_id: Mapped[uuid.UUID | None] = uuid_col(nullable=True)
    user_id: Mapped[uuid.UUID | None] = uuid_col(nullable=True)
    user_email: Mapped[str | None] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(60), nullable=False)  # create/update/post/reverse/login/...
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(60))
    summary: Mapped[str | None] = mapped_column(String(500))
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class Setting(UUIDPk, Timestamped, CompanyScoped, Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    __table_args__ = (UniqueConstraint("company_id", "key"),)


class FiscalYear(UUIDPk, Timestamped, CompanyScoped, Base):
    __tablename__ = "fiscal_years"
    name: Mapped[str] = mapped_column(String(20), nullable=False)  # 2025-26
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    locked_till: Mapped[date | None] = mapped_column(Date)  # period lock: no posting on/before this date
    __table_args__ = (UniqueConstraint("company_id", "name"),)


class NumberSequence(UUIDPk, CompanyScoped, Base):
    __tablename__ = "number_sequences"
    doc_type: Mapped[str] = mapped_column(String(40), nullable=False)
    fiscal_year_id: Mapped[uuid.UUID | None] = uuid_col("fiscal_years.id", nullable=True)
    prefix: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    next_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __table_args__ = (UniqueConstraint("company_id", "doc_type", "fiscal_year_id"),)


# ---------------------------------------------------------------------------
# Accounting
# ---------------------------------------------------------------------------
class AccountGroup(UUIDPk, Timestamped, CompanyScoped, Base):
    __tablename__ = "account_groups"
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("account_groups.id"))
    nature: Mapped[str] = mapped_column(String(20), nullable=False)  # asset/liability/equity/income/expense
    report: Mapped[str] = mapped_column(String(20), nullable=False)  # balance_sheet / profit_loss
    affects_gross_profit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    __table_args__ = (UniqueConstraint("company_id", "code"),)


class Ledger(UUIDPk, Timestamped, CompanyScoped, Base):
    __tablename__ = "ledgers"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(30))
    group_id: Mapped[uuid.UUID] = uuid_col("account_groups.id")
    opening_balance: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"), nullable=False)
    opening_type: Mapped[str] = mapped_column(String(2), default="dr", nullable=False)  # dr / cr
    system_key: Mapped[str | None] = mapped_column(String(40))  # sales, purchase, output_cgst, ... (system ledgers)
    party_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("parties.id", ondelete="SET NULL", use_alter=True))
    is_bank: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_cash: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    bank_account_no: Mapped[str | None] = mapped_column(String(40))
    bank_ifsc: Mapped[str | None] = mapped_column(String(20))
    group: Mapped[AccountGroup] = relationship(lazy="joined")
    __table_args__ = (UniqueConstraint("company_id", "name"), Index("ix_ledgers_company_system_key", "company_id", "system_key"))


class Voucher(UUIDPk, Timestamped, CompanyScoped, Base):
    __tablename__ = "vouchers"
    branch_id: Mapped[uuid.UUID | None] = uuid_col("branches.id", nullable=True)
    fiscal_year_id: Mapped[uuid.UUID] = uuid_col("fiscal_years.id")
    voucher_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    voucher_no: Mapped[str] = mapped_column(String(40), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    narration: Mapped[str | None] = mapped_column(Text)
    reference_type: Mapped[str | None] = mapped_column(String(40))  # trade_document / stock_adjustment / ...
    reference_id: Mapped[uuid.UUID | None] = uuid_col(nullable=True)
    party_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("parties.id", use_alter=True))
    total_debit: Mapped[Decimal] = mapped_column(Money, nullable=False)
    total_credit: Mapped[Decimal] = mapped_column(Money, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="posted", nullable=False)  # posted / reversed / reversal
    reverses_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("vouchers.id"))
    reversed_by_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("vouchers.id"))
    posted_by: Mapped[uuid.UUID | None] = uuid_col(nullable=True, index=False)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(80))
    lines: Mapped[list[VoucherLine]] = relationship(back_populates="voucher", cascade="all, delete-orphan", order_by="VoucherLine.line_no", lazy="selectin")
    __table_args__ = (UniqueConstraint("company_id", "voucher_type", "voucher_no"), UniqueConstraint("company_id", "idempotency_key"))


class VoucherLine(UUIDPk, Base):
    __tablename__ = "voucher_lines"
    tenant_id: Mapped[uuid.UUID] = uuid_col("tenants.id")
    voucher_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("vouchers.id", ondelete="CASCADE"), nullable=False, index=True)
    ledger_id: Mapped[uuid.UUID] = uuid_col("ledgers.id")
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    debit: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"), nullable=False)
    credit: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"), nullable=False)
    narration: Mapped[str | None] = mapped_column(String(500))
    cost_centre: Mapped[str | None] = mapped_column(String(100))
    voucher: Mapped[Voucher] = relationship(back_populates="lines")
    ledger: Mapped[Ledger] = relationship(lazy="joined")


class Bill(UUIDPk, Timestamped, CompanyScoped, Base):
    """Bill-wise outstanding tracking (receivable/payable)."""

    __tablename__ = "bills"
    party_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("parties.id", use_alter=True), nullable=False, index=True)
    ledger_id: Mapped[uuid.UUID] = uuid_col("ledgers.id")
    kind: Mapped[str] = mapped_column(String(12), nullable=False)  # receivable / payable
    bill_no: Mapped[str] = mapped_column(String(40), nullable=False)
    bill_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)  # may be negative for credit balances (advances/returns)
    doc_type: Mapped[str | None] = mapped_column(String(40))
    doc_id: Mapped[uuid.UUID | None] = uuid_col(nullable=True)
    voucher_id: Mapped[uuid.UUID | None] = uuid_col("vouchers.id", nullable=True)
    settlements: Mapped[list[BillSettlement]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class BillSettlement(UUIDPk, Base):
    __tablename__ = "bill_settlements"
    tenant_id: Mapped[uuid.UUID] = uuid_col("tenants.id")
    bill_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("bills.id", ondelete="CASCADE"), nullable=False, index=True)
    voucher_id: Mapped[uuid.UUID] = uuid_col("vouchers.id")
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)


# ---------------------------------------------------------------------------
# Parties, projects
# ---------------------------------------------------------------------------
class Party(UUIDPk, Timestamped, CompanyScoped, Base):
    __tablename__ = "parties"
    party_type: Mapped[str] = mapped_column(String(10), nullable=False)  # customer / supplier / both
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(30))
    contact_person: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(20))
    whatsapp: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(200))
    gstin: Mapped[str | None] = mapped_column(String(15))
    pan: Mapped[str | None] = mapped_column(String(10))
    billing_address: Mapped[str | None] = mapped_column(Text)
    shipping_address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(100))
    state_code: Mapped[str] = mapped_column(String(2), default="27", nullable=False)
    pincode: Mapped[str | None] = mapped_column(String(10))
    credit_limit: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"), nullable=False)
    credit_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    price_tier: Mapped[str] = mapped_column(String(20), default="retail", nullable=False)  # retail/dealer/project
    ledger_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("ledgers.id", use_alter=True))
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    whatsapp_opt_in: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    __table_args__ = (Index("ix_parties_company_name", "company_id", "name"),)


class Project(UUIDPk, Timestamped, CompanyScoped, Base):
    __tablename__ = "projects"
    party_id: Mapped[uuid.UUID] = uuid_col("parties.id")
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    site_address: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    budget: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------
class Unit(UUIDPk, Timestamped, CompanyScoped, Base):
    __tablename__ = "units"
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    symbol: Mapped[str] = mapped_column(String(12), nullable=False)
    decimals: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    __table_args__ = (UniqueConstraint("company_id", "symbol"),)


class Brand(UUIDPk, Timestamped, CompanyScoped, Base):
    __tablename__ = "brands"
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    __table_args__ = (UniqueConstraint("company_id", "name"),)


class Category(UUIDPk, Timestamped, CompanyScoped, Base):
    __tablename__ = "categories"
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), default="general", nullable=False)  # tile / sanitary / general
    parent_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("categories.id"))
    __table_args__ = (UniqueConstraint("company_id", "name"),)


class Godown(UUIDPk, Timestamped, CompanyScoped, Base):
    __tablename__ = "godowns"
    branch_id: Mapped[uuid.UUID | None] = uuid_col("branches.id", nullable=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    __table_args__ = (UniqueConstraint("company_id", "code"),)


class Product(UUIDPk, Timestamped, CompanyScoped, Base):
    __tablename__ = "products"
    sku: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    product_type: Mapped[str] = mapped_column(String(20), default="tile", nullable=False)  # tile / sanitary / general
    category_id: Mapped[uuid.UUID | None] = uuid_col("categories.id", nullable=True)
    brand_id: Mapped[uuid.UUID | None] = uuid_col("brands.id", nullable=True)
    hsn_code: Mapped[str | None] = mapped_column(String(10))
    gst_rate: Mapped[Decimal] = mapped_column(Pct, default=Decimal("18"), nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(60))
    description: Mapped[str | None] = mapped_column(Text)
    # units: stock is always kept in stock_unit (e.g. Box). Alternate: area unit (SQFT) via sqft_per_box, pieces via pieces_per_box
    stock_unit_id: Mapped[uuid.UUID] = uuid_col("units.id")
    pieces_per_box: Mapped[Decimal | None] = mapped_column(Qty)
    sqft_per_box: Mapped[Decimal | None] = mapped_column(Qty)
    sqm_per_box: Mapped[Decimal | None] = mapped_column(Qty)
    boxes_per_pallet: Mapped[Decimal | None] = mapped_column(Qty)
    weight_kg_per_box: Mapped[Decimal | None] = mapped_column(Qty)
    # tile attributes
    series: Mapped[str | None] = mapped_column(String(100))
    design: Mapped[str | None] = mapped_column(String(100))
    colour: Mapped[str | None] = mapped_column(String(60))
    size: Mapped[str | None] = mapped_column(String(40))  # 600x600 mm
    thickness_mm: Mapped[Decimal | None] = mapped_column(Qty)
    finish: Mapped[str | None] = mapped_column(String(60))  # glossy / matt / satin / polished
    material: Mapped[str | None] = mapped_column(String(60))  # vitrified / ceramic / porcelain
    grade: Mapped[str | None] = mapped_column(String(20))  # premium / standard / commercial
    pattern: Mapped[str | None] = mapped_column(String(60))
    application: Mapped[str | None] = mapped_column(String(40))  # wall / floor / outdoor / indoor
    # sanitary attributes
    model_no: Mapped[str | None] = mapped_column(String(60))
    warranty_months: Mapped[int | None] = mapped_column(Integer)
    installation_notes: Mapped[str | None] = mapped_column(Text)
    set_contents: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)  # [{name, qty}]
    compatible_skus: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    # pricing tiers (per stock unit)
    purchase_price: Mapped[Decimal] = mapped_column(Rate, default=Decimal("0"), nullable=False)
    sale_price: Mapped[Decimal] = mapped_column(Rate, default=Decimal("0"), nullable=False)
    retail_price: Mapped[Decimal] = mapped_column(Rate, default=Decimal("0"), nullable=False)
    dealer_price: Mapped[Decimal] = mapped_column(Rate, default=Decimal("0"), nullable=False)
    project_price: Mapped[Decimal] = mapped_column(Rate, default=Decimal("0"), nullable=False)
    mrp: Mapped[Decimal] = mapped_column(Rate, default=Decimal("0"), nullable=False)
    discount_pct: Mapped[Decimal] = mapped_column(Pct, default=Decimal("0"), nullable=False)
    # stock control
    reorder_level: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"), nullable=False)
    track_batches: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    stock_unit: Mapped[Unit] = relationship(lazy="joined")
    brand: Mapped[Brand | None] = relationship(lazy="joined")
    category: Mapped[Category | None] = relationship(lazy="joined")
    __table_args__ = (UniqueConstraint("company_id", "sku"), Index("ix_products_company_name", "company_id", "name"))


class Batch(UUIDPk, Timestamped, CompanyScoped, Base):
    __tablename__ = "batches"
    product_id: Mapped[uuid.UUID] = uuid_col("products.id")
    batch_no: Mapped[str] = mapped_column(String(60), nullable=False)
    shade: Mapped[str | None] = mapped_column(String(30))
    calibre: Mapped[str | None] = mapped_column(String(30))
    mfg_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(String(300))
    __table_args__ = (UniqueConstraint("product_id", "batch_no", "shade", "calibre"),)


class StockMovement(UUIDPk, CompanyScoped, Base):
    __tablename__ = "stock_movements"
    branch_id: Mapped[uuid.UUID | None] = uuid_col("branches.id", nullable=True)
    godown_id: Mapped[uuid.UUID] = uuid_col("godowns.id")
    product_id: Mapped[uuid.UUID] = uuid_col("products.id")
    batch_id: Mapped[uuid.UUID | None] = uuid_col("batches.id", nullable=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    movement_type: Mapped[str] = mapped_column(String(30), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Qty, nullable=False)  # signed, in stock unit
    rate: Mapped[Decimal] = mapped_column(Rate, default=Decimal("0"), nullable=False)  # cost per stock unit
    value: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"), nullable=False)  # signed
    doc_type: Mapped[str | None] = mapped_column(String(40))
    doc_id: Mapped[uuid.UUID | None] = uuid_col(nullable=True)
    narration: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockReservation(UUIDPk, Timestamped, CompanyScoped, Base):
    __tablename__ = "stock_reservations"
    product_id: Mapped[uuid.UUID] = uuid_col("products.id")
    batch_id: Mapped[uuid.UUID | None] = uuid_col("batches.id", nullable=True)
    godown_id: Mapped[uuid.UUID] = uuid_col("godowns.id")
    party_id: Mapped[uuid.UUID | None] = uuid_col("parties.id", nullable=True)
    project_id: Mapped[uuid.UUID | None] = uuid_col("projects.id", nullable=True)
    qty: Mapped[Decimal] = mapped_column(Qty, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)  # active / released / consumed
    expires_on: Mapped[date | None] = mapped_column(Date)


class StockJournal(UUIDPk, Timestamped, CompanyScoped, Base):
    """Stock adjustments and transfers (lines stored as JSONB; movements written to stock_movements)."""

    __tablename__ = "stock_journals"
    branch_id: Mapped[uuid.UUID | None] = uuid_col("branches.id", nullable=True)
    journal_type: Mapped[str] = mapped_column(String(20), nullable=False)  # adjustment / transfer / opening / physical_count
    doc_no: Mapped[str] = mapped_column(String(40), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    from_godown_id: Mapped[uuid.UUID | None] = uuid_col("godowns.id", nullable=True)
    to_godown_id: Mapped[uuid.UUID | None] = uuid_col("godowns.id", nullable=True)
    reason: Mapped[str | None] = mapped_column(String(300))
    lines: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    total_value: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"), nullable=False)
    voucher_id: Mapped[uuid.UUID | None] = uuid_col("vouchers.id", nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="posted", nullable=False)
    created_by: Mapped[uuid.UUID | None] = uuid_col(nullable=True, index=False)
    __table_args__ = (UniqueConstraint("company_id", "journal_type", "doc_no"),)


class SampleIssue(UUIDPk, Timestamped, CompanyScoped, Base):
    __tablename__ = "sample_issues"
    product_id: Mapped[uuid.UUID] = uuid_col("products.id")
    party_id: Mapped[uuid.UUID | None] = uuid_col("parties.id", nullable=True)
    project_id: Mapped[uuid.UUID | None] = uuid_col("projects.id", nullable=True)
    qty: Mapped[Decimal] = mapped_column(Qty, nullable=False)
    issued_on: Mapped[date] = mapped_column(Date, nullable=False)
    expected_return_on: Mapped[date | None] = mapped_column(Date)
    returned_on: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="issued", nullable=False)  # issued / returned / lost / converted
    notes: Mapped[str | None] = mapped_column(String(300))


# ---------------------------------------------------------------------------
# Trade documents (sales + purchase)
# ---------------------------------------------------------------------------
SALES_DOC_TYPES = ("quotation", "sales_order", "delivery_challan", "sales_invoice", "sales_return")
PURCHASE_DOC_TYPES = ("purchase_order", "grn", "purchase_bill", "purchase_return")


class TradeDocument(UUIDPk, Timestamped, CompanyScoped, Base):
    __tablename__ = "trade_documents"
    branch_id: Mapped[uuid.UUID | None] = uuid_col("branches.id", nullable=True)
    doc_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(40), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    due_date: Mapped[date | None] = mapped_column(Date)
    valid_till: Mapped[date | None] = mapped_column(Date)
    party_id: Mapped[uuid.UUID] = uuid_col("parties.id")
    party_name: Mapped[str] = mapped_column(String(200), nullable=False)
    party_gstin: Mapped[str | None] = mapped_column(String(15))
    party_state_code: Mapped[str] = mapped_column(String(2), nullable=False)
    place_of_supply: Mapped[str] = mapped_column(String(2), nullable=False)
    is_interstate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    godown_id: Mapped[uuid.UUID | None] = uuid_col("godowns.id", nullable=True)
    project_id: Mapped[uuid.UUID | None] = uuid_col("projects.id", nullable=True)
    reference_doc_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("trade_documents.id"))
    supplier_ref_no: Mapped[str | None] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)  # draft/posted/cancelled/converted
    subtotal: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"), nullable=False)
    discount_total: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"), nullable=False)
    taxable_total: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"), nullable=False)
    cgst_total: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"), nullable=False)
    sgst_total: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"), nullable=False)
    igst_total: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"), nullable=False)
    round_off: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"), nullable=False)
    grand_total: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"), nullable=False)
    paid_amount: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"), nullable=False)
    payment_ledger_id: Mapped[uuid.UUID | None] = uuid_col("ledgers.id", nullable=True)
    notes: Mapped[str | None] = mapped_column(Text)
    terms: Mapped[str | None] = mapped_column(Text)
    salesman: Mapped[str | None] = mapped_column(String(100))
    transporter: Mapped[str | None] = mapped_column(String(100))
    vehicle_no: Mapped[str | None] = mapped_column(String(20))
    eway_bill_no: Mapped[str | None] = mapped_column(String(20))
    irn: Mapped[str | None] = mapped_column(String(80))
    voucher_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("vouchers.id"))
    cogs_voucher_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("vouchers.id"))
    receipt_voucher_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("vouchers.id"))
    created_by: Mapped[uuid.UUID | None] = uuid_col(nullable=True, index=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str | None] = mapped_column(String(80))
    lines: Mapped[list[TradeLine]] = relationship(back_populates="document", cascade="all, delete-orphan", order_by="TradeLine.line_no", lazy="selectin")
    __table_args__ = (UniqueConstraint("company_id", "doc_type", "doc_no"), UniqueConstraint("company_id", "idempotency_key"))


class TradeLine(UUIDPk, Base):
    __tablename__ = "trade_lines"
    tenant_id: Mapped[uuid.UUID] = uuid_col("tenants.id")
    document_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("trade_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[uuid.UUID] = uuid_col("products.id")
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    hsn_code: Mapped[str | None] = mapped_column(String(10))
    batch_id: Mapped[uuid.UUID | None] = uuid_col("batches.id", nullable=True)
    godown_id: Mapped[uuid.UUID | None] = uuid_col("godowns.id", nullable=True)
    qty: Mapped[Decimal] = mapped_column(Qty, nullable=False)  # in stock unit (boxes)
    unit_symbol: Mapped[str] = mapped_column(String(12), nullable=False)
    area_sqft: Mapped[Decimal | None] = mapped_column(Qty)  # informational for tiles
    rate: Mapped[Decimal] = mapped_column(Rate, nullable=False)
    discount_pct: Mapped[Decimal] = mapped_column(Pct, default=Decimal("0"), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"), nullable=False)
    taxable_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    gst_rate: Mapped[Decimal] = mapped_column(Pct, nullable=False)
    cgst: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"), nullable=False)
    sgst: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"), nullable=False)
    igst: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"), nullable=False)
    total: Mapped[Decimal] = mapped_column(Money, nullable=False)
    cost_rate: Mapped[Decimal] = mapped_column(Rate, default=Decimal("0"), nullable=False)  # for COGS at posting
    document: Mapped[TradeDocument] = relationship(back_populates="lines")


# ---------------------------------------------------------------------------
# Stretch modules: sync, WhatsApp
# ---------------------------------------------------------------------------
class SyncOutbox(UUIDPk, Base):
    __tablename__ = "sync_outbox"
    tenant_id: Mapped[uuid.UUID] = uuid_col("tenants.id")
    company_id: Mapped[uuid.UUID | None] = uuid_col(nullable=True)
    device_id: Mapped[str] = mapped_column(String(100), nullable=False)
    op_id: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    operation: Mapped[str] = mapped_column(String(30), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # pending/applied/conflict/failed
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("tenant_id", "device_id", "op_id"),)


class WhatsAppMessage(UUIDPk, Base):
    __tablename__ = "whatsapp_messages"
    tenant_id: Mapped[uuid.UUID] = uuid_col("tenants.id")
    company_id: Mapped[uuid.UUID] = uuid_col("companies.id")
    party_id: Mapped[uuid.UUID | None] = uuid_col("parties.id", nullable=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    template: Mapped[str] = mapped_column(String(60), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    doc_type: Mapped[str | None] = mapped_column(String(40))
    doc_id: Mapped[uuid.UUID | None] = uuid_col(nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)  # queued/sent/failed/not_configured/opted_out
    provider_ref: Mapped[str | None] = mapped_column(String(120))
    error: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
