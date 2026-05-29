"""
EVM on-chain transaction fetcher.
Supports any Etherscan-compatible API (Ethereum, BSC, Polygon, Arbitrum, Base, etc.).

Requires a free Etherscan API key (or equivalent per chain).
Addresses are public — calling Etherscan reveals your address to them.
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


class EVMProvider(BaseOnChainProvider):
    def __init__(self, chain: str, api_key: str = ""):
        self.chain = chain
        self.api_key = api_key
        cfg = CHAIN_CONFIG.get(chain, CHAIN_CONFIG["ethereum"])
        self.api_url = cfg["api_url"]
        self.native_asset = cfg["native_asset"]
        self.native_decimals = cfg["decimals"]

    async def fetch_transactions(
        self, address: str, since: date | None = None
    ) -> list[OnChainTransaction]:
        txs: list[OnChainTransaction] = []
        address = address.lower()
        start_block = 0

        async with httpx.AsyncClient(timeout=30) as client:
            # Native token transactions
            native = await self._fetch_normal_txs(client, address, start_block)
            txs.extend(native)
            # ERC-20 token transfers
            tokens = await self._fetch_token_transfers(client, address, start_block)
            txs.extend(tokens)

        if since:
            txs = [t for t in txs if t.executed_at >= since]

        return txs

    async def _fetch_normal_txs(
        self, client: httpx.AsyncClient, address: str, start_block: int
    ) -> list[OnChainTransaction]:
        params = {
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": start_block,
            "endblock": 99999999,
            "sort": "asc",
            "apikey": self.api_key or "YourApiKeyToken",
        }
        try:
            resp = await client.get(self.api_url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError:
            return []

        if data.get("status") != "1":
            return []

        result = []
        for tx in data["result"]:
            if tx["isError"] == "1":
                continue
            ts = datetime.fromtimestamp(int(tx["timeStamp"]), tz=timezone.utc).date()
            value = Decimal(tx["value"]) / Decimal(10 ** self.native_decimals)
            if value == 0:
                continue

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
        self, client: httpx.AsyncClient, address: str, start_block: int
    ) -> list[OnChainTransaction]:
        params = {
            "module": "account",
            "action": "tokentx",
            "address": address,
            "startblock": start_block,
            "endblock": 99999999,
            "sort": "asc",
            "apikey": self.api_key or "YourApiKeyToken",
        }
        try:
            resp = await client.get(self.api_url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError:
            return []

        if data.get("status") != "1":
            return []

        result = []
        for tx in data["result"]:
            ts = datetime.fromtimestamp(int(tx["timeStamp"]), tz=timezone.utc).date()
            decimals = int(tx.get("tokenDecimal", 18))
            amount = Decimal(tx["value"]) / Decimal(10 ** decimals)
            if amount == 0:
                continue
            symbol = tx.get("tokenSymbol", "UNKNOWN")
            is_incoming = tx["to"].lower() == address
            result.append(OnChainTransaction(
                external_id=f"{self.chain}-token-{tx['hash']}-{tx['tokenSymbol']}",
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
