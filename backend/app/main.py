from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import wallets, sync, transactions, tax
from app.routers.wallets import exchanges_router


@asynccontextmanager
async def lifespan(app: FastAPI):
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

app.include_router(wallets.router)
app.include_router(exchanges_router)
app.include_router(sync.router)
app.include_router(transactions.router)
app.include_router(tax.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "cryptax-br"}
