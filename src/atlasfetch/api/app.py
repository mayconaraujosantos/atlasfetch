"""Aplicação FastAPI."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from atlasfetch.api.routes import faturas, sync


@asynccontextmanager
async def lifespan(app: FastAPI):
    from database import init_db
    init_db()
    try:
        from scheduler import start_scheduler
        start_scheduler()
    except ImportError:
        pass
    yield
    try:
        from scheduler import stop_scheduler
        stop_scheduler()
    except ImportError:
        pass


app = FastAPI(
    title="Atlasfetch API",
    description="API de faturas Águas de Manaus",
    lifespan=lifespan,
)

app.include_router(faturas.router)
app.include_router(sync.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
