from decimal import Decimal
from pydantic import BaseModel


class AssetGain(BaseModel):
    asset: str
    buy_amount: Decimal
    sell_amount: Decimal
    avg_cost_brl: Decimal
    proceeds_brl: Decimal
    gain_brl: Decimal
    is_taxable: bool


class GainReport(BaseModel):
    year: int
    month: int
    assets: list[AssetGain]
    total_gain_brl: Decimal
    total_loss_brl: Decimal
    net_gain_brl: Decimal
    is_taxable: bool
    taxable_reason: str | None


class DARFObligation(BaseModel):
    year: int
    month: int
    darf_code: str           # "4600" (BR exchange) or "0507" (foreign exchange)
    is_foreign: bool
    net_gain_brl: Decimal
    carryforward_applied_brl: Decimal
    exempt_threshold_brl: Decimal
    taxable_gain_brl: Decimal
    tax_due_brl: Decimal
    effective_rate: Decimal  # tax_due / taxable_gain (progressive, not flat)
    due_date: str


class DARFReport(BaseModel):
    year: int
    obligations: list[DARFObligation]
    total_tax_due_brl: Decimal


class IRPFAsset(BaseModel):
    asset: str
    codigo_bem: str = "89"  # Receita Federal code for crypto
    quantity: Decimal
    avg_cost_brl: Decimal
    total_cost_brl: Decimal
    description: str


class EarnIncomeEntry(BaseModel):
    asset: str
    total_brl: Decimal
    transaction_count: int


class IRPFReport(BaseModel):
    year: int
    assets: list[IRPFAsset]
    total_cost_brl: Decimal
    exempt_gains_brl: Decimal   # gains from BR exchanges below R$35k/month
    taxable_gains_brl: Decimal  # gains paid via DARF
    earn_income: list[EarnIncomeEntry]   # staking rewards / airdrops received
    earn_income_total_brl: Decimal


class IN1888Entry(BaseModel):
    year: int
    month: int
    wallet_name: str
    wallet_type: str
    transaction_count: int
    total_volume_brl: Decimal
    must_report: bool  # volume > R$30k


class IN1888Report(BaseModel):
    year: int
    entries: list[IN1888Entry]
    months_requiring_report: list[int]


class COAFAlert(BaseModel):
    transaction_id: int
    executed_at: str
    asset: str
    amount: Decimal
    total_brl: Decimal
    wallet_name: str
    reason: str  # "Single transaction > R$10k"
