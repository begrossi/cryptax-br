from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Wallet, WalletType
from app.schemas.wallet import WalletCreate, WalletRead
from app.services.crypto import encrypt_credentials

router = APIRouter(prefix="/wallets", tags=["wallets"])

ONCHAIN_TYPES = {WalletType.evm_address, WalletType.solana_address, WalletType.bitcoin_address}
EXCHANGE_TYPES = {WalletType.binance, WalletType.foxbit, WalletType.mercado_bitcoin}


@router.post("", response_model=WalletRead, status_code=201)
async def create_wallet(body: WalletCreate, db: AsyncSession = Depends(get_db)):
    if body.wallet_type in EXCHANGE_TYPES:
        if not body.api_key or not body.api_secret:
            raise HTTPException(400, "api_key and api_secret are required for exchange wallets")
        credentials = encrypt_credentials({"api_key": body.api_key, "api_secret": body.api_secret})
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
    return wallet


@router.get("", response_model=list[WalletRead])
async def list_wallets(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Wallet).order_by(Wallet.id))
    return result.scalars().all()


@router.delete("/{wallet_id}", status_code=204)
async def delete_wallet(wallet_id: int, db: AsyncSession = Depends(get_db)):
    wallet = await db.get(Wallet, wallet_id)
    if not wallet:
        raise HTTPException(404, "Wallet not found")
    await db.delete(wallet)
    await db.commit()
