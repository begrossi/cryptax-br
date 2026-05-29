"""
Binance exchange integration.
Fetches: spot trades, deposits, withdrawals.

API docs: https://binance-docs.github.io/apidocs/spot/en/
Auth: HMAC-SHA256 signed requests.
"""

import hashlib
import hmac
import time
from datetime import date, datetime, timezone
from decimal import Decimal
from urllib.parse import urlencode

import httpx

from app.integrations.exchanges.base import BaseExchange, RawTransaction

BASE_URL = "https://api.binance.com"


def _sign(params: dict, secret: str) -> str:
    query = urlencode(params)
    return hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()


def _ts_ms() -> int:
    return int(time.time() * 1000)


def _date_to_ms(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000)


class BinanceExchange(BaseExchange):
    async def fetch_transactions(
        self, api_key: str, api_secret: str, since: date | None = None
    ) -> list[RawTransaction]:
        txs: list[RawTransaction] = []
        headers = {"X-MBX-APIKEY": api_key}
        since_ms = _date_to_ms(since) if since else None

        async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
            # Fetch all trading symbols (we iterate BRL pairs and main crypto pairs)
            symbols = await self._get_brl_symbols(client, headers)
            for symbol in symbols:
                trades = await self._fetch_trades(client, headers, api_secret, symbol, since_ms)
                txs.extend(trades)

            # Deposits
            deposits = await self._fetch_deposits(client, headers, api_secret, since_ms)
            txs.extend(deposits)

            # Withdrawals
            withdrawals = await self._fetch_withdrawals(client, headers, api_secret, since_ms)
            txs.extend(withdrawals)

        return txs

    async def _get_brl_symbols(self, client: httpx.AsyncClient, headers: dict) -> list[str]:
        """Get all symbols ending in BRL or USDT that the user has traded."""
        try:
            resp = await client.get("/api/v3/exchangeInfo")
            resp.raise_for_status()
            all_symbols = [s["symbol"] for s in resp.json()["symbols"]
                           if s["quoteAsset"] in ("BRL", "USDT", "BUSD", "BTC", "ETH")]
            return all_symbols[:100]  # limit for safety; real impl should filter by account trades
        except httpx.HTTPError:
            return []

    async def _fetch_trades(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        secret: str,
        symbol: str,
        since_ms: int | None,
    ) -> list[RawTransaction]:
        params: dict = {"symbol": symbol, "limit": 1000, "timestamp": _ts_ms()}
        if since_ms:
            params["startTime"] = since_ms
        params["signature"] = _sign(params, secret)

        try:
            resp = await client.get("/api/v3/myTrades", headers=headers, params=params)
            if resp.status_code == 400:  # invalid symbol for this account
                return []
            resp.raise_for_status()
        except httpx.HTTPError:
            return []

        result = []
        for trade in resp.json():
            # Parse symbol: e.g. BTCBRL → base=BTC, quote=BRL
            # We rely on the exchange info mapping; simple heuristic here
            qty = Decimal(trade["qty"])
            price = Decimal(trade["price"])
            quote_qty = Decimal(trade["quoteQty"])
            is_buyer = trade["isBuyer"]
            ts = datetime.fromtimestamp(trade["time"] / 1000, tz=timezone.utc).date()

            # Determine asset and quote from symbol (simplified: assume 3-char base)
            base = symbol.replace("BRL", "").replace("USDT", "").replace("BUSD", "")
            quote = symbol[len(base):]

            result.append(RawTransaction(
                external_id=f"binance-trade-{trade['id']}",
                executed_at=ts,
                transaction_type="buy" if is_buyer else "sell",
                asset=base,
                amount=qty,
                total_quote=quote_qty,
                quote_currency=quote,
                notes=f"Binance spot trade {symbol}",
            ))
        return result

    async def _fetch_deposits(
        self, client: httpx.AsyncClient, headers: dict, secret: str, since_ms: int | None
    ) -> list[RawTransaction]:
        params: dict = {"timestamp": _ts_ms(), "status": 1}  # status=1: success
        if since_ms:
            params["startTime"] = since_ms
        params["signature"] = _sign(params, secret)

        try:
            resp = await client.get("/sapi/v1/capital/deposit/hisrec", headers=headers, params=params)
            resp.raise_for_status()
        except httpx.HTTPError:
            return []

        result = []
        for dep in resp.json():
            ts = datetime.fromtimestamp(dep["insertTime"] / 1000, tz=timezone.utc).date()
            result.append(RawTransaction(
                external_id=f"binance-deposit-{dep['txId']}",
                executed_at=ts,
                transaction_type="transfer_in",
                asset=dep["coin"],
                amount=Decimal(dep["amount"]),
                total_quote=Decimal(0),
                quote_currency="BRL",
                notes="Depósito Binance",
            ))
        return result

    async def _fetch_withdrawals(
        self, client: httpx.AsyncClient, headers: dict, secret: str, since_ms: int | None
    ) -> list[RawTransaction]:
        params: dict = {"timestamp": _ts_ms(), "status": 6}  # status=6: completed
        if since_ms:
            params["startTime"] = since_ms
        params["signature"] = _sign(params, secret)

        try:
            resp = await client.get("/sapi/v1/capital/withdraw/history", headers=headers, params=params)
            resp.raise_for_status()
        except httpx.HTTPError:
            return []

        result = []
        for wd in resp.json():
            ts = datetime.fromtimestamp(wd["applyTime"] / 1000, tz=timezone.utc).date()
            result.append(RawTransaction(
                external_id=f"binance-withdraw-{wd['id']}",
                executed_at=ts,
                transaction_type="transfer_out",
                asset=wd["coin"],
                amount=Decimal(wd["amount"]),
                total_quote=Decimal(0),
                quote_currency="BRL",
                notes="Saque Binance",
            ))
        return result
