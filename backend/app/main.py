import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import require_api_token
from app.config import settings
from app.database import init_db
from app.routers import wallets, sync, transactions, tax
from app.routers.wallets import exchanges_router

logger = logging.getLogger("cryptax")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.api_token:
        logger.warning(
            "API_TOKEN is not set — the backend API is UNAUTHENTICATED and open to "
            "anyone who can reach it. Set API_TOKEN before exposing this service."
        )
    await init_db()
    yield


app = FastAPI(
    title="cryptax-br",
    description="Declaração de criptomoedas para a Receita Federal brasileira. Open-source, local-first.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_protected = [Depends(require_api_token)]
app.include_router(wallets.router, dependencies=_protected)
app.include_router(exchanges_router, dependencies=_protected)
app.include_router(sync.router, dependencies=_protected)
app.include_router(transactions.router, dependencies=_protected)
app.include_router(tax.router, dependencies=_protected)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "cryptax-br"}
