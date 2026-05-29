"""
CoinGecko price fetcher for historical BRL prices.
Uses the free public API (no key needed for basic historical data).
Respects rate limiting with exponential backoff.
"""

import asyncio
from datetime import date, timedelta
from decimal import Decimal

import httpx

BASE_URL = "https://api.coingecko.com/api/v3"

# CoinGecko coin IDs for common assets
COIN_ID_MAP: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "BNB": "binancecoin",
    "SOL": "solana",
    "MATIC": "matic-network",
    "POL": "matic-network",
    "ARB": "arbitrum",
    "OP": "optimism",
    "USDT": "tether",
    "USDC": "usd-coin",
    "BUSD": "binance-usd",
    "DAI": "dai",
    "LINK": "chainlink",
    "UNI": "uniswap",
    "AAVE": "aave",
    "CRV": "curve-dao-token",
    "SUSHI": "sushi",
    "DOGE": "dogecoin",
    "ADA": "cardano",
    "DOT": "polkadot",
    "AVAX": "avalanche-2",
    "ATOM": "cosmos",
    "LTC": "litecoin",
    "XRP": "ripple",
}


def get_coin_id(symbol: str) -> str | None:
    return COIN_ID_MAP.get(symbol.upper())


async def fetch_price_brl(symbol: str, day: date, api_key: str = "") -> Decimal | None:
    """Fetch historical BRL price for an asset on a given date."""
    coin_id = get_coin_id(symbol)
    if not coin_id:
        return None

    date_str = day.strftime("%d-%m-%Y")
    headers = {"x-cg-demo-api-key": api_key} if api_key else {}

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{BASE_URL}/coins/{coin_id}/history",
                    params={"date": date_str, "localization": "false"},
                    headers=headers,
                )
                if resp.status_code == 429:
                    await asyncio.sleep(2 ** attempt * 5)
                    continue
                resp.raise_for_status()
                data = resp.json()
                price = data.get("market_data", {}).get("current_price", {}).get("brl")
                return Decimal(str(price)) if price else None
        except httpx.HTTPError:
            if attempt == 2:
                return None
            await asyncio.sleep(2 ** attempt)
    return None


async def fetch_price_range_brl(
    symbol: str, start: date, end: date, api_key: str = ""
) -> dict[date, Decimal]:
    """Fetch prices for a date range using market_chart endpoint (more efficient)."""
    coin_id = get_coin_id(symbol)
    if not coin_id:
        return {}

    days_count = (end - start).days + 1
    headers = {"x-cg-demo-api-key": api_key} if api_key else {}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{BASE_URL}/coins/{coin_id}/market_chart",
                params={"vs_currency": "brl", "days": days_count, "interval": "daily"},
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError:
        return {}

    result: dict[date, Decimal] = {}
    for ts_ms, price in data.get("prices", []):
        d = date.fromtimestamp(ts_ms / 1000)
        if start <= d <= end:
            result[d] = Decimal(str(price))

    return result
