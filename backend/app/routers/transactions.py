from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Transaction, TransactionType
from app.schemas.transaction import TransactionRead, TransactionSummary

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=list[TransactionRead])
async def list_transactions(
    wallet_id: int | None = Query(None),
    asset: str | None = Query(None),
    transaction_type: TransactionType | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Transaction).order_by(Transaction.executed_at.desc())
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
    return result.scalars().all()


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
        .group_by("yr", "mo", Transaction.asset)
        .order_by("yr", "mo", Transaction.asset)
    )
    result = await db.execute(stmt)
    rows = result.all()

    from decimal import Decimal
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
