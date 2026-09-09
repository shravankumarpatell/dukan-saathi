"""Pydantic v2 schemas (request/response)."""
from __future__ import annotations

import uuid
import datetime as dt
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

MoneyD = Decimal


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------------------------------ auth
class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    tenant_slug: str | None = None
    device_id: str | None = None


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshIn(BaseModel):
    refresh_token: str


class RoleOut(ORM):
    id: uuid.UUID
    name: str
    description: str | None
    permissions: list[str]
    is_system: bool


class RoleIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: str | None = None
    permissions: list[str]


class CompanyOut(ORM):
    id: uuid.UUID
    name: str
    legal_name: str | None
    gstin: str | None
    pan: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    state_code: str
    pincode: str | None
    phone: str | None
    email: str | None
    currency: str
    fy_start_month: int
    allow_negative_stock: bool
    default_wastage_pct: Decimal


class CompanyIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    legal_name: str | None = None
    gstin: str | None = None
    pan: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    state_code: str = "27"
    pincode: str | None = None
    phone: str | None = None
    email: str | None = None
    fy_start_month: int = 4
    allow_negative_stock: bool = False
    default_wastage_pct: Decimal = Decimal("7")


class BranchOut(ORM):
    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    code: str
    address: str | None
    state_code: str | None
    gstin: str | None
    phone: str | None
    is_default: bool
    is_active: bool


class BranchIn(BaseModel):
    name: str
    code: str
    address: str | None = None
    state_code: str | None = None
    gstin: str | None = None
    phone: str | None = None
    is_default: bool = False


class UserOut(ORM):
    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    role_id: uuid.UUID
    default_company_id: uuid.UUID | None
    default_branch_id: uuid.UUID | None
    is_active: bool
    is_owner: bool
    last_login_at: datetime | None


class UserIn(BaseModel):
    email: EmailStr
    full_name: str
    password: str | None = Field(default=None, min_length=6)
    phone: str | None = None
    role_id: uuid.UUID
    default_company_id: uuid.UUID | None = None
    default_branch_id: uuid.UUID | None = None
    is_active: bool = True


class MeOut(BaseModel):
    user: UserOut
    role: RoleOut
    permissions: list[str]
    tenant: dict[str, Any]
    companies: list[CompanyOut]
    branches: list[BranchOut]
    current_company_id: uuid.UUID | None
    current_branch_id: uuid.UUID | None


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)


class FiscalYearOut(ORM):
    id: uuid.UUID
    name: str
    start_date: date
    end_date: date
    is_closed: bool
    locked_till: date | None


class FiscalYearIn(BaseModel):
    name: str
    start_date: date
    end_date: date


class LockPeriodIn(BaseModel):
    locked_till: date | None


class AuditOut(ORM):
    id: uuid.UUID
    user_email: str | None
    action: str
    entity_type: str
    entity_id: str | None
    summary: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    created_at: datetime


class SettingIn(BaseModel):
    key: str
    value: dict[str, Any]


# ------------------------------------------------------------------ accounting
class AccountGroupOut(ORM):
    id: uuid.UUID
    name: str
    code: str
    parent_id: uuid.UUID | None
    nature: str
    report: str
    affects_gross_profit: bool
    sequence: int
    is_system: bool


class AccountGroupIn(BaseModel):
    name: str
    code: str
    parent_id: uuid.UUID | None = None
    nature: Literal["asset", "liability", "equity", "income", "expense"]
    affects_gross_profit: bool = False


class LedgerOut(ORM):
    id: uuid.UUID
    name: str
    code: str | None
    group_id: uuid.UUID
    group_name: str | None = None
    nature: str | None = None
    opening_balance: Decimal
    opening_type: str
    system_key: str | None
    party_id: uuid.UUID | None
    is_bank: bool
    is_cash: bool
    is_system: bool
    is_active: bool
    description: str | None
    bank_account_no: str | None
    bank_ifsc: str | None
    balance: Decimal | None = None  # signed: +ve debit, -ve credit
    balance_type: str | None = None


class LedgerIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str | None = None
    group_id: uuid.UUID
    opening_balance: Decimal = Decimal("0")
    opening_type: Literal["dr", "cr"] = "dr"
    is_bank: bool = False
    is_cash: bool = False
    description: str | None = None
    bank_account_no: str | None = None
    bank_ifsc: str | None = None
    is_active: bool = True


class VoucherLineIn(BaseModel):
    ledger_id: uuid.UUID
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    narration: str | None = None
    cost_centre: str | None = None

    @field_validator("debit", "credit")
    @classmethod
    def non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Amounts must be non-negative")
        return v


