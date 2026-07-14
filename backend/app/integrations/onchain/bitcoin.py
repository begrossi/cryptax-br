"""
Bitcoin on-chain transaction fetcher.

Uses the public mempool.space REST API (no API key required). For each
confirmed transaction touching the address we compute the net BTC movement of
that address — received (sum of outputs to it) minus sent (sum of the inputs it
funded, which already includes the miner fee and any change). A positive net is
a transfer_in, a negative net a transfer_out.

Token concepts (BRC-20, Ordinals) are out of scope; only native BTC value moves
are reported.
"""

import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal

import httpx

from app.integrations.onchain.base import BaseOnChainProvider, OnChainTransaction

_MEMPOOL_URL = "https://mempool.space/api"
_SATS_PER_BTC = Decimal(10 ** 8)
_MAX_PAGES = 10  # mempool returns 25 confirmed txs/page; cap total scanned


def _parse_address_txs(rows: list[dict], address: str) -> list[OnChainTransaction]:
    """Turn mempool.space address-tx JSON into OnChainTransaction records."""
    out: list[OnChainTransaction] = []
    for tx in rows:
        status = tx.get("status", {})
        if not status.get("confirmed"):
            continue  # ignore unconfirmed — not final

        sent = sum(
            Decimal(vin.get("prevout", {}).get("value", 0))
            for vin in tx.get("vin", [])
            if vin.get("prevout", {}).get("scriptpubkey_address") == address
        )
        received = sum(
            Decimal(vout.get("value", 0))
            for vout in tx.get("vout", [])
            if vout.get("scriptpubkey_address") == address
        )
        net = received - sent  # in satoshis; positive = inbound
        if net == 0:
            continue

        block_time = status.get("block_time")
        if not block_time:
            continue
        day = datetime.fromtimestamp(int(block_time), tz=timezone.utc).date()

        out.append(OnChainTransaction(
            external_id=f"bitcoin-{tx['txid']}",
            executed_at=day,
            transaction_type="transfer_in" if net > 0 else "transfer_out",
            asset="BTC",
            amount=abs(net) / _SATS_PER_BTC,
            chain="bitcoin",
            from_address="" if net > 0 else address,
            to_address=address if net > 0 else "",
            notes="Bitcoin on-chain tx",
        ))
    return out


class BitcoinProvider(BaseOnChainProvider):
    async def fetch_transactions(
        self, address: str, since: date | None = None
    ) -> list[OnChainTransaction]:
        txs: list[OnChainTransaction] = []
        async with httpx.AsyncClient(timeout=30) as client:
            last_seen: str | None = None
            for _ in range(_MAX_PAGES):
                url = f"{_MEMPOOL_URL}/address/{address}/txs"
                if last_seen:
                    url = f"{url}/chain/{last_seen}"
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    rows = resp.json()
                except httpx.HTTPError as exc:
                    raise RuntimeError(f"[bitcoin] HTTP error fetching txs: {exc}") from exc

                if not rows:
                    break
                txs.extend(_parse_address_txs(rows, address))
                last_seen = rows[-1]["txid"]
                if len(rows) < 25:
                    break
                await asyncio.sleep(0.25)

        if since:
            txs = [t for t in txs if t.executed_at >= since]
        return txs
