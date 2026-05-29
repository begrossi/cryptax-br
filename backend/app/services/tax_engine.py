"""
Brazilian crypto tax calculation engine.

Rules implemented:
- Cost basis: custo médio ponderado (weighted average cost)
- IRPF gains: taxed progressively (15% up to R$5M, 17.5% up to R$10M, 20% up to R$30M, 22.5% above)
- Brazilian exchange exemption: if total monthly gains <= R$35k, no DARF due
- Foreign exchange: gains always taxable regardless of amount
- IN RFB 1888: self-reporting required when monthly volume on foreign exchange > R$30k
- COAF: flag single transactions > R$10k
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

DARF_EXEMPT_BRL = Decimal("35000")      # BR exchange monthly exemption
IN1888_THRESHOLD_BRL = Decimal("30000") # Foreign exchange self-report threshold
COAF_THRESHOLD_BRL = Decimal("10000")   # Single transaction AML threshold

TAX_BRACKETS = [
    (Decimal("5000000"), Decimal("0.15")),
    (Decimal("10000000"), Decimal("0.175")),
    (Decimal("30000000"), Decimal("0.20")),
    (Decimal("inf"), Decimal("0.225")),
]


@dataclass
class TxRecord:
    """Minimal transaction data needed by the tax engine."""
    id: int
    wallet_id: int
    wallet_name: str
    is_brazilian_exchange: bool
    executed_at: date
    transaction_type: str
    asset: str
    amount: Decimal
    total_brl: Decimal | None
    counterpart_asset: str | None = None
    counterpart_amount: Decimal | None = None


@dataclass
class MonthKey:
    year: int
    month: int

    def __hash__(self):
        return hash((self.year, self.month))

    def __eq__(self, other):
        return self.year == other.year and self.month == other.month


def compute_tax_rate(gain_brl: Decimal) -> Decimal:
    for bracket_limit, rate in TAX_BRACKETS:
        if gain_brl <= bracket_limit:
            return rate
    return Decimal("0.225")


def last_business_day(year: int, month: int) -> date:
    """Return last business day (Mon–Fri) of the given year/month."""
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    last = next_month - timedelta(days=1)
    while last.weekday() >= 5:  # Sat=5, Sun=6
        last -= timedelta(days=1)
    return last


def darf_due_date(year: int, month: int) -> str:
    """DARF for month M is due on last business day of month M+1."""
    if month == 12:
        return last_business_day(year + 1, 1).isoformat()
    return last_business_day(year, month + 1).isoformat()


def compute_gains(transactions: list[TxRecord]) -> dict[MonthKey, dict[str, dict]]:
    """
    Compute per-asset, per-month gains using custo médio ponderado.
    Returns: {MonthKey: {asset: {"gain": Decimal, "loss": Decimal, "avg_cost": Decimal,
                                  "proceeds": Decimal, "buy_amount": Decimal, "sell_amount": Decimal}}}
    """
    # Running average cost per asset: {asset: {"total_cost": Decimal, "quantity": Decimal}}
    cost_basis: dict[str, dict] = defaultdict(lambda: {"total_cost": Decimal(0), "quantity": Decimal(0)})

    # Sort by date to maintain running average
    txs = sorted(transactions, key=lambda t: t.executed_at)

    monthly: dict[MonthKey, dict[str, dict]] = defaultdict(
        lambda: defaultdict(lambda: {
            "gain": Decimal(0), "loss": Decimal(0),
            "proceeds": Decimal(0), "avg_cost_at_sale": Decimal(0),
            "buy_amount": Decimal(0), "sell_amount": Decimal(0),
        })
    )

    for tx in txs:
        mk = MonthKey(tx.executed_at.year, tx.executed_at.month)
        brl = tx.total_brl or Decimal(0)

        if tx.transaction_type in ("buy", "transfer_in", "earn", "swap_in"):
            cb = cost_basis[tx.asset]
            cb["total_cost"] += brl
            cb["quantity"] += tx.amount
            monthly[mk][tx.asset]["buy_amount"] += tx.amount

        elif tx.transaction_type in ("sell", "transfer_out", "swap_out"):
            cb = cost_basis[tx.asset]
            avg = cb["total_cost"] / cb["quantity"] if cb["quantity"] > 0 else Decimal(0)
            cost_of_sold = avg * tx.amount
            gain = brl - cost_of_sold

            monthly[mk][tx.asset]["sell_amount"] += tx.amount
            monthly[mk][tx.asset]["proceeds"] += brl
            monthly[mk][tx.asset]["avg_cost_at_sale"] = avg

            if gain > 0:
                monthly[mk][tx.asset]["gain"] += gain
            else:
                monthly[mk][tx.asset]["loss"] += abs(gain)

            # Reduce cost basis
            cb["total_cost"] = max(Decimal(0), cb["total_cost"] - cost_of_sold)
            cb["quantity"] = max(Decimal(0), cb["quantity"] - tx.amount)

    return {k: dict(v) for k, v in monthly.items()}


def get_cost_basis_snapshot(transactions: list[TxRecord]) -> dict[str, dict]:
    """Return current cost basis for all assets (for IRPF bens e direitos)."""
    cost_basis: dict[str, dict] = defaultdict(lambda: {"total_cost": Decimal(0), "quantity": Decimal(0)})
    for tx in sorted(transactions, key=lambda t: t.executed_at):
        if tx.transaction_type in ("buy", "transfer_in", "earn", "swap_in"):
            cb = cost_basis[tx.asset]
            cb["total_cost"] += tx.total_brl or Decimal(0)
            cb["quantity"] += tx.amount
        elif tx.transaction_type in ("sell", "transfer_out", "swap_out"):
            cb = cost_basis[tx.asset]
            if cb["quantity"] > 0:
                avg = cb["total_cost"] / cb["quantity"]
                cb["total_cost"] = max(Decimal(0), cb["total_cost"] - avg * tx.amount)
                cb["quantity"] = max(Decimal(0), cb["quantity"] - tx.amount)
    return {k: v for k, v in cost_basis.items() if v["quantity"] > 0}


def darf_obligations(transactions: list[TxRecord], year: int) -> list[dict]:
    """Calculate DARF obligations for each month of the given year."""
    monthly_gains = compute_gains(transactions)
    obligations = []

    for month in range(1, 13):
        mk = MonthKey(year, month)
        if mk not in monthly_gains:
            continue

        month_data = monthly_gains[mk]
        total_gain = sum(d["gain"] for d in month_data.values())
        total_loss = sum(d["loss"] for d in month_data.values())
        net_gain = total_gain - total_loss
        if net_gain <= 0:
            continue

        # Determine if foreign transactions are involved
        month_txs = [t for t in transactions
                     if t.executed_at.year == year and t.executed_at.month == month]
        has_foreign = any(not t.is_brazilian_exchange for t in month_txs)

        if has_foreign:
            exempt = Decimal(0)
            reason = "Operações em exchanges estrangeiras: isenção de R$35k não se aplica"
        else:
            exempt = DARF_EXEMPT_BRL
            reason = None

        taxable = max(Decimal(0), net_gain - exempt)
        if taxable <= 0:
            continue

        rate = compute_tax_rate(taxable)
        tax_due = (taxable * rate).quantize(Decimal("0.01"))

        obligations.append({
            "year": year,
            "month": month,
            "net_gain_brl": net_gain,
            "exempt_threshold_brl": exempt,
            "taxable_gain_brl": taxable,
            "tax_rate": rate,
            "tax_due_brl": tax_due,
            "due_date": darf_due_date(year, month),
            "is_foreign": has_foreign,
            "reason": reason,
        })

    return obligations


def in1888_report(transactions: list[TxRecord], year: int) -> list[dict]:
    """Flag months where volume on foreign exchanges exceeds R$30k."""
    entries = []
    month_volume: dict[tuple, Decimal] = defaultdict(Decimal)
    month_count: dict[tuple, int] = defaultdict(int)
    wallet_info: dict[int, dict] = {}

    for tx in transactions:
        if tx.is_brazilian_exchange:
            continue
        mk = (tx.executed_at.year, tx.executed_at.month, tx.wallet_id)
        month_volume[mk] += tx.total_brl or Decimal(0)
        month_count[mk] += 1
        wallet_info[tx.wallet_id] = {"name": tx.wallet_name}

    for (yr, mo, wid), volume in month_volume.items():
        if yr != year:
            continue
        entries.append({
            "year": yr,
            "month": mo,
            "wallet_name": wallet_info[wid]["name"],
            "transaction_count": month_count[(yr, mo, wid)],
            "total_volume_brl": volume,
            "must_report": volume > IN1888_THRESHOLD_BRL,
        })

    return sorted(entries, key=lambda e: (e["year"], e["month"]))


def coaf_alerts(transactions: list[TxRecord]) -> list[dict]:
    """Return transactions exceeding the COAF R$10k threshold."""
    alerts = []
    for tx in transactions:
        brl = tx.total_brl or Decimal(0)
        if brl > COAF_THRESHOLD_BRL:
            alerts.append({
                "transaction_id": tx.id,
                "executed_at": tx.executed_at.isoformat(),
                "asset": tx.asset,
                "amount": tx.amount,
                "total_brl": brl,
                "wallet_name": tx.wallet_name,
                "reason": f"Transação única acima de R${COAF_THRESHOLD_BRL:,.0f}",
            })
    return alerts