class BillAllocationIn(BaseModel):
    bill_id: uuid.UUID
    amount: Decimal


class VoucherIn(BaseModel):
    voucher_type: Literal["journal", "payment", "receipt", "contra"]
    date: date
    narration: str | None = None
    lines: list[VoucherLineIn] = Field(min_length=2)
    party_id: uuid.UUID | None = None
    allocations: list[BillAllocationIn] = Field(default_factory=list)
    auto_allocate: bool = False  # FIFO allocate receipt/payment against party's open bills
    idempotency_key: str | None = None


class QuickReceiptIn(BaseModel):
    """Simplified receipt/payment: party + amount + cash/bank ledger."""

    kind: Literal["receipt", "payment"]
    date: date
    party_id: uuid.UUID
    amount: Decimal = Field(gt=0)
    account_ledger_id: uuid.UUID  # cash / bank ledger
    narration: str | None = None
    allocations: list[BillAllocationIn] = Field(default_factory=list)
    auto_allocate: bool = True
    idempotency_key: str | None = None


class VoucherLineOut(ORM):
    id: uuid.UUID
    ledger_id: uuid.UUID
    ledger_name: str | None = None
    line_no: int
    debit: Decimal
    credit: Decimal
    narration: str | None
    cost_centre: str | None


class VoucherOut(ORM):
    id: uuid.UUID
    voucher_type: str
    voucher_no: str
    date: date
    narration: str | None
    reference_type: str | None
    reference_id: uuid.UUID | None
    party_id: uuid.UUID | None
    total_debit: Decimal
    total_credit: Decimal
    status: str
    reverses_id: uuid.UUID | None
    reversed_by_id: uuid.UUID | None
    posted_at: datetime
    lines: list[VoucherLineOut]


class ReverseIn(BaseModel):
    date: dt.date | None = None
    narration: str | None = None


# ------------------------------------------------------------------ parties / projects
class PartyIn(BaseModel):
    party_type: Literal["customer", "supplier", "both"] = "customer"
    name: str = Field(min_length=1, max_length=200)
    code: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    email: str | None = None
    gstin: str | None = None
    pan: str | None = None
    billing_address: str | None = None
    shipping_address: str | None = None
    city: str | None = None
    state_code: str = "27"
    pincode: str | None = None
    credit_limit: Decimal = Decimal("0")
    credit_days: int = 0
    price_tier: Literal["retail", "dealer", "project"] = "retail"
    opening_balance: Decimal = Decimal("0")
    opening_type: Literal["dr", "cr"] = "dr"
    tags: list[str] = Field(default_factory=list)
    whatsapp_opt_in: bool = False
    notes: str | None = None
    is_active: bool = True


class PartyOut(ORM):
    id: uuid.UUID
    party_type: str
    name: str
    code: str | None
    contact_person: str | None
    phone: str | None
    whatsapp: str | None
    email: str | None
    gstin: str | None
    pan: str | None
    billing_address: str | None
    shipping_address: str | None
    city: str | None
    state_code: str
    pincode: str | None
    credit_limit: Decimal
    credit_days: int
    price_tier: str
    ledger_id: uuid.UUID | None
    tags: list[str]
    whatsapp_opt_in: bool
    notes: str | None
    is_active: bool
    outstanding: Decimal | None = None


class ProjectIn(BaseModel):
    party_id: uuid.UUID
    name: str
    site_address: str | None = None
    status: str = "active"
    budget: Decimal = Decimal("0")
    notes: str | None = None


class ProjectOut(ORM):
    id: uuid.UUID
    party_id: uuid.UUID
    name: str
    site_address: str | None
    status: str
    budget: Decimal
    notes: str | None


# ------------------------------------------------------------------ inventory
class UnitOut(ORM):
    id: uuid.UUID
    name: str
    symbol: str
    decimals: int
    is_system: bool


class UnitIn(BaseModel):
    name: str
    symbol: str
    decimals: int = 2


class NamedIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class BrandOut(ORM):
    id: uuid.UUID
    name: str


class CategoryIn(BaseModel):
    name: str
    kind: Literal["tile", "sanitary", "general"] = "general"
    parent_id: uuid.UUID | None = None


class CategoryOut(ORM):
    id: uuid.UUID
    name: str
    kind: str
    parent_id: uuid.UUID | None


class GodownIn(BaseModel):
    name: str
    code: str
    branch_id: uuid.UUID | None = None
    address: str | None = None
    is_default: bool = False


class GodownOut(ORM):
    id: uuid.UUID
    branch_id: uuid.UUID | None
    name: str
    code: str
    address: str | None
    is_default: bool
    is_active: bool


