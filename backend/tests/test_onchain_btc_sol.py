"""
Parsing tests for Bitcoin and Solana on-chain providers (issue #7).
No network — the HTTP layer is separated from the pure parsing functions.
"""

from decimal import Decimal

from app.integrations.onchain.bitcoin import _parse_address_txs
from app.integrations.onchain.solana import _parse_native_delta

ADDR_BTC = "bc1qexample"
ADDR_SOL = "SoLaddrExample1111111111111111111111111111"

# block_time 1704067200 = 2024-01-01 UTC
_BTC_ROWS = [
    {  # received 0.5 BTC (50_000_000 sats) — inbound
        "txid": "aaa",
        "status": {"confirmed": True, "block_time": 1704067200},
        "vin": [{"prevout": {"scriptpubkey_address": "other", "value": 50_000_000}}],
        "vout": [{"scriptpubkey_address": ADDR_BTC, "value": 50_000_000}],
    },
    {  # spent 0.3 BTC net (funded 1 BTC input, got 0.7 change) — outbound
        "txid": "bbb",
        "status": {"confirmed": True, "block_time": 1704067200},
        "vin": [{"prevout": {"scriptpubkey_address": ADDR_BTC, "value": 100_000_000}}],
        "vout": [
            {"scriptpubkey_address": "dest", "value": 30_000_000},
            {"scriptpubkey_address": ADDR_BTC, "value": 70_000_000},
        ],
    },
    {  # unconfirmed — ignored
        "txid": "ccc",
        "status": {"confirmed": False},
        "vin": [], "vout": [{"scriptpubkey_address": ADDR_BTC, "value": 1}],
    },
]


def test_btc_inbound_and_outbound_net():
    recs = _parse_address_txs(_BTC_ROWS, ADDR_BTC)
    assert len(recs) == 2
    inbound = next(r for r in recs if r.external_id == "bitcoin-aaa")
    outbound = next(r for r in recs if r.external_id == "bitcoin-bbb")
    assert inbound.transaction_type == "transfer_in"
    assert inbound.amount == Decimal("0.5")
    assert outbound.transaction_type == "transfer_out"
    assert outbound.amount == Decimal("0.3")  # 1.0 spent - 0.7 change
    assert outbound.asset == "BTC" and outbound.chain == "bitcoin"


def test_sol_balance_delta_inbound():
    tx_json = {
        "meta": {"err": None, "preBalances": [1_000_000_000, 0], "postBalances": [3_000_000_000, 0]},
        "transaction": {"message": {"accountKeys": [ADDR_SOL, "other"]}},
    }
    rec = _parse_native_delta(tx_json, ADDR_SOL, "sig1", 1704067200)
    assert rec is not None
    assert rec.transaction_type == "transfer_in"
    assert rec.amount == Decimal("2")  # 2 SOL
    assert rec.asset == "SOL" and rec.chain == "solana"


def test_sol_failed_tx_skipped():
    tx_json = {
        "meta": {"err": {"x": 1}, "preBalances": [1_000_000_000], "postBalances": [500_000_000]},
        "transaction": {"message": {"accountKeys": [ADDR_SOL]}},
    }
    assert _parse_native_delta(tx_json, ADDR_SOL, "sig2", 1704067200) is None


def test_sol_v0_account_key_objects():
    tx_json = {
        "meta": {"err": None, "preBalances": [5_000_000_000], "postBalances": [4_000_000_000]},
        "transaction": {"message": {"accountKeys": [{"pubkey": ADDR_SOL}]}},
    }
    rec = _parse_native_delta(tx_json, ADDR_SOL, "sig3", 1704067200)
    assert rec is not None and rec.transaction_type == "transfer_out"
    assert rec.amount == Decimal("1")
