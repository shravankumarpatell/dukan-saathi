from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from .config import get_settings
from .routers import accounting, auth, inventory, parties, reports, settings as settings_router, stretch, tools, trade

log = logging.getLogger("tileos")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
settings = get_settings()
BACKEND_DIR = Path(__file__).resolve().parent.parent


def bootstrap_postgres() -> None:
    """Dev convenience: make sure the local PostgreSQL is up (self-healing across pod restarts)."""
    if not settings.auto_bootstrap_pg or "127.0.0.1" not in settings.database_url and "localhost" not in settings.database_url:
        return
    script = BACKEND_DIR.parent / "scripts" / "ensure_pg.sh"
    if script.exists():
        try:
            out = subprocess.run(["bash", str(script)], capture_output=True, text=True, timeout=240)
            if out.returncode != 0:
                log.error("ensure_pg failed: %s %s", out.stdout[-2000:], out.stderr[-2000:])
            else:
                log.info("PostgreSQL ready")
        except Exception as e:  # noqa: BLE001
            log.exception("ensure_pg error: %s", e)


def run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(bootstrap_postgres)
    await asyncio.to_thread(run_migrations)
    log.info("Migrations applied")
    if settings.seed_on_start:
        from .seed import seed_if_empty

        try:
            await seed_if_empty()
        except Exception as e:  # noqa: BLE001
            log.exception("Seeding failed: %s", e)
    yield


app = FastAPI(title="TileOS API", version="1.0.0", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(IntegrityError)
async def integrity_handler(request: Request, exc: IntegrityError):
    msg = str(exc.orig) if exc.orig else str(exc)
    detail = "Duplicate or invalid reference"
    if "unique" in msg.lower() or "duplicate" in msg.lower():
        detail = "A record with the same unique value already exists"
    elif "foreign key" in msg.lower():
        detail = "Referenced record does not exist or is still in use"
    return JSONResponse(status_code=409, content={"detail": detail, "db_error": msg.split("\n")[0][:300]})


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errors = [{"field": ".".join(str(x) for x in e.get("loc", [])[1:]), "message": e.get("msg")} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": "; ".join(f"{e['field']}: {e['message']}" for e in errors) or "Validation error", "errors": errors})


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    log.exception("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=500, content={"detail": f"Internal error: {type(exc).__name__}: {str(exc)[:300]}"})


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.app_name, "env": settings.env}


for r in (auth.router, settings_router.router, accounting.router, reports.router, parties.router, inventory.router, trade.router, tools.router, stretch.router):
    app.include_router(r, prefix="/api")