class ProductIn(BaseModel):
    sku: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=250)
    product_type: Literal["tile", "sanitary", "general"] = "tile"
    category_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    hsn_code: str | None = None
    gst_rate: Decimal = Decimal("18")
    barcode: str | None = None
    description: str | None = None
    stock_unit_id: uuid.UUID
    pieces_per_box: Decimal | None = None
    sqft_per_box: Decimal | None = None
    sqm_per_box: Decimal | None = None
    boxes_per_pallet: Decimal | None = None
    weight_kg_per_box: Decimal | None = None
    series: str | None = None
    design: str | None = None
    colour: str | None = None
    size: str | None = None
    thickness_mm: Decimal | None = None
    finish: str | None = None
    material: str | None = None
    grade: str | None = None
    pattern: str | None = None
    application: str | None = None
    model_no: str | None = None
    warranty_months: int | None = None
    installation_notes: str | None = None
    set_contents: list[dict[str, Any]] = Field(default_factory=list)
    compatible_skus: list[str] = Field(default_factory=list)
    purchase_price: Decimal = Decimal("0")
    sale_price: Decimal = Decimal("0")
    retail_price: Decimal = Decimal("0")
    dealer_price: Decimal = Decimal("0")
    project_price: Decimal = Decimal("0")
    mrp: Decimal = Decimal("0")
    discount_pct: Decimal = Decimal("0")
    reorder_level: Decimal = Decimal("0")
    track_batches: bool = True
    is_active: bool = True


class ProductOut(ProductIn, ORM):
    id: uuid.UUID
    unit_symbol: str | None = None
    brand_name: str | None = None
    category_name: str | None = None
    stock_qty: Decimal | None = None
    stock_value: Decimal | None = None


class BatchIn(BaseModel):
    product_id: uuid.UUID
    batch_no: str
    shade: str | None = None
    calibre: str | None = None
    mfg_date: date | None = None
    notes: str | None = None


class BatchOut(ORM):
    id: uuid.UUID
    product_id: uuid.UUID
    batch_no: str
    shade: str | None
    calibre: str | None
    mfg_date: date | None
    notes: str | None
    qty: Decimal | None = None


class StockJournalLineIn(BaseModel):
    product_id: uuid.UUID
    batch_id: uuid.UUID | None = None
    qty: Decimal  # +in / -out for adjustments; positive for transfers
    rate: Decimal | None = None  # cost per stock unit for inward adjustments; defaults to avg cost
    godown_id: uuid.UUID | None = None  # adjustments only
    narration: str | None = None


class StockJournalIn(BaseModel):
    journal_type: Literal["adjustment", "transfer", "opening", "physical_count"]
    date: date
    from_godown_id: uuid.UUID | None = None
    to_godown_id: uuid.UUID | None = None
    reason: str | None = None
    lines: list[StockJournalLineIn] = Field(min_length=1)
    idempotency_key: str | None = None


class StockJournalOut(ORM):
    id: uuid.UUID
    journal_type: str
    doc_no: str
    date: date
    from_godown_id: uuid.UUID | None
    to_godown_id: uuid.UUID | None
    reason: str | None
    lines: list[dict[str, Any]]
    total_value: Decimal
    voucher_id: uuid.UUID | None
    status: str
    created_at: datetime


class ReservationIn(BaseModel):
    product_id: uuid.UUID
    godown_id: uuid.UUID
    batch_id: uuid.UUID | None = None
    party_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    qty: Decimal = Field(gt=0)
    reference: str | None = None
    expires_on: date | None = None


class ReservationOut(ORM):
    id: uuid.UUID
    product_id: uuid.UUID
    godown_id: uuid.UUID
    batch_id: uuid.UUID | None
    party_id: uuid.UUID | None
    project_id: uuid.UUID | None
    qty: Decimal
    reference: str | None
    status: str
    expires_on: date | None
    created_at: datetime


class SampleIn(BaseModel):
    product_id: uuid.UUID
    party_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    qty: Decimal = Field(gt=0)
    issued_on: date
    expected_return_on: date | None = None
    notes: str | None = None


class SampleOut(ORM):
    id: uuid.UUID
    product_id: uuid.UUID
    party_id: uuid.UUID | None
    project_id: uuid.UUID | None
    qty: Decimal
    issued_on: date
    expected_return_on: date | None
    returned_on: date | None
    status: str
    notes: str | None


# ------------------------------------------------------------------ trade documents
class TradeLineIn(BaseModel):
    product_id: uuid.UUID
    description: str | None = None
    batch_id: uuid.UUID | None = None
    godown_id: uuid.UUID | None = None
    qty: Decimal = Field(gt=0)
    unit_symbol: str | None = None
    area_sqft: Decimal | None = None
    rate: Decimal = Field(ge=0)
    discount_pct: Decimal = Decimal("0")
    gst_rate: Decimal | None = None
    hsn_code: str | None = None


