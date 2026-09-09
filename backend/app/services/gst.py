"""GST computation (CGST/SGST for intra-state, IGST for inter-state)."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from .common import ZERO, money

HUNDRED = Decimal("100")


def compute_line(qty: Decimal, rate: Decimal, discount_pct: Decimal, gst_rate: Decimal, interstate: bool) -> dict[str, Decimal]:
    gross = money(qty * rate)
    discount = money(gross * discount_pct / HUNDRED) if discount_pct else ZERO
    taxable = money(gross - discount)
    tax = money(taxable * gst_rate / HUNDRED)
    if interstate:
        cgst, sgst, igst = ZERO, ZERO, tax
    else:
        half = money(tax / 2)
        cgst, sgst, igst = half, money(tax - half), ZERO
    return {
        "gross": gross,
        "discount_amount": discount,
        "taxable_amount": taxable,
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "total": money(taxable + cgst + sgst + igst),
    }


def compute_totals(lines: list[dict[str, Decimal]], round_off_enabled: bool = True) -> dict[str, Decimal]:
    subtotal = money(sum((l["gross"] for l in lines), ZERO))
    discount = money(sum((l["discount_amount"] for l in lines), ZERO))
    taxable = money(sum((l["taxable_amount"] for l in lines), ZERO))
    cgst = money(sum((l["cgst"] for l in lines), ZERO))
    sgst = money(sum((l["sgst"] for l in lines), ZERO))
    igst = money(sum((l["igst"] for l in lines), ZERO))
    raw_total = money(taxable + cgst + sgst + igst)
    if round_off_enabled:
        grand = raw_total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        round_off = money(grand - raw_total)
    else:
        grand, round_off = raw_total, ZERO
    return {
        "subtotal": subtotal,
        "discount_total": discount,
        "taxable_total": taxable,
        "cgst_total": cgst,
        "sgst_total": sgst,
        "igst_total": igst,
        "round_off": round_off,
        "grand_total": money(grand),
    }


INDIAN_STATES = {
    "01": "Jammu & Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh", "05": "Uttarakhand", "06": "Haryana", "07": "Delhi",
    "08": "Rajasthan", "09": "Uttar Pradesh", "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal", "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh",
    "23": "Madhya Pradesh", "24": "Gujarat", "26": "Dadra & Nagar Haveli and Daman & Diu", "27": "Maharashtra", "29": "Karnataka", "30": "Goa",
    "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry", "35": "Andaman & Nicobar", "36": "Telangana", "37": "Andhra Pradesh", "38": "Ladakh",
}
