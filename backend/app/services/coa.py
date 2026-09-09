"""Default chart of accounts + system ledgers for a new company."""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AccountGroup, FiscalYear, Godown, Ledger, Unit

# code, name, parent_code, nature, report, affects_gross_profit, sequence
GROUPS: list[tuple[str, str, str | None, str, str, bool, int]] = [
    ("ASSETS", "Assets", None, "asset", "balance_sheet", False, 10),
    ("FA", "Fixed Assets", "ASSETS", "asset", "balance_sheet", False, 11),
    ("CA", "Current Assets", "ASSETS", "asset", "balance_sheet", False, 12),
    ("CASH", "Cash-in-Hand", "CA", "asset", "balance_sheet", False, 13),
    ("BANK", "Bank Accounts", "CA", "asset", "balance_sheet", False, 14),
    ("DEBTORS", "Sundry Debtors", "CA", "asset", "balance_sheet", False, 15),
    ("STOCK", "Stock-in-Hand", "CA", "asset", "balance_sheet", False, 16),
    ("TAXASSET", "Duties & Taxes (Input)", "CA", "asset", "balance_sheet", False, 17),
    ("ADVANCES", "Loans & Advances (Asset)", "CA", "asset", "balance_sheet", False, 18),
    ("LIAB", "Liabilities", None, "liability", "balance_sheet", False, 20),
    ("CL", "Current Liabilities", "LIAB", "liability", "balance_sheet", False, 21),
    ("CREDITORS", "Sundry Creditors", "CL", "liability", "balance_sheet", False, 22),
    ("TAXLIAB", "Duties & Taxes (Output)", "CL", "liability", "balance_sheet", False, 23),
    ("PROVISIONS", "Provisions", "CL", "liability", "balance_sheet", False, 24),
    ("LOANS", "Loans (Liability)", "LIAB", "liability", "balance_sheet", False, 25),
    ("EQUITY", "Capital & Reserves", None, "equity", "balance_sheet", False, 30),
    ("CAPITAL", "Capital Account", "EQUITY", "equity", "balance_sheet", False, 31),
    ("RESERVES", "Reserves & Surplus", "EQUITY", "equity", "balance_sheet", False, 32),
    ("INCOME", "Income", None, "income", "profit_loss", False, 40),
    ("SALES", "Sales Accounts", "INCOME", "income", "profit_loss", True, 41),
    ("DIRINC", "Direct Income", "INCOME", "income", "profit_loss", True, 42),
    ("INDINC", "Indirect Income", "INCOME", "income", "profit_loss", False, 43),
    ("EXPENSE", "Expenses", None, "expense", "profit_loss", False, 50),
    ("COGSGRP", "Cost of Goods Sold", "EXPENSE", "expense", "profit_loss", True, 51),
    ("PURCHASE", "Purchase Accounts", "EXPENSE", "expense", "profit_loss", True, 52),
    ("DIREXP", "Direct Expenses", "EXPENSE", "expense", "profit_loss", True, 53),
    ("INDEXP", "Indirect Expenses", "EXPENSE", "expense", "profit_loss", False, 54),
]

# name, group_code, system_key, flags
LEDGERS: list[tuple[str, str, str | None, dict]] = [
    ("Cash", "CASH", "cash", {"is_cash": True}),
    ("Petty Cash", "CASH", None, {"is_cash": True}),
    ("Bank Account", "BANK", "bank", {"is_bank": True}),
    ("Stock-in-Hand", "STOCK", "inventory", {}),
    ("Input CGST", "TAXASSET", "input_cgst", {}),
    ("Input SGST", "TAXASSET", "input_sgst", {}),
    ("Input IGST", "TAXASSET", "input_igst", {}),
    ("Output CGST", "TAXLIAB", "output_cgst", {}),
    ("Output SGST", "TAXLIAB", "output_sgst", {}),
    ("Output IGST", "TAXLIAB", "output_igst", {}),
    ("TDS Payable", "TAXLIAB", "tds_payable", {}),
    ("TCS Payable", "TAXLIAB", "tcs_payable", {}),
    ("Owner's Capital", "CAPITAL", "capital", {}),
    ("Retained Earnings", "RESERVES", "retained_earnings", {}),
    ("Sales", "SALES", "sales", {}),
    ("Sales Returns", "SALES", "sales_return", {}),
    ("Round Off", "INDINC", "round_off", {}),
    ("Discount Received", "INDINC", "discount_received", {}),
    ("Cost of Goods Sold", "COGSGRP", "cogs", {}),
    ("Purchases", "PURCHASE", "purchase", {}),
    ("Purchase Returns", "PURCHASE", "purchase_return", {}),
    ("Freight Inward", "DIREXP", "freight_inward", {}),
    ("Stock Adjustment", "INDEXP", "stock_adjustment", {}),
    ("Discount Allowed", "INDEXP", "discount_allowed", {}),
    ("Rent", "INDEXP", None, {}),
    ("Salaries & Wages", "INDEXP", None, {}),
    ("Electricity", "INDEXP", None, {}),
    ("Transport & Delivery", "INDEXP", None, {}),
    ("Bank Charges", "INDEXP", None, {}),
    ("Bad Debts", "INDEXP", None, {}),
]

UNITS = [("Box", "Box", 2), ("Piece", "Pcs", 0), ("Square Feet", "Sqft", 2), ("Square Metre", "Sqm", 3), ("Kilogram", "Kg", 3), ("Metre", "Mtr", 2), ("Running Feet", "Rft", 2), ("Set", "Set", 0), ("Pair", "Pair", 0), ("Dozen", "Dzn", 0), ("Number", "Nos", 0), ("Bag", "Bag", 0), ("Carton", "Ctn", 0), ("Pallet", "Plt", 2), ("Litre", "Ltr", 2)]


async def setup_company_defaults(db: AsyncSession, tenant_id: uuid.UUID, company_id: uuid.UUID, branch_id: uuid.UUID | None, fy_start_month: int = 4, today=None) -> None:
    from datetime import date

    today = today or date.today()
    existing = (await db.execute(select(AccountGroup.id).where(AccountGroup.company_id == company_id).limit(1))).first()
    if existing:
        return
    groups: dict[str, AccountGroup] = {}
    for code, name, parent, nature, report, agp, seq in GROUPS:
        g = AccountGroup(tenant_id=tenant_id, company_id=company_id, name=name, code=code, parent_id=groups[parent].id if parent else None, nature=nature, report=report, affects_gross_profit=agp, sequence=seq, is_system=True)
        db.add(g)
        await db.flush()
        groups[code] = g
    for name, gcode, key, flags in LEDGERS:
        db.add(Ledger(tenant_id=tenant_id, company_id=company_id, name=name, group_id=groups[gcode].id, system_key=key, is_system=key is not None, opening_balance=Decimal("0"), **flags))
    for name, sym, dec in UNITS:
        db.add(Unit(tenant_id=tenant_id, company_id=company_id, name=name, symbol=sym, decimals=dec, is_system=True))
    db.add(Godown(tenant_id=tenant_id, company_id=company_id, branch_id=branch_id, name="Main Godown", code="MAIN", is_default=True))
    # fiscal year covering today (+ previous one for openings)
    y = today.year if today.month >= fy_start_month else today.year - 1
    for yy in (y - 1, y):
        start = date(yy, fy_start_month, 1)
        end = date(yy + 1, fy_start_month, 1) - __import__("datetime").timedelta(days=1)
        db.add(FiscalYear(tenant_id=tenant_id, company_id=company_id, name=f"{yy}-{str(yy + 1)[-2:]}", start_date=start, end_date=end))
    await db.flush()
