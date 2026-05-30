from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Wallet, SyncLog
from app.services.sync_service import sync_wallet
from app.services.self_transfer_detector import detect_self_transfers

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/detect-self-transfers")
async def run_detect_self_transfers(db: AsyncSession = Depends(get_db)):
    """
    Scan all transfer_in / transfer_out transactions and auto-mark pairs
    that look like self-transfers between own wallets.
    """
    marked = await detect_self_transfers(db)
    await db.commit()
    pairs = marked // 2
    return {
        "transactions_marked": marked,
        "pairs_found": pairs,
        "message": (
            f"{pairs} par(es) de auto-transferência detectado(s) e marcado(s)."
            if pairs else "Nenhum par de auto-transferência detectado."
        ),
    }


@router.post("/{wallet_id}")
async def trigger_sync(
    wallet_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    wallet = await db.get(Wallet, wallet_id)
    if not wallet:
        raise HTTPException(404, "Wallet not found")

    background_tasks.add_task(_run_sync, wallet_id)
    return {"message": f"Sync started for wallet {wallet_id}", "wallet_name": wallet.name}


@router.post("/all")
async def sync_all(background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Wallet))
    wallets = result.scalars().all()
    for wallet in wallets:
        background_tasks.add_task(_run_sync, wallet.id)
    return {"message": f"Sync started for {len(wallets)} wallet(s)"}


@router.get("/status", response_model=list[dict])
async def sync_status(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SyncLog).order_by(SyncLog.started_at.desc()).limit(50)
    )
    logs = result.scalars().all()
    return [
        {
            "id": log.id,
            "wallet_id": log.wallet_id,
            "started_at": log.started_at.isoformat(),
            "finished_at": log.finished_at.isoformat() if log.finished_at else None,
            "status": log.status,
            "transactions_added": log.transactions_added,
            "error_message": log.error_message,
        }
        for log in logs
    ]


async def _run_sync(wallet_id: int) -> None:
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        try:
            await sync_wallet(session, wallet_id)
            # Auto-detect self-transfers after every sync
            await detect_self_transfers(session)
            await session.commit()
        except Exception:
            pass  # errors are persisted to sync_log by sync_wallet
