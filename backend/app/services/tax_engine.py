"""
Brazilian crypto tax calculation engine.

Rules implemented:
- Cost basis: custo médio ponderado (weighted average cost), unified pool across all wallets
- Brazilian exchange gains (code 4600): R$35k/month exemption; losses carry forward
- Foreign exchange gains (code 0507): always taxable, no exemption; losses carry forward
- BR and foreign carryforwards are tracked separately (different tax regimes)
- Tax: progressive brackets (15% / 17.5% / 20% / 22.5%) applied tier-by-tier
- IN RFB 1888: self-reporting when monthly trade volume on foreign exchange > R$30k
- COAF: flag single transactions > R$10k
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

DARF_EXEMPT_BRL = Decimal("35000")       # BR exchange monthly exemption
IN1888_THRESHOLD_BRL = Decimal("30000")  # Foreign exchange self-report threshold
COAF_THRESHOLD_BRL = Decimal("10000")    # Single-transaction AML threshold

# (upper_limit, marginal_rate) — last bracket has no upper limit sentinel
TAX_BRACKETS = [
    (Decimal("5000000"),  Decimal("0.15")),
    (Decimal("10000000"), Decimal("0.175")),
    (Decimal("30000000"), Decimal("0.20")),
    (None,                Decimal("0.225")),  # None = unbounded
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
    is_self_transfer: bool = False


@dataclass
class MonthKey:
    year: int
    month: int

    def __hash__(self):
        return hash((self.year, self.month))

    def __eq__(self, other):
        return self.year == other.year and self.month == other.month


# ---------------------------------------------------------------------------
# Tax calculation helpers
# ---------------------------------------------------------------------------

def compute_progressive_tax(gain_brl: Decimal) -> Decimal:
    """
    Apply progressive brackets tier-by-tier.
    Each rate applies only to the portion within that bracket.
    Returns total tax amount (not rate).
    """
    tax = Decimal(0)
    prev_limit = Decimal(0)
    for upper_limit, rate in TAX_BRACKETS:
        if upper_limit is None:
            tax += (gain_brl - prev_limit) * rate
            break
        taxable_in_bracket = min(gain_brl, upper_limit) - prev_limit
        if taxable_in_bracket <= 0:
            break
        tax += taxable_in_bracket * rate
        if gain_brl <= upper_limit:
            break
        prev_limit = upper_limit
    return tax.quantize(Decimal("0.01"))


def effective_rate(tax_due: Decimal, taxable_gain: Decimal) -> Decimal:
    if taxable_gain == 0:
        return Decimal(0)
    return (tax_due / taxable_gain).quantize(Decimal("0.0001"))


def _easter(year: int) -> date:
    """Anonymous Gregorian algorithm for Easter Sunday."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def _br_holidays(year: int) -> frozenset[date]:
    """
    Brazilian national holidays (feriados nacionais) for a given year.

    Fixed holidays: Lei 10.607/2002 + Lei 14.759/2023 (Consciência Negra).
    Variable holidays: Good Friday (Easter − 2) and Corpus Christi (Easter + 60).

    Note: Carnival (Tuesday) is a *facultative* banking holiday observed by the
    Banco Central/financial system. It is included here because the Receita Federal
    follows the BCB payment calendar for DARF due dates.
    """
    easter = _easter(year)
    return frozenset({
        date(year, 1, 1),                       # Confraternização Universal
        date(year, 4, 21),                      # Tiradentes
        date(year, 5, 1),                       # Dia do Trabalhador
        date(year, 9, 7),                       # Independência do Brasil
        date(year, 10, 12),                     # Nossa Senhora Aparecida
        date(year, 11, 2),                      # Finados
        date(year, 11, 15),                     # Proclamação da República
        date(year, 11, 20),                     # Consciência Negra (Lei 14.759/2023)
        date(year, 12, 25),                     # Natal
        easter - timedelta(days=48),            # Segunda de Carnaval (facultativo BCB)
        easter - timedelta(days=47),            # Terça de Carnaval (facultativo BCB)
        easter - timedelta(days=2),             # Sexta-feira Santa
        easter + timedelta(days=60),            # Corpus Christi
    })


