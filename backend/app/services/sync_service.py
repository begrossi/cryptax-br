"""
Orchestrates syncing transactions from exchanges and on-chain sources.
Handles BRL price resolution, deduplication, and cost basis population.
"""

import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations.exchanges.base import RawTransaction
from app.integrations.exchanges.ccxt_exchange import CCXTExchange
from app.integrations.onchain.base import OnChainTransaction
from app.integrations.onchain.evm import EVMProvider, CHAIN_CONFIG
from app.integrations.onchain.bitcoin import BitcoinProvider
from app.integrations.onchain.solana import SolanaProvider
from app.integrations.prices.coingecko import fetch_price_brl
from app.models import Transaction, TransactionType, Wallet, WalletType, SyncLog, SyncStatus, AssetPrice
from app.services.crypto import decrypt_credentials

# Maps legacy WalletType enum values to their CCXT exchange IDs
LEGACY_EXCHANGE_MAP: dict[WalletType, str] = {
    WalletType.binance: "binance",
    WalletType.foxbit: "foxbit",
    WalletType.mercado_bitcoin: "mercadobitcoin",
}

ONCHAIN_WALLET_TYPES = {
    WalletType.evm_address,
    WalletType.solana_address,
    WalletType.bitcoin_address,
}


def _get_ccxt_exchange_id(wallet: Wallet) -> str | None:
    """Return the CCXT exchange ID for a wallet, or None if it's not an exchange wallet."""
    if wallet.wallet_type == WalletType.ccxt_exchange:
        try:
            return decrypt_credentials(wallet.credentials).get("exchange_id")
        except Exception:
            return None
    return LEGACY_EXCHANGE_MAP.get(wallet.wallet_type)


async def get_or_fetch_price(
    session: AsyncSession, asset: str, day: date
) -> Decimal | None:
    """Return cached BRL price or fetch from CoinGecko."""
    stmt = select(AssetPrice).where(AssetPrice.asset == asset, AssetPrice.date == day)
    cached = (await session.execute(stmt)).scalar_one_or_none()
    if cached:
        return cached.price_brl

    price = await fetch_price_brl(asset, day, settings.coingecko_api_key)
    if price:
        session.add(AssetPrice(asset=asset, date=day, price_brl=price))
        await session.flush()
    return price


async def sync_wallet(session: AsyncSession, wallet_id: int) -> SyncLog:
    wallet = await session.get(Wallet, wallet_id)
    if not wallet:
        raise ValueError(f"Wallet {wallet_id} not found")

    log = SyncLog(wallet_id=wallet_id, status=SyncStatus.running)
    session.add(log)
    await session.flush()

    try:
        added, warnings = await _do_sync(session, wallet)
        # Partial failures (e.g. one EVM chain rate-limited) don't fail the whole
        # sync — the data that did load is kept, and the issues are recorded.
        log.status = SyncStatus.success
        log.transactions_added = added
        if warnings:
            log.error_message = (" | ".join(warnings))[:900]
    except Exception as exc:
        log.status = SyncStatus.error
        log.error_message = str(exc)[:900]
        raise
    finally:
        log.finished_at = datetime.now(tz=timezone.utc)
        await session.commit()

    return log


async def _do_sync(session: AsyncSession, wallet: Wallet) -> tuple[int, list[str]]:
    # Find last synced date for incremental sync
    stmt = select(Transaction.executed_at).where(
        Transaction.wallet_id == wallet.id
    ).order_by(Transaction.executed_at.desc()).limit(1)
    last_date_row = (await session.execute(stmt)).scalar_one_or_none()
    since = last_date_row.date() if last_date_row else None

    raw_txs: list[RawTransaction | OnChainTransaction] = []
    warnings: list[str] = []

    exchange_id = _get_ccxt_exchange_id(wallet)
    if exchange_id:
        creds = decrypt_credentials(wallet.credentials)
        raw_txs = await CCXTExchange().fetch_transactions(
            api_key=creds["api_key"],
            api_secret=creds["api_secret"],
            since=since,
            exchange_id=exchange_id,
            password=creds.get("password"),
        )
    elif wallet.wallet_type in ONCHAIN_WALLET_TYPES:
        address = wallet.credentials
        if wallet.wallet_type == WalletType.evm_address:
            # Fetch each chain independently — a failure on one (rate limit,
            # plan limit, etc.) must not prevent the others from loading.
            for chain in CHAIN_CONFIG:
                provider = EVMProvider(chain, api_key=settings.etherscan_api_key)
                try:
                    txs = await provider.fetch_transactions(address, since=since)
                    raw_txs.extend(txs)
                except Exception as exc:
                    warnings.append(str(exc))
                await asyncio.sleep(0.25)
        elif wallet.wallet_type == WalletType.bitcoin_address:
            try:
                raw_txs.extend(await BitcoinProvider().fetch_transactions(address, since=since))
            except Exception as exc:
                warnings.append(str(exc))
        elif wallet.wallet_type == WalletType.solana_address:
            try:
                raw_txs.extend(await SolanaProvider().fetch_transactions(address, since=since))
            except Exception as exc:
                warnings.append(str(exc))

    added = 0
    for raw in raw_txs:
        external_id = raw.external_id
        exists = (await session.execute(
            select(Transaction).where(
                Transaction.wallet_id == wallet.id,
                Transaction.external_id == external_id,
            )
        )).scalar_one_or_none()
        if exists:
            continue

        asset = raw.asset
        tx_date = raw.executed_at if isinstance(raw.executed_at, date) else raw.executed_at

        if isinstance(raw, RawTransaction):
            if raw.quote_currency == "BRL":
                total_brl = raw.total_quote
            else:
                price = await get_or_fetch_price(session, asset, tx_date)
                total_brl = (price * raw.amount) if price else None
        else:
            price = await get_or_fetch_price(session, asset, tx_date)
            total_brl = (price * raw.amount) if price else None

        price_brl = (total_brl / raw.amount) if (total_brl and raw.amount > 0) else None

        tx = Transaction(
            wallet_id=wallet.id,
            external_id=external_id,
            executed_at=datetime.combine(tx_date, datetime.min.time()),
            transaction_type=TransactionType(raw.transaction_type),
            asset=asset,
            amount=raw.amount,
            price_brl=price_brl,
            total_brl=total_brl,
            chain=getattr(raw, "chain", None),
            from_address=getattr(raw, "from_address", None),
            to_address=getattr(raw, "to_address", None),
            notes=raw.notes,
        )
        session.add(tx)
        added += 1

    await session.flush()
    return added, warnings
