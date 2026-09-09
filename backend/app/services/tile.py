"""Tile & sanitaryware domain functions: area/box/wastage and unit conversions.

Worked example (must hold):
  1,000 SQFT, 16 SQFT/box, 7% wastage -> required 1,070 SQFT -> ceil(1070/16) = 67 boxes
"""
from __future__ import annotations

import math
from decimal import Decimal

from fastapi import HTTPException

from ..models import Product
from ..schemas import TileCalcIn, TileCalcOut
from .common import ZERO, money, qty

SQM_TO_SQFT = Decimal("10.7639")


def boxes_for_area(area_sqft: Decimal, sqft_per_box: Decimal, wastage_pct: Decimal = ZERO) -> tuple[Decimal, int]:
    if sqft_per_box <= ZERO:
        raise HTTPException(422, "sqft_per_box must be positive")
    required = qty(area_sqft * (Decimal("1") + wastage_pct / Decimal("100")))
    boxes = math.ceil(required / sqft_per_box)
    return required, boxes


def fmt(d: Decimal) -> str:
    s = f"{d:f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def tile_calc(inp: TileCalcIn) -> TileCalcOut:
    if inp.area_sqft is not None:
        area = qty(inp.area_sqft)
    elif inp.area_sqm is not None:
        area = qty(inp.area_sqm * SQM_TO_SQFT)
    elif inp.length_ft is not None and inp.width_ft is not None:
        area = qty(inp.length_ft * inp.width_ft)
    else:
        raise HTTPException(422, "Provide area_sqft, area_sqm, or length_ft + width_ft")
    if area <= ZERO:
        raise HTTPException(422, "Area must be positive")
    required, boxes = boxes_for_area(area, inp.sqft_per_box, inp.wastage_pct)
    covered = qty(Decimal(boxes) * inp.sqft_per_box)
    pieces = int(Decimal(boxes) * inp.pieces_per_box) if inp.pieces_per_box else None
    amount = None
    if inp.rate_per_box is not None:
        amount = money(Decimal(boxes) * inp.rate_per_box)
    elif inp.rate_per_sqft is not None:
        amount = money(covered * inp.rate_per_sqft)
    return TileCalcOut(
        area_sqft=area,
        wastage_pct=inp.wastage_pct,
        required_area_sqft=required,
        boxes_required=boxes,
        pieces_required=pieces,
        covered_area_sqft=covered,
        surplus_sqft=qty(covered - area),
        estimated_amount=amount,
        formula=f"ceil(({fmt(area)} sqft x (1 + {fmt(inp.wastage_pct)}%)) / {fmt(inp.sqft_per_box)} sqft/box) = ceil({fmt(required)} / {fmt(inp.sqft_per_box)}) = {boxes} boxes",
    )


def convert_units(product: Product, quantity: Decimal, from_unit: str, to_unit: str) -> Decimal:
    """Convert between box / piece / sqft / sqm / pallet for a product using its defined factors."""
    from_unit, to_unit = from_unit.lower(), to_unit.lower()
    base_sym = product.stock_unit.symbol.lower()

    def to_boxes(q: Decimal, u: str) -> Decimal:
        if u in (base_sym, "box"):
            return q
        if u in ("piece", "pcs", "pc"):
            if not product.pieces_per_box:
                raise HTTPException(422, f"{product.name}: pieces per box not defined")
            return q / product.pieces_per_box
        if u == "sqft":
            if not product.sqft_per_box:
                raise HTTPException(422, f"{product.name}: sqft per box not defined")
            return q / product.sqft_per_box
        if u == "sqm":
            per_box = product.sqm_per_box or (product.sqft_per_box / SQM_TO_SQFT if product.sqft_per_box else None)
            if not per_box:
                raise HTTPException(422, f"{product.name}: sqm per box not defined")
            return q / per_box
        if u == "pallet":
            if not product.boxes_per_pallet:
                raise HTTPException(422, f"{product.name}: boxes per pallet not defined")
            return q * product.boxes_per_pallet
        raise HTTPException(422, f"Unknown unit {u}")

    def from_boxes(b: Decimal, u: str) -> Decimal:
        if u in (base_sym, "box"):
            return b
        if u in ("piece", "pcs", "pc"):
            return b * (product.pieces_per_box or ZERO)
        if u == "sqft":
            return b * (product.sqft_per_box or ZERO)
        if u == "sqm":
            per_box = product.sqm_per_box or (product.sqft_per_box / SQM_TO_SQFT if product.sqft_per_box else ZERO)
            return b * per_box
        if u == "pallet":
            if not product.boxes_per_pallet:
                raise HTTPException(422, f"{product.name}: boxes per pallet not defined")
            return b / product.boxes_per_pallet
        raise HTTPException(422, f"Unknown unit {u}")

    return qty(from_boxes(to_boxes(quantity, from_unit), to_unit))