def last_business_day(year: int, month: int) -> date:
    """
    Return last business day (Mon–Fri, not a Brazilian national holiday)
    of the given year/month.
    """
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    last = next_month - timedelta(days=1)
    holidays = _br_holidays(last.year)
    while last.weekday() >= 5 or last in holidays:
        last -= timedelta(days=1)
        # Refresh holiday set if we crossed a year boundary
        if last.year not in (year, last.year):
            holidays = holidays | _br_holidays(last.year)
    return last


def darf_due_date(year: int, month: int) -> str:
    """DARF for month M is due on last business day of month M+1."""
    if month == 12:
        return last_business_day(year + 1, 1).isoformat()
    return last_business_day(year, month + 1).isoformat()


# ---------------------------------------------------------------------------
# Core gains computation
# ---------------------------------------------------------------------------

def _empty_asset_data() -> dict:
    return {
        "gain": Decimal(0), "loss": Decimal(0),
        "proceeds": Decimal(0), "avg_cost_at_sale": Decimal(0),
        "buy_amount": Decimal(0), "sell_amount": Decimal(0),
        # Total BRL cost of everything sold this month; avg_cost_at_sale is
        # derived from it (cost_of_sold / sell_amount) so multiple sells at
        # different pool averages produce a quantity-weighted figure.
        "cost_of_sold": Decimal(0),
    }


def _compute_gains_split(
    transactions: list[TxRecord],
) -> tuple[dict[MonthKey, dict[str, dict]], dict[MonthKey, dict[str, dict]]]:
    """
    Compute monthly gains using a **single unified cost basis pool** for all assets,
    but attribute each realized gain/loss to the exchange type where the sell occurred.

    This is the correct Brazilian treatment: cost basis is per-asset regardless of
    which exchange holds it; tax regime (BR code 4600 vs foreign code 0507) depends
    on where the disposal happens.

    Returns: (br_monthly_gains, foreign_monthly_gains)
    """
    cost_basis: dict[str, dict] = defaultdict(
        lambda: {"total_cost": Decimal(0), "quantity": Decimal(0)}
    )
    br_monthly: dict[MonthKey, dict] = defaultdict(
        lambda: defaultdict(_empty_asset_data)
    )
    foreign_monthly: dict[MonthKey, dict] = defaultdict(
        lambda: defaultdict(_empty_asset_data)
    )

    for tx in sorted(transactions, key=lambda t: t.executed_at):
        # Self-transfers are pure custody moves — skip entirely.
        # Both the outgoing and incoming legs must be marked to keep the
        # cost basis correct; skipping only one side would corrupt the pool.
        if tx.is_self_transfer:
            continue

        mk = MonthKey(tx.executed_at.year, tx.executed_at.month)
        brl = tx.total_brl or Decimal(0)
        monthly = br_monthly if tx.is_brazilian_exchange else foreign_monthly

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

            d = monthly[mk][tx.asset]
            d["sell_amount"] += tx.amount
            d["proceeds"] += brl
            d["cost_of_sold"] += cost_of_sold
            d["avg_cost_at_sale"] = (
                d["cost_of_sold"] / d["sell_amount"] if d["sell_amount"] > 0 else Decimal(0)
            )

            if gain > 0:
                monthly[mk][tx.asset]["gain"] += gain
            else:
                monthly[mk][tx.asset]["loss"] += abs(gain)

            cb["total_cost"] = max(Decimal(0), cb["total_cost"] - cost_of_sold)
            cb["quantity"] = max(Decimal(0), cb["quantity"] - tx.amount)

        elif tx.transaction_type == "fee":
            # On-chain gas fees: the fee token (ETH, BNB) is consumed at 0 proceeds.
            # Gain = 0 − avg_cost × amount = a loss equal to the BRL cost of the gas.
            # This correctly deducts gas from the user's overall gains for the month.
            cb = cost_basis[tx.asset]
            avg = cb["total_cost"] / cb["quantity"] if cb["quantity"] > 0 else Decimal(0)
            cost_of_gas = avg * tx.amount

            monthly[mk][tx.asset]["loss"] += cost_of_gas

            cb["total_cost"] = max(Decimal(0), cb["total_cost"] - cost_of_gas)
            cb["quantity"] = max(Decimal(0), cb["quantity"] - tx.amount)

    return (
        {k: dict(v) for k, v in br_monthly.items()},
        {k: dict(v) for k, v in foreign_monthly.items()},
    )


