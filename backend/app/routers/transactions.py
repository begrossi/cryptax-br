from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Transaction, TransactionType
from app.models.wallet import Wallet
from app.schemas.transaction import TransactionRead, TransactionSummary

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=list[TransactionRead])
async def list_transactions(
    wallet_id: int | None = Query(None),
    asset: str | None = Query(None),
    transaction_type: TransactionType | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    show_ignored: bool = Query(False),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Transaction, Wallet.name.label("wallet_name"))
        .join(Wallet, Transaction.wallet_id == Wallet.id)
        .order_by(Transaction.executed_at.desc())
    )
    if not show_ignored:
        stmt = stmt.where(Transaction.is_ignored == False)  # noqa: E712
    if wallet_id:
        stmt = stmt.where(Transaction.wallet_id == wallet_id)
    if asset:
        stmt = stmt.where(Transaction.asset == asset.upper())
    if transaction_type:
        stmt = stmt.where(Transaction.transaction_type == transaction_type)
    if date_from:
        stmt = stmt.where(Transaction.executed_at >= date_from)
    if date_to:
        stmt = stmt.where(Transaction.executed_at <= date_to)
    stmt = stmt.offset(offset).limit(limit)

    result = await db.execute(stmt)
    rows = result.all()
    return [
        TransactionRead.model_validate(tx).model_copy(update={"wallet_name": wallet_name})
        for tx, wallet_name in rows
    ]


@router.get("/pending-transfers", response_model=list[TransactionRead])
async def pending_transfers(db: AsyncSession = Depends(get_db)):
    """
    Transfer legs the auto-detector did NOT pair as self-transfers.

    The tax engine treats an unmarked transfer_out/transfer_in as a taxable
    disposal/acquisition. A missed match therefore creates a phantom gain or
    loss. Surfacing these lets the user review each one: mark it a self-transfer
    (custody move, skipped in tax) or leave it as a genuine buy/sell.
    """
    stmt = (
        select(Transaction, Wallet.name.label("wallet_name"))
        .join(Wallet, Transaction.wallet_id == Wallet.id)
        .where(
            Transaction.transaction_type.in_([
                TransactionType.transfer_in,
                TransactionType.transfer_out,
            ]),
            Transaction.is_self_transfer == False,  # noqa: E712
            Transaction.is_ignored == False,  # noqa: E712
        )
        .order_by(Transaction.executed_at.desc())
    )
    result = await db.execute(stmt)
    return [
        TransactionRead.model_validate(tx).model_copy(update={"wallet_name": wallet_name})
        for tx, wallet_name in result.all()
    ]


@router.get("/summary", response_model=list[TransactionSummary])
async def transactions_summary(
    year: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(
            func.strftime("%Y", Transaction.executed_at).label("yr"),
            func.strftime("%m", Transaction.executed_at).label("mo"),
            Transaction.asset,
            func.sum(
                func.case((Transaction.transaction_type.in_(["buy", "transfer_in", "earn"]), Transaction.total_brl), else_=0)
            ).label("buy_total"),
            func.sum(
                func.case((Transaction.transaction_type.in_(["sell", "transfer_out"]), Transaction.total_brl), else_=0)
            ).label("sell_total"),
            func.count(Transaction.id).label("count"),
        )
        .where(func.strftime("%Y", Transaction.executed_at) == str(year))
        .where(Transaction.is_ignored == False)  # noqa: E712
        .group_by("yr", "mo", Transaction.asset)
        .order_by("yr", "mo", Transaction.asset)
    )
    result = await db.execute(stmt)
    rows = result.all()

    from decimal import Decimal  # noqa: PLC0415
    return [
        TransactionSummary(
            year=int(r.yr),
            month=int(r.mo),
            asset=r.asset,
            buy_total_brl=r.buy_total or Decimal(0),
            sell_total_brl=r.sell_total or Decimal(0),
            gain_brl=(r.sell_total or Decimal(0)) - (r.buy_total or Decimal(0)),
            transaction_count=r.count,
        )
        for r in rows
    ]


class SelfTransferUpdate(BaseModel):
    is_self_transfer: bool


class IgnoreUpdate(BaseModel):
    is_ignored: bool


@router.patch("/{tx_id}/self-transfer", response_model=TransactionRead)
async def toggle_self_transfer(
    tx_id: int,
    body: SelfTransferUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Mark (or unmark) a transfer as a self-transfer between own wallets."""
    tx = await db.get(Transaction, tx_id)
    if not tx:
        raise HTTPException(404, "Transaction not found")
    if tx.transaction_type not in (TransactionType.transfer_in, TransactionType.transfer_out):
        raise HTTPException(400, "Only transfer_in / transfer_out can be marked as self-transfers")
    tx.is_self_transfer = body.is_self_transfer
    await db.commit()
    await db.refresh(tx)
    return tx


@router.patch("/{tx_id}/ignore", response_model=TransactionRead)
async def toggle_ignore(
    tx_id: int,
    body: IgnoreUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Mark (or unmark) a transaction as ignored (spam/dust/noise)."""
    tx = await db.get(Transaction, tx_id)
    if not tx:
        raise HTTPException(404, "Transaction not found")
    tx.is_ignored = body.is_ignored
    await db.commit()
    await db.refresh(tx)
    return tx
