from datetime import datetime
from pydantic import BaseModel, Field
from app.models.wallet import WalletType


class WalletCreate(BaseModel):
    name: str = Field(max_length=100)
    wallet_type: WalletType
    # Exchange credentials
    api_key: str | None = None
    api_secret: str | None = None
    # CCXT exchange ID (e.g. "binance", "kraken", "bybit") — required for ccxt_exchange type
    exchange_id: str | None = None
    # Optional passphrase — required by some exchanges (OKX, Coinbase Pro, etc.)
    password: str | None = None
    # On-chain wallets
    address: str | None = None
    is_brazilian_exchange: bool = True


class WalletRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    name: str
    wallet_type: WalletType
    is_brazilian_exchange: bool
    created_at: datetime
    # Derived from credentials at read time — never exposes keys
    exchange_id: str | None = None


class ExchangeInfo(BaseModel):
    id: str
    name: str
    popular: bool = False