def compute_gains(transactions: list[TxRecord]) -> dict[MonthKey, dict[str, dict]]:
    """
    Unified monthly gains (BR + foreign merged) for the gains report.
    Uses the same unified cost basis as _compute_gains_split.
    """
    br_monthly, foreign_monthly = _compute_gains_split(transactions)
    all_keys = set(br_monthly) | set(foreign_monthly)
    merged: dict[MonthKey, dict[str, dict]] = {}
    for mk in all_keys:
        combined: dict[str, dict] = {}
        # Iterate both regime dicts as (asset, data) pairs. A dict union here
        # would drop the BR entry whenever the same asset was sold on both a
        # BR and a foreign exchange in the same month.
        month_items = list(br_monthly.get(mk, {}).items()) + list(foreign_monthly.get(mk, {}).items())
        for asset, data in month_items:
            if asset not in combined:
                combined[asset] = _empty_asset_data()
            d = combined[asset]
            d["gain"] += data["gain"]
            d["loss"] += data["loss"]
            d["proceeds"] += data["proceeds"]
            d["buy_amount"] += data["buy_amount"]
            d["sell_amount"] += data["sell_amount"]
            d["cost_of_sold"] += data["cost_of_sold"]
            # Quantity-weighted across both regimes (BR + foreign sells of the
            # same asset in the same month), not "last non-zero wins".
            d["avg_cost_at_sale"] = (
                d["cost_of_sold"] / d["sell_amount"] if d["sell_amount"] > 0 else Decimal(0)
            )
        merged[mk] = combined
    return merged


def get_cost_basis_snapshot(transactions: list[TxRecord]) -> dict[str, dict]:
    """Return current cost basis for all assets (for IRPF bens e direitos)."""
    cost_basis: dict[str, dict] = defaultdict(
        lambda: {"total_cost": Decimal(0), "quantity": Decimal(0)}
    )
    for tx in sorted(transactions, key=lambda t: t.executed_at):
        if tx.is_self_transfer:
            continue
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
        elif tx.transaction_type == "fee":
            cb = cost_basis[tx.asset]
            if cb["quantity"] > 0:
                avg = cb["total_cost"] / cb["quantity"]
                cb["total_cost"] = max(Decimal(0), cb["total_cost"] - avg * tx.amount)
                cb["quantity"] = max(Decimal(0), cb["quantity"] - tx.amount)
    return {k: v for k, v in cost_basis.items() if v["quantity"] > 0}


# ---------------------------------------------------------------------------
# DARF obligations
# ---------------------------------------------------------------------------

