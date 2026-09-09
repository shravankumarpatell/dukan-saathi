from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import Ctx, get_ctx
from ..schemas import TileCalcIn, TileCalcOut
from ..services.gst import INDIAN_STATES
from ..services.tile import tile_calc

router = APIRouter(prefix="/tools", tags=["tools"])


@router.post("/tile-calculator", response_model=TileCalcOut)
async def tile_calculator(data: TileCalcIn, ctx: Ctx = Depends(get_ctx)):
    return tile_calc(data)


@router.get("/states")
async def states():
    return [{"code": k, "name": v} for k, v in sorted(INDIAN_STATES.items())]
