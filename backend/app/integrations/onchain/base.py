from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass
class OnChainTransaction:
    external_id: str
    executed_at: date
    transaction_type: str
    asset: str
    amount: Decimal
    chain: str
    from_address: str
    to_address: str
    notes: str | None = None


class BaseOnChainProvider(ABC):
    @abstractmethod
    async def fetch_transactions(
        self, address: str, since: date | None = None
    ) -> list[OnChainTransaction]:
        ...