def darf_obligations(transactions: list[TxRecord], year: int) -> list[dict]:
    """
    Calculate DARF obligations for each month of the given year.

    BR gains (code 4600): R$35k/month exemption; net monthly losses carry forward.
    Foreign gains (code 0507): always taxable; net monthly losses carry forward.
    Carryforwards are independent between regimes.
    Tax is calculated progressively tier-by-tier.
    """
    br_monthly, foreign_monthly = _compute_gains_split(transactions)
    obligations = []
    br_loss_carry = Decimal(0)
    foreign_loss_carry = Decimal(0)

    for month in range(1, 13):
        mk = MonthKey(year, month)

        # --- Brazilian exchange (DARF code 4600) ---
        br_data = br_monthly.get(mk, {})
        br_gross_gain = sum(d["gain"] for d in br_data.values())
        br_gross_loss = sum(d["loss"] for d in br_data.values())
        br_net = br_gross_gain - br_gross_loss

        br_carry_applied = Decimal(0)
        if br_net > 0 and br_loss_carry > 0:
            br_carry_applied = min(br_net, br_loss_carry)
            br_net -= br_carry_applied
            br_loss_carry -= br_carry_applied
        elif br_net < 0:
            br_loss_carry += abs(br_net)
            br_net = Decimal(0)

        br_taxable = max(Decimal(0), br_net - DARF_EXEMPT_BRL)
        if br_taxable > 0:
            tax_due = compute_progressive_tax(br_taxable)
            obligations.append({
                "year": year,
                "month": month,
                "darf_code": "4600",
                "is_foreign": False,
                "net_gain_brl": br_net,
                "carryforward_applied_brl": br_carry_applied,
                "exempt_threshold_brl": DARF_EXEMPT_BRL,
                "taxable_gain_brl": br_taxable,
                "tax_due_brl": tax_due,
                "effective_rate": effective_rate(tax_due, br_taxable),
                "due_date": darf_due_date(year, month),
            })

        # --- Foreign exchange (DARF code 0507) ---
        fgn_data = foreign_monthly.get(mk, {})
        fgn_gross_gain = sum(d["gain"] for d in fgn_data.values())
        fgn_gross_loss = sum(d["loss"] for d in fgn_data.values())
        fgn_net = fgn_gross_gain - fgn_gross_loss

        fgn_carry_applied = Decimal(0)
        if fgn_net > 0 and foreign_loss_carry > 0:
            fgn_carry_applied = min(fgn_net, foreign_loss_carry)
            fgn_net -= fgn_carry_applied
            foreign_loss_carry -= fgn_carry_applied
        elif fgn_net < 0:
            foreign_loss_carry += abs(fgn_net)
            fgn_net = Decimal(0)

        if fgn_net > 0:
            tax_due = compute_progressive_tax(fgn_net)
            obligations.append({
                "year": year,
                "month": month,
                "darf_code": "0507",
                "is_foreign": True,
                "net_gain_brl": fgn_net,
                "carryforward_applied_brl": fgn_carry_applied,
                "exempt_threshold_brl": Decimal(0),
                "taxable_gain_brl": fgn_net,
                "tax_due_brl": tax_due,
                "effective_rate": effective_rate(tax_due, fgn_net),
                "due_date": darf_due_date(year, month),
            })

    return obligations


# ---------------------------------------------------------------------------
# Earn income (staking rewards, airdrops)
# ---------------------------------------------------------------------------

def earn_income_by_year(transactions: list[TxRecord], year: int) -> list[dict]:
    """
    Aggregate 'earn' transactions (staking, airdrops, yield) by asset for a given year.

    Under Brazilian law, the RFB has not issued definitive guidance on whether
    staking/airdrops are taxed as income at receipt (progressive rates up to 27.5%)
    or only as capital gains on eventual disposal (15%). The conservative and
    widely-adopted accountant position is to declare them as income at receipt.
    This function surfaces them so the user can decide with their accountant.
    """
    totals: dict[str, dict] = defaultdict(lambda: {"total_brl": Decimal(0), "count": 0})
    for tx in transactions:
        if tx.transaction_type != "earn":
            continue
        if tx.executed_at.year != year:
            continue
        totals[tx.asset]["total_brl"] += tx.total_brl or Decimal(0)
        totals[tx.asset]["count"] += 1
    return [
        {"asset": asset, "total_brl": data["total_brl"], "transaction_count": data["count"]}
        for asset, data in sorted(totals.items())
        if data["total_brl"] > 0
    ]


# ---------------------------------------------------------------------------
# Data quality — missing BRL prices
# ---------------------------------------------------------------------------

# Types whose BRL value feeds cost basis or proceeds. A missing price on any of
# these silently zeroes cost/proceeds and inflates (or hides) the taxable gain.
# 'fee' is excluded: gas is valued from the pool's average cost, not total_brl.
PRICED_TYPES = {
    "buy", "sell", "swap_in", "swap_out", "transfer_in", "transfer_out", "earn",
}


