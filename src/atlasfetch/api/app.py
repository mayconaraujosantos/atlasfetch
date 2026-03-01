"""Aplicação FastAPI."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlasfetch.api.routes import faturas, sync


@asynccontextmanager
async def lifespan(app: FastAPI):
    from atlasfetch.infrastructure.persistence.database import init_db
    init_db()
    # Scheduler NÃO inicia com a API - rode separadamente: make scheduler
    yield


app = FastAPI(
    title="Atlasfetch API",
    description="API de faturas Águas de Manaus",
    version="0.2.0",
    lifespan=lifespan,
    servers=[
        {"url": "http://localhost:8000", "description": "Local"},
        {"url": "http://127.0.0.1:8000", "description": "Local (127.0.0.1)"},
    ],
    swagger_ui_parameters={"tryItOutEnabled": True},
)

app.include_router(faturas.router)
app.include_router(sync.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}
