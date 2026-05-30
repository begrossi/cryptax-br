import enum
from datetime import datetime

from sqlalchemy import String, Enum, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class WalletType(str, enum.Enum):
    # Generic CCXT exchange — exchange_id stored in credentials JSON
    ccxt_exchange = "ccxt_exchange"
    # Legacy values kept for backward compatibility (map to CCXT IDs in sync_service)
    binance = "binance"
    foxbit = "foxbit"
    mercado_bitcoin = "mercado_bitcoin"
    # On-chain addresses
    evm_address = "evm_address"
    solana_address = "solana_address"
    bitcoin_address = "bitcoin_address"


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    wallet_type: Mapped[WalletType] = mapped_column(Enum(WalletType))
    # For exchanges: encrypted JSON {"api_key": "...", "api_secret": "..."}
    # For on-chain: the address itself (public, no encryption needed)
    credentials: Mapped[str] = mapped_column(String(2000))
    # Brazilian exchange flag affects DARF threshold (R$35k exempt only for BR exchanges)
    is_brazilian_exchange: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="wallet")
    sync_logs: Mapped[list["SyncLog"]] = relationship(back_populates="wallet")
