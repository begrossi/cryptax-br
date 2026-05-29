from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass
class RawTransaction:
    """Normalized transaction from any exchange."""
    external_id: str
    executed_at: date
    transaction_type: str  # TransactionType enum value
    asset: str
    amount: Decimal
    total_quote: Decimal   # amount in quote currency (BRL, USDT, etc.)
    quote_currency: str    # "BRL", "USDT", "BUSD", etc.
    counterpart_asset: str | None = None
    counterpart_amount: Decimal | None = None
    notes: str | None = None


class BaseExchange(ABC):
    @abstractmethod
    async def fetch_transactions(
        self, api_key: str, api_secret: str, since: date | None = None
    ) -> list[RawTransaction]:
        ...
