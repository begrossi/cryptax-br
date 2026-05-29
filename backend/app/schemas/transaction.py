from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel
from app.models.transaction import TransactionType


class TransactionRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    wallet_id: int
    external_id: str
    executed_at: datetime
    transaction_type: TransactionType
    asset: str
    amount: Decimal
    price_brl: Decimal | None
    total_brl: Decimal | None
    cost_basis_brl: Decimal | None
    counterpart_asset: str | None
    counterpart_amount: Decimal | None
    chain: str | None
    notes: str | None


class TransactionSummary(BaseModel):
    year: int
    month: int
    asset: str
    buy_total_brl: Decimal
    sell_total_brl: Decimal
    gain_brl: Decimal
    transaction_count: int
