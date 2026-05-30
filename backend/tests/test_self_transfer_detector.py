"""
Unit tests for the self-transfer detection algorithm.
Tests only _match() — no DB required.
"""

from datetime import date
from decimal import Decimal

from app.services.self_transfer_detector import _match, _Candidate, TIME_WINDOW_DAYS

# Helper
def cand(tx_id: int, wallet_id: int, asset: str, amount: str, day: date) -> _Candidate:
    return _Candidate(tx_id=tx_id, wallet_id=wallet_id, asset=asset,
                      amount=Decimal(amount), executed_at=day)


D1 = date(2024, 3, 1)
D2 = date(2024, 3, 2)
D3 = date(2024, 3, 5)  # 4 days after D1 — outside window


# --- Basic matching ---

def test_exact_match_same_day():
    outs = [cand(1, 1, "BTC", "1.0", D1)]
    ins  = [cand(2, 2, "BTC", "1.0", D1)]
    pairs = _match(outs, ins)
    assert pairs == [(1, 2)]


def test_match_with_fee_deducted():
    # Sent 1 ETH, received 0.995 ETH (0.5% network fee)
    outs = [cand(1, 1, "ETH", "1.0",   D1)]
    ins  = [cand(2, 2, "ETH", "0.995", D1)]
    pairs = _match(outs, ins)
    assert pairs == [(1, 2)]


def test_match_next_day():
    outs = [cand(1, 1, "BTC", "0.5", D1)]
    ins  = [cand(2, 2, "BTC", "0.5", D2)]
    pairs = _match(outs, ins)
    assert pairs == [(1, 2)]


def test_no_match_outside_time_window():
    outs = [cand(1, 1, "BTC", "1.0", D1)]
    ins  = [cand(2, 2, "BTC", "1.0", D3)]  # 4 days later
    pairs = _match(outs, ins)
    assert pairs == []


def test_no_match_different_asset():
    outs = [cand(1, 1, "BTC", "1.0", D1)]
    ins  = [cand(2, 2, "ETH", "1.0", D1)]
    pairs = _match(outs, ins)
    assert pairs == []


def test_no_match_same_wallet():
    # transfer_out and transfer_in from same wallet shouldn't match
    outs = [cand(1, 1, "BTC", "1.0", D1)]
    ins  = [cand(2, 1, "BTC", "1.0", D1)]
    pairs = _match(outs, ins)
    assert pairs == []


def test_no_match_amount_too_small():
    # Received only 80% — exceeds 10% fee tolerance
    outs = [cand(1, 1, "ETH", "1.0", D1)]
    ins  = [cand(2, 2, "ETH", "0.80", D1)]
    pairs = _match(outs, ins)
    assert pairs == []


def test_no_match_amount_too_large():
    # Received more than sent (impossible for a fee scenario)
    outs = [cand(1, 1, "ETH", "1.0",  D1)]
    ins  = [cand(2, 2, "ETH", "1.10", D1)]
    pairs = _match(outs, ins)
    assert pairs == []


# --- 1:1 matching (greedy) ---

def test_one_to_one_two_pairs():
    outs = [cand(1, 1, "BTC", "0.5", D1), cand(3, 1, "ETH", "2.0", D1)]
    ins  = [cand(2, 2, "BTC", "0.5", D1), cand(4, 2, "ETH", "2.0", D1)]
    pairs = _match(outs, ins)
    assert set(pairs) == {(1, 2), (3, 4)}


def test_closer_match_wins():
    # Two candidates for the same transfer_out; the same-day one should win
    outs = [cand(1, 1, "BTC", "1.0", D1)]
    ins  = [
        cand(2, 2, "BTC", "1.0", D2),  # 1 day later
        cand(3, 3, "BTC", "1.0", D1),  # same day — should win
    ]
    pairs = _match(outs, ins)
    assert pairs == [(1, 3)]


def test_no_double_match():
    # One transfer_out cannot match two transfer_ins
    outs = [cand(1, 1, "BTC", "1.0", D1)]
    ins  = [cand(2, 2, "BTC", "1.0", D1), cand(3, 3, "BTC", "1.0", D1)]
    pairs = _match(outs, ins)
    assert len(pairs) == 1


def test_no_double_use_of_transfer_in():
    # One transfer_in cannot match two transfer_outs
    outs = [cand(1, 1, "ETH", "1.0", D1), cand(3, 3, "ETH", "1.0", D1)]
    ins  = [cand(2, 2, "ETH", "1.0", D1)]
    pairs = _match(outs, ins)
    assert len(pairs) == 1


def test_empty_inputs():
    assert _match([], []) == []
    assert _match([cand(1, 1, "BTC", "1.0", D1)], []) == []
    assert _match([], [cand(1, 1, "BTC", "1.0", D1)]) == []


# --- Edge cases ---

def test_zero_amount_ignored():
    outs = [cand(1, 1, "ETH", "0", D1)]
    ins  = [cand(2, 2, "ETH", "0", D1)]
    pairs = _match(outs, ins)
    assert pairs == []


def test_common_pattern_exchange_to_self_custody():
    # Withdraw 0.1 BTC from Binance (wallet 1), receive 0.0998 BTC in MetaMask (wallet 2)
    outs = [cand(10, 1, "BTC", "0.1",    D1)]
    ins  = [cand(20, 2, "BTC", "0.0998", D2)]
    pairs = _match(outs, ins)
    assert pairs == [(10, 20)]
