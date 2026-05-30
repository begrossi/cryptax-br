import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, Enum, DateTime, Numeric, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TransactionType(str, enum.Enum):
    buy = "buy"
    sell = "sell"
    swap_in = "swap_in"     # received side of a DeFi swap
    swap_out = "swap_out"   # sent side of a DeFi swap
    transfer_in = "transfer_in"
    transfer_out = "transfer_out"
    earn = "earn"           # staking rewards, airdrops
    fee = "fee"             # on-chain gas fees paid in native token


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("wallet_id", "external_id", name="uq_wallet_external"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    wallet_id: Mapped[int] = mapped_column(ForeignKey("wallets.id"))
    external_id: Mapped[str] = mapped_column(String(200))  # tx hash or exchange order ID

    executed_at: Mapped[datetime] = mapped_column(DateTime)
    transaction_type: Mapped[TransactionType] = mapped_column(Enum(TransactionType))

    asset: Mapped[str] = mapped_column(String(20))       # e.g. "BTC", "ETH"
    amount: Mapped[Decimal] = mapped_column(Numeric(36, 18))  # raw asset units

    # BRL values at time of transaction (fetched from price cache)
    price_brl: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    total_brl: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)

    # Cost basis at time of this tx (populated by tax engine after sync)
    cost_basis_brl: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)

    # For swaps: the other side asset (e.g. ETH→USDC: counterpart_asset="USDC")
    counterpart_asset: Mapped[str | None] = mapped_column(String(20), nullable=True)
    counterpart_amount: Mapped[Decimal | None] = mapped_column(Numeric(36, 18), nullable=True)

    chain: Mapped[str | None] = mapped_column(String(30), nullable=True)  # "ethereum", "bsc", etc.
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # True = moving between own wallets; skipped in all tax calculations
    is_self_transfer: Mapped[bool] = mapped_column(default=False, server_default="0")

    wallet: Mapped["Wallet"] = relationship(back_populates="transactions")
