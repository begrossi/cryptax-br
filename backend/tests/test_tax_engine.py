"""
Unit tests for the tax engine — no DB required.
All scenarios use hand-crafted TxRecord lists.
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
    in1888_report,
    coaf_alerts,
    darf_due_date,
    DARF_EXEMPT_BRL,
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
) -> TxRecord:
    return TxRecord(
        id=id, wallet_id=1, wallet_name=wallet_name,
        is_brazilian_exchange=is_br,
        executed_at=day,
        transaction_type=tx_type,
        asset=asset,
        amount=Decimal(amount),
        total_brl=Decimal(total_brl),
    )


# --- custo médio ponderado ---

def test_simple_buy_sell_gain():
    txs = [
        tx(1, date(2024, 1, 10), "buy",  "BTC", "1", "100000"),  # buy 1 BTC @ 100k
        tx(2, date(2024, 1, 20), "sell", "BTC", "1", "150000"),  # sell 1 BTC @ 150k
    ]
    monthly = compute_gains(txs)
    mk = MonthKey(2024, 1)
    assert mk in monthly
    assert monthly[mk]["BTC"]["gain"] == Decimal("50000")
    assert monthly[mk]["BTC"]["loss"] == Decimal("0")


def test_avg_cost_two_buys():
    txs = [
        tx(1, date(2024, 1, 5),  "buy",  "ETH", "1", "10000"),   # buy 1 ETH @ 10k
        tx(2, date(2024, 1, 10), "buy",  "ETH", "1", "20000"),   # buy 1 ETH @ 20k → avg = 15k
        tx(3, date(2024, 1, 25), "sell", "ETH", "1", "18000"),   # sell 1 ETH @ 18k
    ]
    monthly = compute_gains(txs)
    mk = MonthKey(2024, 1)
    # avg cost at sale = 15k, proceeds = 18k, gain = 3k
    assert monthly[mk]["ETH"]["gain"] == Decimal("3000")


def test_sell_below_cost_is_loss():
    txs = [
        tx(1, date(2024, 3, 1), "buy",  "BTC", "1", "200000"),
        tx(2, date(2024, 3, 15), "sell", "BTC", "1", "180000"),
    ]
    monthly = compute_gains(txs)
    mk = MonthKey(2024, 3)
    assert monthly[mk]["BTC"]["loss"] == Decimal("20000")
    assert monthly[mk]["BTC"]["gain"] == Decimal("0")


# --- DARF ---

def test_darf_below_35k_exempt():
    txs = [
        tx(1, date(2024, 5, 1), "buy",  "BTC", "0.5", "50000"),
        tx(2, date(2024, 5, 20), "sell", "BTC", "0.5", "80000"),
    ]
    # Gain = 30k — below R$35k exemption on BR exchange → no DARF
    obligations = darf_obligations(txs, 2024)
    assert obligations == []


def test_darf_above_35k():
    txs = [
        tx(1, date(2024, 6, 1), "buy",  "BTC", "1", "100000"),
        tx(2, date(2024, 6, 25), "sell", "BTC", "1", "150000"),
    ]
    # Gain = 50k → taxable = 50k - 35k = 15k → tax = 15k * 15% = R$2.250
    obligations = darf_obligations(txs, 2024)
    assert len(obligations) == 1
    assert obligations[0]["taxable_gain_brl"] == Decimal("15000")
    assert obligations[0]["tax_due_brl"] == Decimal("2250.00")


def test_darf_foreign_always_taxable():
    txs = [
        tx(1, date(2024, 7, 1), "buy",  "ETH", "1", "10000", is_br=False),
        tx(2, date(2024, 7, 15), "sell", "ETH", "1", "20000", is_br=False),
    ]
    # Gain = 10k — foreign exchange → no exemption → taxable
    obligations = darf_obligations(txs, 2024)
    assert len(obligations) == 1
    assert obligations[0]["is_foreign"] is True
    assert obligations[0]["taxable_gain_brl"] == Decimal("10000")


# --- DARF due date ---

def test_darf_due_date_jan_due_feb():
    assert darf_due_date(2024, 1) == "2024-02-29"  # Feb 2024 has 29 days (leap year)


def test_darf_due_date_dec_due_jan():
    result = darf_due_date(2024, 12)
    assert result.startswith("2025-01")


# --- IN 1888 ---

def test_in1888_above_threshold():
    txs = [
        tx(1, date(2024, 8, 1), "buy",  "BTC", "1", "200000", is_br=False, wallet_name="Coinbase"),
        tx(2, date(2024, 8, 15), "sell", "BTC", "1", "250000", is_br=False, wallet_name="Coinbase"),
    ]
    report = in1888_report(txs, 2024)
    assert len(report) == 1
    assert report[0]["must_report"] is True


def test_in1888_br_exchange_ignored():
    txs = [
        tx(1, date(2024, 9, 1), "buy",  "BTC", "1", "200000", is_br=True),
        tx(2, date(2024, 9, 15), "sell", "BTC", "1", "250000", is_br=True),
    ]
    # BR exchange not subject to IN 1888 self-reporting
    report = in1888_report(txs, 2024)
    assert report == []


# --- COAF ---

def test_coaf_flags_large_tx():
    txs = [
        tx(1, date(2024, 4, 10), "buy", "BTC", "0.1", "15000"),
    ]
    alerts = coaf_alerts(txs)
    assert len(alerts) == 1
    assert alerts[0]["total_brl"] == Decimal("15000")


def test_coaf_ignores_small_tx():
    txs = [
        tx(1, date(2024, 4, 10), "buy", "BTC", "0.01", "5000"),
    ]
    alerts = coaf_alerts(txs)
    assert alerts == []


# --- Cost basis snapshot ---

def test_cost_basis_snapshot():
    txs = [
        tx(1, date(2024, 1, 1), "buy", "BTC", "1", "100000"),
        tx(2, date(2024, 2, 1), "buy", "BTC", "1", "200000"),
        tx(3, date(2024, 3, 1), "sell", "BTC", "1", "180000"),
    ]
    snapshot = get_cost_basis_snapshot(txs)
    assert "BTC" in snapshot
    # Remaining: 1 BTC with avg cost 150k
    assert snapshot["BTC"]["quantity"] == Decimal("1")
    assert snapshot["BTC"]["total_cost"] == Decimal("150000")
