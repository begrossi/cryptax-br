from datetime import datetime
from pydantic import BaseModel, Field
from app.models.wallet import WalletType


class ExchangeCredentials(BaseModel):
    api_key: str
    api_secret: str


class WalletCreate(BaseModel):
    name: str = Field(max_length=100)
    wallet_type: WalletType
    # For exchanges: provide api_key + api_secret
    api_key: str | None = None
    api_secret: str | None = None
    # For on-chain wallets: provide address
    address: str | None = None
    is_brazilian_exchange: bool = True


class WalletRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    name: str
    wallet_type: WalletType
    is_brazilian_exchange: bool
    created_at: datetime
