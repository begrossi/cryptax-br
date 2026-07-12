"""
DB-backed test for the pending-transfers review endpoint (issue #4).

A transfer that the auto-detector pairs as a self-transfer must NOT appear.
A transfer it cannot pair MUST appear, so the user can review it instead of
being silently taxed on a phantom gain.
"""

from datetime import datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth import require_api_token
from app.database import Base, get_db
from app.main import app
from app.models import Transaction, TransactionType, Wallet, WalletType
from app.services.self_transfer_detector import detect_self_transfers


def _tx(wallet_id, ext, ttype, asset, amount, day):
    return Transaction(
        wallet_id=wallet_id, external_id=ext, transaction_type=ttype,
        asset=asset, amount=Decimal(amount), executed_at=datetime(2024, 3, day),
        total_brl=Decimal("50000"),
    )


@pytest.mark.asyncio
async def test_pending_transfers_lists_only_unmatched():
    engine = create_async_engine("sqlite+aiosqlite://")  # in-memory
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with Session() as s:
        s.add_all([
            Wallet(id=1, name="A", wallet_type=WalletType.evm_address, credentials="0xa"),
            Wallet(id=2, name="B", wallet_type=WalletType.evm_address, credentials="0xb"),
        ])
        await s.flush()
        # Matchable pair: 1 BTC out of A on day 1, 1 BTC into B on day 1.
        s.add(_tx(1, "out-1", TransactionType.transfer_out, "BTC", "1.0", 1))
        s.add(_tx(2, "in-1", TransactionType.transfer_in, "BTC", "1.0", 1))
        # Lone, unpairable transfer_out (no matching inbound leg).
        s.add(_tx(1, "out-2", TransactionType.transfer_out, "ETH", "5.0", 10))
        await s.commit()
        marked = await detect_self_transfers(s)
        await s.commit()
        assert marked == 2  # the BTC pair got matched

    async def _override_db():
        async with Session() as s:
            yield s

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[require_api_token] = lambda: None
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            r = await c.get("/transactions/pending-transfers")
        assert r.status_code == 200
        data = r.json()
        assert [t["external_id"] for t in data] == ["out-2"]  # only the unmatched leg
    finally:
        app.dependency_overrides.clear()

    await engine.dispose()
