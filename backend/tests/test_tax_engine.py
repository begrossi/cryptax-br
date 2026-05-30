"""
Unit tests for the tax engine — no DB required.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.services.tax_engine import (
    TxRecord,
    MonthKey,
    compute_gains,
    get_cost_basis_snapshot,
    darf_obligations,
    earn_income_by_year,
    in1888_report,
    coaf_alerts,
    darf_due_date,
    last_business_day,
    _easter,
    _br_holidays,
    compute_progressive_tax,
    DARF_EXEMPT_BRL,
    TRADE_TYPES,
)


def tx(
    id: int,
    day: date,
    tx_type: str,
    asset: str,
    amount: str,
    total_brl: str,
    is_br: bool = True,
    wallet_name: str = "Test",
    wallet_id: int = 1,
) -> TxRecord:
    return TxRecord(
        id=id, wallet_id=wallet_id, wallet_name=wallet_name,
        is_brazilian_exchange=is_br,
        executed_at=day,
        transaction_type=tx_type,
        asset=asset,
        amount=Decimal(amount),
        total_brl=Decimal(total_brl),
    )


# ---------------------------------------------------------------------------
# Issue 4: Progressive tax brackets (was previously a flat rate)
# ---------------------------------------------------------------------------

def test_progressive_tax_under_5m():
    # Entire gain in first bracket → all at 15%
    assert compute_progressive_tax(Decimal("100000")) == Decimal("15000.00")


def test_progressive_tax_exactly_5m():
    assert compute_progressive_tax(Decimal("5000000")) == Decimal("750000.00")


def test_progressive_tax_spans_two_brackets():
    # R$6M: first 5M at 15% = 750k, next 1M at 17.5% = 175k → total 925k
    result = compute_progressive_tax(Decimal("6000000"))
    assert result == Decimal("925000.00")


def test_progressive_tax_spans_three_brackets():
    # R$15M: 5M@15% + 5M@17.5% + 5M@20% = 750k + 875k + 1M = 2.625M
    result = compute_progressive_tax(Decimal("15000000"))
    assert result == Decimal("2625000.00")


def test_progressive_tax_top_bracket():
    # R$35M: 5M@15% + 5M@17.5% + 20M@20% + 5M@22.5%
    # = 750k + 875k + 4M + 1.125M = 6.75M
    result = compute_progressive_tax(Decimal("35000000"))
    assert result == Decimal("6750000.00")


# ---------------------------------------------------------------------------
# Issue 3: Loss carryforward
# ---------------------------------------------------------------------------

def test_br_loss_carries_forward_to_next_month():
    txs = [
        # January: buy 1 BTC @ 100k, sell @ 80k → loss of 20k
        tx(1, date(2024, 1, 5),  "buy",  "BTC", "1", "100000"),
        tx(2, date(2024, 1, 20), "sell", "BTC", "1", "80000"),
        # February: buy 1 BTC @ 80k, sell @ 160k → gain of 80k
        tx(3, date(2024, 2, 5),  "buy",  "BTC", "1", "80000"),
        tx(4, date(2024, 2, 20), "sell", "BTC", "1", "160000"),
    ]
    # Feb net gain after carryforward = 80k - 20k = 60k; taxable = 60k - 35k = 25k
    obligations = darf_obligations(txs, 2024)
    assert len(obligations) == 1
    assert obligations[0]["month"] == 2
    assert obligations[0]["carryforward_applied_brl"] == Decimal("20000")
    assert obligations[0]["taxable_gain_brl"] == Decimal("25000")


def test_br_loss_fully_absorbs_future_gain():
    txs = [
        tx(1, date(2024, 3, 1), "buy",  "BTC", "1", "200000"),
        tx(2, date(2024, 3, 15), "sell", "BTC", "1", "100000"),  # loss 100k
        tx(3, date(2024, 4, 1), "buy",  "BTC", "1", "100000"),
        tx(4, date(2024, 4, 20), "sell", "BTC", "1", "170000"),  # gain 70k
    ]
    # April net 70k, minus 100k carryforward → 0 taxable
    obligations = darf_obligations(txs, 2024)
    assert obligations == []


def test_foreign_loss_carries_forward_independently():
    txs = [
        # BR exchange: gain 50k in Jan → DARF due
        tx(1, date(2024, 1, 5),  "buy",  "ETH", "1", "10000", is_br=True),
        tx(2, date(2024, 1, 25), "sell", "ETH", "1", "60000", is_br=True),
        # Foreign exchange: loss 20k in Jan
        tx(3, date(2024, 1, 10), "buy",  "BTC", "1", "100000", is_br=False, wallet_id=2),
        tx(4, date(2024, 1, 20), "sell", "BTC", "1",  "80000", is_br=False, wallet_id=2),
        # Foreign exchange: gain 40k in Feb → carryforward 20k → taxable 20k
        tx(5, date(2024, 2, 10), "buy",  "BTC", "1", "80000", is_br=False, wallet_id=2),
        tx(6, date(2024, 2, 25), "sell", "BTC", "1", "120000", is_br=False, wallet_id=2),
    ]
    obligations = darf_obligations(txs, 2024)

    br_jan = next((o for o in obligations if o["month"] == 1 and not o["is_foreign"]), None)
    fgn_feb = next((o for o in obligations if o["month"] == 2 and o["is_foreign"]), None)

    assert br_jan is not None
    assert fgn_feb is not None
    assert fgn_feb["carryforward_applied_brl"] == Decimal("20000")
    assert fgn_feb["taxable_gain_brl"] == Decimal("20000")


def test_br_and_foreign_carryforwards_are_independent():
    txs = [
        # Foreign loss in Jan
        tx(1, date(2024, 1, 1), "buy",  "BTC", "1", "100000", is_br=False, wallet_id=2),
        tx(2, date(2024, 1, 31), "sell", "BTC", "1",  "50000", is_br=False, wallet_id=2),
        # BR gain in Feb — should NOT benefit from foreign loss carryforward
        tx(3, date(2024, 2, 1), "buy",  "ETH", "1", "10000", is_br=True),
        tx(4, date(2024, 2, 28), "sell", "ETH", "1", "80000", is_br=True),
    ]
    obligations = darf_obligations(txs, 2024)
    br_feb = next((o for o in obligations if o["month"] == 2 and not o["is_foreign"]), None)
    assert br_feb is not None
    assert br_feb["carryforward_applied_brl"] == Decimal("0")
    # taxable = 70k - 35k = 35k
    assert br_feb["taxable_gain_brl"] == Decimal("35000")


# ---------------------------------------------------------------------------
# Issue 2: Mixed BR + foreign months → two separate obligations
# ---------------------------------------------------------------------------

def test_mixed_month_produces_two_obligations():
    txs = [
        # BR exchange: gain 50k in Jan
        tx(1, date(2024, 1, 5),  "buy",  "ETH", "1", "10000", is_br=True),
        tx(2, date(2024, 1, 25), "sell", "ETH", "1", "60000", is_br=True),
        # Foreign exchange: gain 30k in Jan
        tx(3, date(2024, 1, 10), "buy",  "BTC", "0.5", "50000", is_br=False, wallet_id=2),
        tx(4, date(2024, 1, 20), "sell", "BTC", "0.5", "80000", is_br=False, wallet_id=2),
    ]
    obligations = darf_obligations(txs, 2024)

    jan_br  = next((o for o in obligations if o["month"] == 1 and not o["is_foreign"]), None)
    jan_fgn = next((o for o in obligations if o["month"] == 1 and o["is_foreign"]), None)

    assert jan_br  is not None, "Expected a BR DARF obligation for January"
    assert jan_fgn is not None, "Expected a foreign DARF obligation for January"


def test_mixed_month_br_keeps_35k_exemption():
    txs = [
        tx(1, date(2024, 1, 5),  "buy",  "ETH", "1", "10000", is_br=True),
        tx(2, date(2024, 1, 25), "sell", "ETH", "1", "60000", is_br=True),   # gain 50k
        tx(3, date(2024, 1, 10), "buy",  "BTC", "1", "100000", is_br=False, wallet_id=2),
        tx(4, date(2024, 1, 20), "sell", "BTC", "1", "110000", is_br=False, wallet_id=2),  # gain 10k
    ]
    obligations = darf_obligations(txs, 2024)
    jan_br = next(o for o in obligations if not o["is_foreign"])

    # BR gain 50k − 35k exemption = 15k taxable (exemption is NOT stripped by foreign activity)
    assert jan_br["exempt_threshold_brl"] == Decimal("35000")
    assert jan_br["taxable_gain_brl"] == Decimal("15000")


# ---------------------------------------------------------------------------
# Issue 1: DARF codes
# ---------------------------------------------------------------------------

def test_br_obligation_uses_code_4600():
    txs = [
        tx(1, date(2024, 6, 1),  "buy",  "BTC", "1", "100000"),
        tx(2, date(2024, 6, 25), "sell", "BTC", "1", "150000"),
    ]
    obligations = darf_obligations(txs, 2024)
    assert len(obligations) == 1
    assert obligations[0]["darf_code"] == "4600"


def test_foreign_obligation_uses_code_0507():
    txs = [
        tx(1, date(2024, 7, 1),  "buy",  "ETH", "1", "10000", is_br=False),
        tx(2, date(2024, 7, 15), "sell", "ETH", "1", "20000", is_br=False),
    ]
    obligations = darf_obligations(txs, 2024)
    assert len(obligations) == 1
    assert obligations[0]["darf_code"] == "0507"


# ---------------------------------------------------------------------------
# Unified cost basis across wallets (buy on BR, sell on foreign)
# ---------------------------------------------------------------------------

def test_sell_on_foreign_uses_unified_cost_basis():
    txs = [
        # Buy 1 BTC @ 100k on Brazilian exchange
        tx(1, date(2024, 1, 5),  "buy",  "BTC", "1", "100000", is_br=True),
        # Sell 1 BTC @ 150k on foreign exchange — cost basis should be 100k
        tx(2, date(2024, 1, 20), "sell", "BTC", "1", "150000", is_br=False, wallet_id=2),
    ]
    obligations = darf_obligations(txs, 2024)
    fgn = next(o for o in obligations if o["is_foreign"])
    # Foreign gain = 150k - 100k = 50k, all taxable (no exemption)
    assert fgn["taxable_gain_brl"] == Decimal("50000")
    assert fgn["darf_code"] == "0507"


# ---------------------------------------------------------------------------
# Pre-existing tests (custo médio, DARF exemption, IN 1888, COAF, snapshot)
# ---------------------------------------------------------------------------

def test_simple_buy_sell_gain():
    txs = [
        tx(1, date(2024, 1, 10), "buy",  "BTC", "1", "100000"),
        tx(2, date(2024, 1, 20), "sell", "BTC", "1", "150000"),
    ]
    monthly = compute_gains(txs)
    mk = MonthKey(2024, 1)
    assert mk in monthly
    assert monthly[mk]["BTC"]["gain"] == Decimal("50000")
    assert monthly[mk]["BTC"]["loss"] == Decimal("0")


def test_avg_cost_two_buys():
    txs = [
        tx(1, date(2024, 1, 5),  "buy",  "ETH", "1", "10000"),
        tx(2, date(2024, 1, 10), "buy",  "ETH", "1", "20000"),   # avg = 15k
        tx(3, date(2024, 1, 25), "sell", "ETH", "1", "18000"),   # gain = 3k
    ]
    monthly = compute_gains(txs)
    mk = MonthKey(2024, 1)
    assert monthly[mk]["ETH"]["gain"] == Decimal("3000")


def test_sell_below_cost_is_loss():
    txs = [
        tx(1, date(2024, 3, 1),  "buy",  "BTC", "1", "200000"),
        tx(2, date(2024, 3, 15), "sell", "BTC", "1", "180000"),
    ]
    monthly = compute_gains(txs)
    mk = MonthKey(2024, 3)
    assert monthly[mk]["BTC"]["loss"] == Decimal("20000")
    assert monthly[mk]["BTC"]["gain"] == Decimal("0")


def test_darf_below_35k_exempt():
    txs = [
        tx(1, date(2024, 5, 1),  "buy",  "BTC", "0.5", "50000"),
        tx(2, date(2024, 5, 20), "sell", "BTC", "0.5", "80000"),
    ]
    obligations = darf_obligations(txs, 2024)
    assert obligations == []


def test_darf_above_35k():
    txs = [
        tx(1, date(2024, 6, 1),  "buy",  "BTC", "1", "100000"),
        tx(2, date(2024, 6, 25), "sell", "BTC", "1", "150000"),
    ]
    # Gain 50k; taxable = 50k - 35k = 15k; tax = 15k * 15% = 2250
    obligations = darf_obligations(txs, 2024)
    assert len(obligations) == 1
    assert obligations[0]["taxable_gain_brl"] == Decimal("15000")
    assert obligations[0]["tax_due_brl"] == Decimal("2250.00")


def test_darf_foreign_always_taxable():
    txs = [
        tx(1, date(2024, 7, 1),  "buy",  "ETH", "1", "10000", is_br=False),
        tx(2, date(2024, 7, 15), "sell", "ETH", "1", "20000", is_br=False),
    ]
    obligations = darf_obligations(txs, 2024)
    assert len(obligations) == 1
    assert obligations[0]["is_foreign"] is True
    assert obligations[0]["taxable_gain_brl"] == Decimal("10000")
    assert obligations[0]["exempt_threshold_brl"] == Decimal("0")


def test_darf_due_date_jan_due_feb():
    assert darf_due_date(2024, 1) == "2024-02-29"  # Feb 2024 has 29 days (leap year)


def test_darf_due_date_dec_due_jan():
    result = darf_due_date(2024, 12)
    assert result.startswith("2025-01")


def test_in1888_above_threshold():
    txs = [
        tx(1, date(2024, 8, 1),  "buy",  "BTC", "1", "200000", is_br=False, wallet_name="Coinbase"),
        tx(2, date(2024, 8, 15), "sell", "BTC", "1", "250000", is_br=False, wallet_name="Coinbase"),
    ]
    report = in1888_report(txs, 2024)
    assert len(report) == 1
    assert report[0]["must_report"] is True


def test_in1888_br_exchange_ignored():
    txs = [
        tx(1, date(2024, 9, 1),  "buy",  "BTC", "1", "200000", is_br=True),
        tx(2, date(2024, 9, 15), "sell", "BTC", "1", "250000", is_br=True),
    ]
    assert in1888_report(txs, 2024) == []


def test_in1888_transfers_not_counted():
    txs = [
        # Only transfers — should not count toward IN 1888 volume
        tx(1, date(2024, 10, 1),  "transfer_in",  "BTC", "2", "400000", is_br=False, wallet_name="Coinbase"),
        tx(2, date(2024, 10, 15), "transfer_out", "BTC", "2", "400000", is_br=False, wallet_name="Coinbase"),
    ]
    report = in1888_report(txs, 2024)
    assert report == []


def test_in1888_only_trades_count():
    txs = [
        tx(1, date(2024, 11, 1), "buy",  "BTC", "0.1", "10000", is_br=False, wallet_name="Coinbase"),
        tx(2, date(2024, 11, 5), "sell", "BTC", "0.1", "11000", is_br=False, wallet_name="Coinbase"),
        # Large transfer that would push volume above threshold if wrongly counted
        tx(3, date(2024, 11, 10), "transfer_in", "BTC", "5", "1000000", is_br=False, wallet_name="Coinbase"),
    ]
    report = in1888_report(txs, 2024)
    assert len(report) == 1
    # Volume = 10k + 11k = 21k, below 30k threshold
    assert report[0]["must_report"] is False


def test_coaf_flags_large_tx():
    txs = [tx(1, date(2024, 4, 10), "buy", "BTC", "0.1", "15000")]
    alerts = coaf_alerts(txs)
    assert len(alerts) == 1
    assert alerts[0]["total_brl"] == Decimal("15000")


def test_coaf_ignores_small_tx():
    txs = [tx(1, date(2024, 4, 10), "buy", "BTC", "0.01", "5000")]
    assert coaf_alerts(txs) == []


# ---------------------------------------------------------------------------
# Issue 5: Gas fees reduce cost basis (treated as disposal at 0 proceeds)
# ---------------------------------------------------------------------------

def test_fee_generates_loss_equal_to_gas_cost():
    txs = [
        tx(1, date(2024, 1, 1), "buy", "ETH", "1", "10000"),     # 1 ETH @ 10k cost
        tx(2, date(2024, 1, 5), "fee", "ETH", "0.01", "100"),    # 0.01 ETH gas = 100 BRL cost
    ]
    monthly = compute_gains(txs)
    mk = MonthKey(2024, 1)
    # Loss = avg_cost(10k) * 0.01 = 100 BRL (gas correctly deducted)
    assert monthly[mk]["ETH"]["loss"] == Decimal("100")


def test_fee_reduces_cost_basis_snapshot():
    txs = [
        tx(1, date(2024, 1, 1), "buy", "ETH", "2", "20000"),    # 2 ETH @ 10k avg
        tx(2, date(2024, 1, 5), "fee", "ETH", "0.1", "0"),      # 0.1 ETH burned as gas
    ]
    snapshot = get_cost_basis_snapshot(txs)
    # Remaining: 1.9 ETH, cost = 20k - (10k * 0.1) = 19k
    assert snapshot["ETH"]["quantity"] == Decimal("1.9")
    assert snapshot["ETH"]["total_cost"] == Decimal("19000")


def test_fee_reduces_darf_taxable_gain():
    txs = [
        tx(1, date(2024, 1, 1), "buy",  "ETH", "1", "10000"),   # buy 1 ETH @ 10k
        tx(2, date(2024, 1, 5), "fee",  "ETH", "0.1", "0"),     # gas: 0.1 ETH @ 10k avg = 1k loss
        tx(3, date(2024, 1, 20), "sell", "ETH", "0.9", "18000"), # sell 0.9 ETH
    ]
    # After fee: 0.9 ETH remains, avg cost = 10k; sell proceeds = 18k; gain = 18k - 9k = 9k
    # Plus fee loss = 1k → net = 9k - 1k = 8k → below 35k exemption → no DARF
    # Actually: fee creates 1k loss in Jan. Sell creates 9k gain. Net = 8k. Below 35k → no DARF.
    obligations = darf_obligations(txs, 2024)
    assert obligations == []


# ---------------------------------------------------------------------------
# Issue 6: Self-transfers are skipped in tax calculations
# ---------------------------------------------------------------------------

def self_tx(
    id: int,
    day: date,
    tx_type: str,
    asset: str,
    amount: str,
    total_brl: str,
    wallet_id: int = 1,
) -> TxRecord:
    return TxRecord(
        id=id, wallet_id=wallet_id, wallet_name="Test",
        is_brazilian_exchange=True,
        executed_at=day,
        transaction_type=tx_type,
        asset=asset,
        amount=Decimal(amount),
        total_brl=Decimal(total_brl),
        is_self_transfer=True,
    )


def test_self_transfer_does_not_create_gain_or_loss():
    txs = [
        tx(1, date(2024, 2, 1), "buy",          "BTC", "1", "100000"),
        # Self-transfer out from wallet A
        self_tx(2, date(2024, 2, 10), "transfer_out", "BTC", "1", "120000", wallet_id=1),
        # Self-transfer in to wallet B
        self_tx(3, date(2024, 2, 10), "transfer_in",  "BTC", "1", "120000", wallet_id=2),
    ]
    monthly = compute_gains(txs)
    mk = MonthKey(2024, 2)
    # No gain/loss from the self-transfer
    assert monthly[mk]["BTC"]["gain"] == Decimal("0")
    assert monthly[mk]["BTC"]["loss"] == Decimal("0")


def test_self_transfer_preserves_cost_basis():
    txs = [
        tx(1, date(2024, 3, 1), "buy",          "ETH", "2", "20000"),
        self_tx(2, date(2024, 3, 15), "transfer_out", "ETH", "2", "30000", wallet_id=1),
        self_tx(3, date(2024, 3, 15), "transfer_in",  "ETH", "2", "30000", wallet_id=2),
        tx(4, date(2024, 3, 25), "sell",         "ETH", "2", "40000", wallet_id=2),
    ]
    # Sell on wallet B: cost basis should still be 20k (original buy), gain = 40k - 20k = 20k
    monthly = compute_gains(txs)
    mk = MonthKey(2024, 3)
    assert monthly[mk]["ETH"]["gain"] == Decimal("20000")


def test_non_self_transfer_out_still_taxable():
    txs = [
        tx(1, date(2024, 4, 1),  "buy",          "BTC", "1", "100000"),
        tx(2, date(2024, 4, 15), "transfer_out", "BTC", "1", "150000"),  # withdrawal, not self
    ]
    # transfer_out to unknown → disposal → gain = 50k
    monthly = compute_gains(txs)
    mk = MonthKey(2024, 4)
    assert monthly[mk]["BTC"]["gain"] == Decimal("50000")


# ---------------------------------------------------------------------------
# Issue 7: Earn income surfaced separately
# ---------------------------------------------------------------------------

def test_earn_income_aggregated_by_asset():
    txs = [
        tx(1, date(2024, 5, 1),  "earn", "ETH", "0.5", "5000"),
        tx(2, date(2024, 5, 15), "earn", "ETH", "0.3", "3200"),
        tx(3, date(2024, 6, 1),  "earn", "SOL", "10",  "2000"),
    ]
    report = earn_income_by_year(txs, 2024)
    assets = {e["asset"]: e for e in report}
    assert assets["ETH"]["total_brl"] == Decimal("8200")
    assert assets["ETH"]["transaction_count"] == 2
    assert assets["SOL"]["total_brl"] == Decimal("2000")


def test_earn_income_filtered_by_year():
    txs = [
        tx(1, date(2023, 12, 1), "earn", "BTC", "0.01", "1500"),
        tx(2, date(2024, 1, 1),  "earn", "BTC", "0.01", "1600"),
    ]
    report = earn_income_by_year(txs, 2024)
    assert len(report) == 1
    assert report[0]["total_brl"] == Decimal("1600")


def test_earn_adds_to_cost_basis():
    txs = [
        tx(1, date(2024, 1, 1),  "earn", "ETH", "1", "10000"),   # received 1 ETH as staking, BRL value 10k
        tx(2, date(2024, 1, 20), "sell", "ETH", "1", "15000"),   # sold at 15k
    ]
    # Cost basis = 10k (earn value), gain = 15k - 10k = 5k
    monthly = compute_gains(txs)
    mk = MonthKey(2024, 1)
    assert monthly[mk]["ETH"]["gain"] == Decimal("5000")


# ---------------------------------------------------------------------------
# Issue 9: Holiday-aware DARF due dates
# ---------------------------------------------------------------------------

def test_easter_2024():
    # Easter 2024 is March 31
    assert _easter(2024) == date(2024, 3, 31)


def test_easter_2025():
    # Easter 2025 is April 20
    assert _easter(2025) == date(2025, 4, 20)


def test_tiradentes_april_21_is_holiday():
    holidays = _br_holidays(2025)
    assert date(2025, 4, 21) in holidays


def test_good_friday_is_holiday():
    # Easter 2025 = April 20 → Good Friday = April 18
    holidays = _br_holidays(2025)
    assert date(2025, 4, 18) in holidays


def test_last_business_day_skips_holiday():
    # April 2025: last calendar day = 30 (Wednesday) — not a holiday → should be Apr 30
    result = last_business_day(2025, 4)
    assert result == date(2025, 4, 30)


def test_last_business_day_tiradentes_at_month_end():
    # April 2021: April 30 = Friday (not holiday). Last business day = Apr 30.
    # Tiradentes (Apr 21) doesn't affect the last day.
    result = last_business_day(2021, 4)
    assert result.weekday() < 5
    assert result not in _br_holidays(2021)


def test_last_business_day_christmas_at_month_end():
    # December: last calendar day = 31. Dec 31, 2024 = Tuesday (not a holiday).
    # Christmas (Dec 25) is in the middle, doesn't affect month-end.
    result = last_business_day(2024, 12)
    assert result.weekday() < 5
    assert result not in _br_holidays(2024)
    assert result.month == 12


def test_last_business_day_new_year_forces_january_rollback():
    # For a DARF due in January: last business day of January must skip Jan 1 (New Year)
    # Jan 2025: Jan 1 = Wednesday (holiday). Last calendar day = Jan 31 (Friday, not holiday).
    result = last_business_day(2025, 1)
    assert result == date(2025, 1, 31)
    assert result not in _br_holidays(2025)


def test_due_date_month_ending_on_holiday():
    # November 2025: Nov 30 = Sunday, Nov 29 = Saturday, Nov 28 = Friday
    # Nov 15 (República) and Nov 20 (Consciência Negra) are holidays but not near month-end
    result = last_business_day(2025, 11)
    assert result == date(2025, 11, 28)


# ---------------------------------------------------------------------------
# Issue 10: COAF structuring detection
# ---------------------------------------------------------------------------

def test_coaf_single_transaction_alert():
    txs = [tx(1, date(2024, 4, 10), "buy", "BTC", "0.1", "15000")]
    alerts = coaf_alerts(txs)
    single = [a for a in alerts if a["alert_type"] == "single_transaction"]
    assert len(single) == 1
    assert single[0]["transaction_ids"] == [1]
    assert single[0]["asset"] == "BTC"


def test_coaf_structuring_same_day_same_wallet():
    txs = [
        tx(1, date(2024, 5, 1), "buy", "BTC", "0.05", "4000", wallet_id=1),
        tx(2, date(2024, 5, 1), "buy", "ETH", "0.1",  "4000", wallet_id=1),
        tx(3, date(2024, 5, 1), "buy", "SOL", "10",   "4000", wallet_id=1),
    ]
    alerts = coaf_alerts(txs)
    structuring = [a for a in alerts if a["alert_type"] == "structuring"]
    assert len(structuring) == 1
    assert set(structuring[0]["transaction_ids"]) == {1, 2, 3}
    assert structuring[0]["total_brl"] == Decimal("12000")


def test_coaf_no_structuring_when_individual_above_threshold():
    # Individual transactions already trigger single-transaction alerts, not structuring
    txs = [
        tx(1, date(2024, 6, 1), "buy", "BTC", "1", "11000", wallet_id=1),
        tx(2, date(2024, 6, 1), "buy", "ETH", "1", "11000", wallet_id=1),
    ]
    alerts = coaf_alerts(txs)
    structuring = [a for a in alerts if a["alert_type"] == "structuring"]
    assert structuring == []  # both individual → single_transaction alerts, not structuring


def test_coaf_no_structuring_across_different_wallets():
    txs = [
        tx(1, date(2024, 7, 1), "buy", "BTC", "0.05", "6000", wallet_id=1),
        tx(2, date(2024, 7, 1), "buy", "BTC", "0.05", "6000", wallet_id=2),
    ]
    alerts = coaf_alerts(txs)
    structuring = [a for a in alerts if a["alert_type"] == "structuring"]
    assert structuring == []


def test_coaf_no_alert_when_sum_below_threshold():
    txs = [
        tx(1, date(2024, 8, 1), "buy", "BTC", "0.05", "3000", wallet_id=1),
        tx(2, date(2024, 8, 1), "buy", "ETH", "0.1",  "2000", wallet_id=1),
    ]
    alerts = coaf_alerts(txs)
    assert alerts == []


def test_coaf_structuring_single_transaction_not_flagged_as_structuring():
    # Only one transaction on the day → not structuring
    txs = [tx(1, date(2024, 9, 1), "buy", "BTC", "0.05", "9999", wallet_id=1)]
    alerts = coaf_alerts(txs)
    assert alerts == []


# ---------------------------------------------------------------------------
# Pre-existing tests
# ---------------------------------------------------------------------------

def test_cost_basis_snapshot():
    txs = [
        tx(1, date(2024, 1, 1), "buy",  "BTC", "1", "100000"),
        tx(2, date(2024, 2, 1), "buy",  "BTC", "1", "200000"),
        tx(3, date(2024, 3, 1), "sell", "BTC", "1", "180000"),
    ]
    snapshot = get_cost_basis_snapshot(txs)
    assert "BTC" in snapshot
    # Remaining: 1 BTC, avg cost was 150k
    assert snapshot["BTC"]["quantity"] == Decimal("1")
    assert snapshot["BTC"]["total_cost"] == Decimal("150000")
