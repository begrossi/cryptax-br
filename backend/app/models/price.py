from datetime import date
from decimal import Decimal

from sqlalchemy import String, Date, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AssetPrice(Base):
    __tablename__ = "asset_prices"
    __table_args__ = (UniqueConstraint("asset", "date", name="uq_asset_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    asset: Mapped[str] = mapped_column(String(20))
    date: Mapped[date] = mapped_column(Date)
    price_brl: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    source: Mapped[str] = mapped_column(String(50), default="coingecko")
