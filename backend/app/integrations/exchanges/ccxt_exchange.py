"""
CCXT-based exchange integration.
Supports any of the 100+ exchanges in the CCXT library through a unified interface.

Fetches: spot trades, deposits, withdrawals.
Falls back gracefully when an exchange does not support a particular endpoint
(CCXT's `has` dict is checked before each call).
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import ccxt.async_support as ccxt

from app.integrations.exchanges.base import BaseExchange, RawTransaction


def _ms_since(d: date | None) -> int | None:
    if d is None:
        return None
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000)


def _date_from_ms(ms: int | None) -> date:
    if not ms:
        return datetime.now(tz=timezone.utc).date()
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date()


def _normalize_trade(t: dict, exchange_id: str) -> RawTransaction:
    symbol: str = t.get("symbol", "/")
    parts = symbol.split("/")
    asset = parts[0] if parts else "UNKNOWN"
    quote = parts[1] if len(parts) > 1 else "USDT"

    side = t.get("side", "buy").lower()
    tx_type = "buy" if side == "buy" else "sell"

    amount = Decimal(str(t.get("amount") or 0))
    cost = Decimal(str(t.get("cost") or 0))

    return RawTransaction(
        external_id=f"{exchange_id}-trade-{t['id']}",
        executed_at=_date_from_ms(t.get("timestamp")),
        transaction_type=tx_type,
        asset=asset,
        amount=amount,
        total_quote=cost,
        quote_currency=quote,
        notes=f"{exchange_id} spot trade {symbol}",
    )


def _normalize_deposit(d: dict, exchange_id: str) -> RawTransaction:
    currency = d.get("currency") or d.get("coin") or "UNKNOWN"
    amount = Decimal(str(d.get("amount") or 0))
    tx_id = d.get("txid") or d.get("id") or "unknown"

    return RawTransaction(
        external_id=f"{exchange_id}-deposit-{tx_id}",
        executed_at=_date_from_ms(d.get("timestamp")),
        transaction_type="transfer_in",
        asset=currency,
        amount=amount,
        total_quote=Decimal(0),
        quote_currency="BRL",
        notes=f"Depósito {exchange_id}",
    )


def _normalize_withdrawal(w: dict, exchange_id: str) -> RawTransaction:
    currency = w.get("currency") or w.get("coin") or "UNKNOWN"
    amount = Decimal(str(w.get("amount") or 0))
    tx_id = w.get("txid") or w.get("id") or "unknown"

    return RawTransaction(
        external_id=f"{exchange_id}-withdrawal-{tx_id}",
        executed_at=_date_from_ms(w.get("timestamp")),
        transaction_type="transfer_out",
        asset=currency,
        amount=amount,
        total_quote=Decimal(0),
        quote_currency="BRL",
        notes=f"Saque {exchange_id}",
    )


class CCXTExchange(BaseExchange):
    async def fetch_transactions(
        self,
        api_key: str,
        api_secret: str,
        since: date | None = None,
        exchange_id: str = "binance",
        password: str | None = None,
    ) -> list[RawTransaction]:
        exchange_class = getattr(ccxt, exchange_id, None)
        if exchange_class is None:
            raise ValueError(f"Exchange '{exchange_id}' not supported by CCXT")

        config: dict = {
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
        }
        if password:
            config["password"] = password

        exchange = exchange_class(config)
        since_ms = _ms_since(since)
        txs: list[RawTransaction] = []

        try:
            # Spot trades
            if exchange.has.get("fetchMyTrades"):
                try:
                    trades = await exchange.fetch_my_trades(since=since_ms, limit=1000)
                    txs.extend(_normalize_trade(t, exchange_id) for t in trades)
                except (ccxt.BaseError, Exception):
                    pass

            # Deposits
            if exchange.has.get("fetchDeposits"):
                try:
                    deposits = await exchange.fetch_deposits(since=since_ms)
                    txs.extend(_normalize_deposit(d, exchange_id) for d in deposits)
                except (ccxt.BaseError, Exception):
                    pass
            elif exchange.has.get("fetchTransactions"):
                try:
                    all_txs = await exchange.fetch_transactions(since=since_ms)
                    for item in all_txs:
                        if item.get("type") == "deposit":
                            txs.append(_normalize_deposit(item, exchange_id))
                        elif item.get("type") == "withdrawal":
                            txs.append(_normalize_withdrawal(item, exchange_id))
                except (ccxt.BaseError, Exception):
                    pass

            # Withdrawals (only if not already covered by fetchTransactions)
            if exchange.has.get("fetchWithdrawals") and not exchange.has.get("fetchTransactions"):
                try:
                    withdrawals = await exchange.fetch_withdrawals(since=since_ms)
                    txs.extend(_normalize_withdrawal(w, exchange_id) for w in withdrawals)
                except (ccxt.BaseError, Exception):
                    pass

        finally:
            await exchange.close()

        return txs