def unpriced_transactions(transactions: list[TxRecord]) -> list[dict]:
    """
    Return transactions that affect tax math but have no BRL price.

    These must be surfaced before trusting any DARF/IRPF number: a missing
    price is treated as R$0, which inflates gains (0 cost on a sale) or hides
    them (0 proceeds). Self-transfers are skipped — they carry no tax value.
    """
    out: list[dict] = []
    for tx in transactions:
        if tx.is_self_transfer:
            continue
        if tx.transaction_type not in PRICED_TYPES:
            continue
        if tx.total_brl is None or tx.total_brl <= 0:
            out.append({
                "id": tx.id,
                "wallet_name": tx.wallet_name,
                "executed_at": tx.executed_at.isoformat(),
                "transaction_type": tx.transaction_type,
                "asset": tx.asset,
                "amount": tx.amount,
            })
    return sorted(out, key=lambda x: (x["executed_at"], x["id"]))


# ---------------------------------------------------------------------------
# IN RFB 1888
# ---------------------------------------------------------------------------

TRADE_TYPES = {"buy", "sell", "swap_in", "swap_out"}


def in1888_report(transactions: list[TxRecord], year: int) -> list[dict]:
    """
    Flag months where trade volume on foreign exchanges exceeds R$30k.
    Only counts actual trades (buy/sell/swap), not custody transfers.
    """
    month_volume: dict[tuple, Decimal] = defaultdict(Decimal)
    month_count: dict[tuple, int] = defaultdict(int)
    wallet_info: dict[int, dict] = {}

    for tx in transactions:
        if tx.is_brazilian_exchange:
            continue
        if tx.transaction_type not in TRADE_TYPES:
            continue
        mk = (tx.executed_at.year, tx.executed_at.month, tx.wallet_id)
        month_volume[mk] += tx.total_brl or Decimal(0)
        month_count[mk] += 1
        wallet_info[tx.wallet_id] = {"name": tx.wallet_name}

    entries = []
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


# ---------------------------------------------------------------------------
# COAF
# ---------------------------------------------------------------------------

def coaf_alerts(transactions: list[TxRecord]) -> list[dict]:
    """
    Return all COAF-relevant alerts:
    1. Single transactions above R$10k.
    2. Potential structuring: multiple sub-threshold transactions from the same
       wallet on the same day whose combined value exceeds R$10k.
       (Resolução COAF nº 36/2021 — fracionamento suspeito)
    """
    alerts: list[dict] = []

    # --- Single-transaction threshold ---
    for tx in transactions:
        brl = tx.total_brl or Decimal(0)
        if brl > COAF_THRESHOLD_BRL:
            alerts.append({
                "alert_type": "single_transaction",
                "transaction_ids": [tx.id],
                "executed_at": tx.executed_at.isoformat(),
                "asset": tx.asset,
                "amount": tx.amount,
                "total_brl": brl,
                "wallet_name": tx.wallet_name,
                "reason": f"Transação única acima de R${COAF_THRESHOLD_BRL:,.0f}",
            })

    # --- Structuring: sub-threshold transactions that collectively exceed R$10k ---
    # Group by (wallet_id, date); only consider transactions individually below the threshold.
    groups: dict[tuple, list[TxRecord]] = defaultdict(list)
    for tx in transactions:
        brl = tx.total_brl or Decimal(0)
        if Decimal(0) < brl < COAF_THRESHOLD_BRL:
            groups[(tx.wallet_id, tx.executed_at)].append(tx)

    for (wallet_id, day), group in groups.items():
        if len(group) < 2:
            continue
        total = sum(t.total_brl or Decimal(0) for t in group)
        if total > COAF_THRESHOLD_BRL:
            assets = sorted({t.asset for t in group})
            alerts.append({
                "alert_type": "structuring",
                "transaction_ids": [t.id for t in group],
                "executed_at": day.isoformat(),
                "asset": ", ".join(assets) if len(assets) == 1 else None,
                "amount": None,
                "total_brl": total,
                "wallet_name": group[0].wallet_name,
                "reason": (
                    f"{len(group)} transações abaixo de R${COAF_THRESHOLD_BRL:,.0f} "
                    f"no mesmo dia somam {total:,.2f} — possível fracionamento (Res. COAF 36/2021)"
                ),
            })

    return sorted(alerts, key=lambda a: a["executed_at"])