class TradeDocIn(BaseModel):
    date: date
    party_id: uuid.UUID
    due_date: date | None = None
    valid_till: date | None = None
    place_of_supply: str | None = None
    godown_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    reference_doc_id: uuid.UUID | None = None
    supplier_ref_no: str | None = None
    lines: list[TradeLineIn] = Field(min_length=1)
    paid_amount: Decimal = Decimal("0")
    payment_ledger_id: uuid.UUID | None = None
    notes: str | None = None
    terms: str | None = None
    salesman: str | None = None
    transporter: str | None = None
    vehicle_no: str | None = None
    eway_bill_no: str | None = None
    round_off_enabled: bool = True
    post: bool = False  # save & post in one call
    idempotency_key: str | None = None


class TradeLineOut(ORM):
    id: uuid.UUID
    line_no: int
    product_id: uuid.UUID
    description: str
    hsn_code: str | None
    batch_id: uuid.UUID | None
    godown_id: uuid.UUID | None
    qty: Decimal
    unit_symbol: str
    area_sqft: Decimal | None
    rate: Decimal
    discount_pct: Decimal
    discount_amount: Decimal
    taxable_amount: Decimal
    gst_rate: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    total: Decimal
    cost_rate: Decimal


class TradeDocOut(ORM):
    id: uuid.UUID
    branch_id: uuid.UUID | None
    doc_type: str
    doc_no: str
    date: date
    due_date: date | None
    valid_till: date | None
    party_id: uuid.UUID
    party_name: str
    party_gstin: str | None
    party_state_code: str
    place_of_supply: str
    is_interstate: bool
    godown_id: uuid.UUID | None
    project_id: uuid.UUID | None
    reference_doc_id: uuid.UUID | None
    supplier_ref_no: str | None
    status: str
    subtotal: Decimal
    discount_total: Decimal
    taxable_total: Decimal
    cgst_total: Decimal
    sgst_total: Decimal
    igst_total: Decimal
    round_off: Decimal
    grand_total: Decimal
    paid_amount: Decimal
    payment_ledger_id: uuid.UUID | None
    notes: str | None
    terms: str | None
    salesman: str | None
    transporter: str | None
    vehicle_no: str | None
    eway_bill_no: str | None
    irn: str | None
    voucher_id: uuid.UUID | None
    cogs_voucher_id: uuid.UUID | None
    receipt_voucher_id: uuid.UUID | None
    posted_at: datetime | None
    created_at: datetime
    lines: list[TradeLineOut]
    balance_due: Decimal | None = None


class TradeDocListOut(BaseModel):
    id: uuid.UUID
    doc_type: str
    doc_no: str
    date: date
    due_date: date | None
    party_id: uuid.UUID
    party_name: str
    status: str
    taxable_total: Decimal
    grand_total: Decimal
    paid_amount: Decimal
    balance_due: Decimal
    line_count: int


class ConvertIn(BaseModel):
    target_doc_type: str
    date: dt.date | None = None
    post: bool = False


# ------------------------------------------------------------------ tools
class TileCalcIn(BaseModel):
    area_sqft: Decimal | None = None
    area_sqm: Decimal | None = None
    length_ft: Decimal | None = None
    width_ft: Decimal | None = None
    sqft_per_box: Decimal = Field(gt=0)
    wastage_pct: Decimal = Decimal("7")
    pieces_per_box: Decimal | None = None
    rate_per_box: Decimal | None = None
    rate_per_sqft: Decimal | None = None


class TileCalcOut(BaseModel):
    area_sqft: Decimal
    wastage_pct: Decimal
    required_area_sqft: Decimal
    boxes_required: int
    pieces_required: int | None
    covered_area_sqft: Decimal
    surplus_sqft: Decimal
    estimated_amount: Decimal | None
    formula: str


class UnitConvertIn(BaseModel):
    product_id: uuid.UUID
    qty: Decimal
    from_unit: str  # box / sqft / sqm / piece / pallet
    to_unit: str


class Paginated(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int


class AIQueryIn(BaseModel):
    question: str = Field(min_length=2, max_length=500)


class WhatsAppSendIn(BaseModel):
    party_id: uuid.UUID
    template: Literal["invoice", "quotation", "outstanding_reminder", "payment_thanks", "delivery_update", "custom"]
    doc_id: uuid.UUID | None = None
    custom_body: str | None = None


class SyncPushIn(BaseModel):
    device_id: str
    operations: list[dict[str, Any]]
