import ccxt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Wallet, WalletType
from app.schemas.wallet import WalletCreate, WalletRead, ExchangeInfo
from app.services.crypto import encrypt_credentials, decrypt_credentials

router = APIRouter(prefix="/wallets", tags=["wallets"])
exchanges_router = APIRouter(prefix="/exchanges", tags=["exchanges"])

ONCHAIN_TYPES = {WalletType.evm_address, WalletType.solana_address, WalletType.bitcoin_address}
EXCHANGE_TYPES = {WalletType.ccxt_exchange, WalletType.binance, WalletType.foxbit, WalletType.mercado_bitcoin}

# Exchanges to surface prominently in the UI
POPULAR_EXCHANGES = {
    "binance", "binanceus", "foxbit", "mercadobitcoin",
    "coinbase", "coinbaseadvanced", "kraken", "bybit",
    "okx", "kucoin", "bitfinex", "huobi", "gate", "bitstamp",
    "gemini", "poloniex", "bitget", "mexc",
}

# Legacy enum values → CCXT exchange IDs (for wallets created before CCXT integration)
LEGACY_CCXT_MAP = {
    WalletType.binance: "binance",
    WalletType.foxbit: "foxbit",
    WalletType.mercado_bitcoin: "mercadobitcoin",
}


def _read_exchange_id(wallet: Wallet) -> str | None:
    """Extract exchange_id from a wallet's credentials, supporting both new and legacy types."""
    if wallet.wallet_type in LEGACY_CCXT_MAP:
        return LEGACY_CCXT_MAP[wallet.wallet_type]
    if wallet.wallet_type == WalletType.ccxt_exchange:
        try:
            return decrypt_credentials(wallet.credentials).get("exchange_id")
        except Exception:
            return None
    return None


@exchanges_router.get("", response_model=list[ExchangeInfo])
async def list_exchanges():
    """Return all CCXT-supported exchanges, with popular ones flagged."""
    result = []
    for exchange_id in sorted(ccxt.exchanges):
        try:
            cls = getattr(ccxt, exchange_id)
            name = getattr(cls, "name", exchange_id) or exchange_id
        except Exception:
            name = exchange_id
        result.append(ExchangeInfo(
            id=exchange_id,
            name=name,
            popular=exchange_id in POPULAR_EXCHANGES,
        ))
    return result


@router.post("", response_model=WalletRead, status_code=201)
async def create_wallet(body: WalletCreate, db: AsyncSession = Depends(get_db)):
    if body.wallet_type in EXCHANGE_TYPES:
        if not body.api_key or not body.api_secret:
            raise HTTPException(400, "api_key and api_secret are required for exchange wallets")
        if body.wallet_type == WalletType.ccxt_exchange:
            if not body.exchange_id:
                raise HTTPException(400, "exchange_id is required for ccxt_exchange wallets")
            if body.exchange_id not in ccxt.exchanges:
                raise HTTPException(400, f"'{body.exchange_id}' is not a supported CCXT exchange")
        creds: dict = {"api_key": body.api_key, "api_secret": body.api_secret}
        if body.exchange_id:
            creds["exchange_id"] = body.exchange_id
        if body.password:
            creds["password"] = body.password
        credentials = encrypt_credentials(creds)

    elif body.wallet_type in ONCHAIN_TYPES:
        if not body.address:
            raise HTTPException(400, "address is required for on-chain wallets")
        credentials = body.address
    else:
        raise HTTPException(400, "Unsupported wallet type")

    wallet = Wallet(
        name=body.name,
        wallet_type=body.wallet_type,
        credentials=credentials,
        is_brazilian_exchange=body.is_brazilian_exchange,
    )
    db.add(wallet)
    await db.commit()
    await db.refresh(wallet)

    read = WalletRead.model_validate(wallet)
    read.exchange_id = _read_exchange_id(wallet)
    return read


@router.get("", response_model=list[WalletRead])
async def list_wallets(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Wallet).order_by(Wallet.id))
    wallets = result.scalars().all()
    out = []
    for w in wallets:
        r = WalletRead.model_validate(w)
        r.exchange_id = _read_exchange_id(w)
        out.append(r)
    return out


@router.delete("/{wallet_id}", status_code=204)
async def delete_wallet(wallet_id: int, db: AsyncSession = Depends(get_db)):
    wallet = await db.get(Wallet, wallet_id)
    if not wallet:
        raise HTTPException(404, "Wallet not found")
    await db.delete(wallet)
    await db.commit()
