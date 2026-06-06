"""
EVM on-chain transaction fetcher.
Supports any Etherscan-compatible API (Ethereum, BSC, Polygon, Arbitrum, Base, etc.).

Requires a free Etherscan API key (etherscan.io/apis).
Without a key, Etherscan rate-limits to ~1 req/5s which causes sync failures
when querying multiple chains and endpoints.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import httpx

from app.integrations.onchain.base import BaseOnChainProvider, OnChainTransaction

CHAIN_CONFIG: dict[str, dict] = {
    "ethereum": {
        "api_url": "https://api.etherscan.io/api",
        "native_asset": "ETH",
        "decimals": 18,
    },
    "bsc": {
        "api_url": "https://api.bscscan.com/api",
        "native_asset": "BNB",
        "decimals": 18,
    },
    "polygon": {
        "api_url": "https://api.polygonscan.com/api",
        "native_asset": "POL",
        "decimals": 18,
    },
    "arbitrum": {
        "api_url": "https://api.arbiscan.io/api",
        "native_asset": "ETH",
        "decimals": 18,
    },
    "base": {
        "api_url": "https://api.basescan.org/api",
        "native_asset": "ETH",
        "decimals": 18,
    },
    "optimism": {
        "api_url": "https://api-optimistic.etherscan.io/api",
        "native_asset": "ETH",
        "decimals": 18,
    },
}

# Etherscan messages that mean "valid empty result, not an error"
_EMPTY_MESSAGES = {"no transactions found", "no token transfers found", "no records found"}


class EVMProvider(BaseOnChainProvider):
    def __init__(self, chain: str, api_key: str = ""):
        self.chain = chain
        self.api_key = api_key
        cfg = CHAIN_CONFIG.get(chain, CHAIN_CONFIG["ethereum"])
        self.api_url = cfg["api_url"]
        self.native_asset = cfg["native_asset"]
        self.native_decimals = cfg["decimals"]

    def _params(self, extra: dict) -> dict:
        base = {"apikey": self.api_key or "YourApiKeyToken"}
        base.update(extra)
        return base

    async def _get(self, client: httpx.AsyncClient, params: dict, label: str) -> list:
        """Fetch one Etherscan page. Returns results list or raises on API errors."""
        try:
            resp = await client.get(self.api_url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"[{self.chain}] HTTP error fetching {label}: {exc}") from exc

        status = data.get("status")
        message = str(data.get("message", "")).lower()
        result = data.get("result", [])

        if status == "1":
            return result if isinstance(result, list) else []

        # Empty address — not an error
        if message in _EMPTY_MESSAGES or result == []:
            return []

        # Real API error (rate limit, invalid key, etc.)
        hint = " — set ETHERSCAN_API_KEY in .env (free at etherscan.io/apis)" if not self.api_key else ""
        raise RuntimeError(
            f"[{self.chain}] Etherscan error fetching {label}: {data.get('message', 'unknown')}{hint}"
        )

    async def fetch_transactions(
        self, address: str, since: date | None = None
    ) -> list[OnChainTransaction]:
        txs: list[OnChainTransaction] = []
        address = address.lower()

        async with httpx.AsyncClient(timeout=30) as client:
            native = await self._fetch_normal_txs(client, address)
            txs.extend(native)
            tokens = await self._fetch_token_transfers(client, address)
            txs.extend(tokens)

        if since:
            txs = [t for t in txs if t.executed_at >= since]

        return txs

    async def _fetch_normal_txs(
        self, client: httpx.AsyncClient, address: str
    ) -> list[OnChainTransaction]:
        params = self._params({
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": 0,
            "endblock": 99999999,
            "sort": "asc",
        })
        rows = await self._get(client, params, "native txs")

        result = []
        for tx in rows:
            if tx.get("isError") == "1":
                continue
            value = Decimal(tx["value"]) / Decimal(10 ** self.native_decimals)
            if value == 0:
                continue
            ts = datetime.fromtimestamp(int(tx["timeStamp"]), tz=timezone.utc).date()
            is_incoming = tx["to"].lower() == address
            result.append(OnChainTransaction(
                external_id=f"{self.chain}-{tx['hash']}",
                executed_at=ts,
                transaction_type="transfer_in" if is_incoming else "transfer_out",
                asset=self.native_asset,
                amount=value,
                chain=self.chain,
                from_address=tx["from"],
                to_address=tx["to"],
                notes=f"EVM tx on {self.chain}",
            ))
        return result

    async def _fetch_token_transfers(
        self, client: httpx.AsyncClient, address: str
    ) -> list[OnChainTransaction]:
        params = self._params({
            "module": "account",
            "action": "tokentx",
            "address": address,
            "startblock": 0,
            "endblock": 99999999,
            "sort": "asc",
        })
        rows = await self._get(client, params, "token transfers")

        result = []
        for tx in rows:
            decimals = int(tx.get("tokenDecimal", 18))
            amount = Decimal(tx["value"]) / Decimal(10 ** decimals)
            if amount == 0:
                continue
            ts = datetime.fromtimestamp(int(tx["timeStamp"]), tz=timezone.utc).date()
            symbol = tx.get("tokenSymbol", "UNKNOWN")
            is_incoming = tx["to"].lower() == address
            result.append(OnChainTransaction(
                external_id=f"{self.chain}-token-{tx['hash']}-{symbol}",
                executed_at=ts,
                transaction_type="transfer_in" if is_incoming else "transfer_out",
                asset=symbol,
                amount=amount,
                chain=self.chain,
                from_address=tx["from"],
                to_address=tx["to"],
                notes=f"ERC-20 {symbol} on {self.chain}",
            ))
        return result
