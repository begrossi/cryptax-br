"""
Solana on-chain transaction fetcher.

Uses the public Solana JSON-RPC endpoint (no API key). We list recent
signatures for the address, then for each successful transaction compute the
native SOL balance delta of the address from the transaction's pre/post
balances. A positive delta is a transfer_in, a negative delta a transfer_out
(the fee payer's delta already includes the network fee).

SPL token transfers are out of scope for now; only native SOL moves are
reported.
"""

import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal

import httpx

from app.integrations.onchain.base import BaseOnChainProvider, OnChainTransaction

_RPC_URL = "https://api.mainnet-beta.solana.com"
_LAMPORTS_PER_SOL = Decimal(10 ** 9)
_MAX_SIGNATURES = 100


def _account_keys(tx_json: dict) -> list[str]:
    """Return account pubkeys as strings, handling both legacy and v0 shapes."""
    msg = tx_json.get("transaction", {}).get("message", {})
    keys = msg.get("accountKeys", [])
    out = []
    for k in keys:
        # v0 encoded transactions may give objects {"pubkey": ...}; legacy gives strings
        out.append(k["pubkey"] if isinstance(k, dict) else k)
    return out


def _parse_native_delta(tx_json: dict, address: str, signature: str, block_time: int | None) -> OnChainTransaction | None:
    """Build a transfer record from the address's SOL balance delta, or None."""
    meta = tx_json.get("meta") or {}
    if meta.get("err") is not None:
        return None  # failed tx — no balance change to tax
    pre = meta.get("preBalances")
    post = meta.get("postBalances")
    keys = _account_keys(tx_json)
    if not pre or not post or address not in keys:
        return None

    idx = keys.index(address)
    delta = Decimal(post[idx]) - Decimal(pre[idx])  # lamports
    if delta == 0:
        return None
    if block_time is None:
        return None

    day = datetime.fromtimestamp(int(block_time), tz=timezone.utc).date()
    return OnChainTransaction(
        external_id=f"solana-{signature}",
        executed_at=day,
        transaction_type="transfer_in" if delta > 0 else "transfer_out",
        asset="SOL",
        amount=abs(delta) / _LAMPORTS_PER_SOL,
        chain="solana",
        from_address="" if delta > 0 else address,
        to_address=address if delta > 0 else "",
        notes="Solana on-chain tx",
    )


class SolanaProvider(BaseOnChainProvider):
    async def _rpc(self, client: httpx.AsyncClient, method: str, params: list) -> dict:
        try:
            resp = await client.post(_RPC_URL, json={
                "jsonrpc": "2.0", "id": 1, "method": method, "params": params,
            })
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"[solana] HTTP error on {method}: {exc}") from exc
        if "error" in data:
            raise RuntimeError(f"[solana] RPC error on {method}: {data['error']}")
        return data.get("result")

    async def fetch_transactions(
        self, address: str, since: date | None = None
    ) -> list[OnChainTransaction]:
        txs: list[OnChainTransaction] = []
        async with httpx.AsyncClient(timeout=30) as client:
            sigs = await self._rpc(
                client, "getSignaturesForAddress",
                [address, {"limit": _MAX_SIGNATURES}],
            ) or []

            for entry in sigs:
                if entry.get("err") is not None:
                    continue
                signature = entry["signature"]
                block_time = entry.get("blockTime")
                tx_json = await self._rpc(
                    client, "getTransaction",
                    [signature, {"maxSupportedTransactionVersion": 0, "encoding": "json"}],
                )
                if not tx_json:
                    continue
                rec = _parse_native_delta(tx_json, address, signature, block_time)
                if rec:
                    txs.append(rec)
                await asyncio.sleep(0.1)  # be gentle with the public RPC

        if since:
            txs = [t for t in txs if t.executed_at >= since]
        return txs
