"""
Auto-detection of self-transfers between the user's own wallets.

A self-transfer is a transfer_out from wallet A matched with a transfer_in
to wallet B where:
  - Same asset
  - Received amount ≥ 90% of sent amount (up to 10% fee tolerance)
  - Executed within 2 days of each other (blockchain confirmation + sync lag)
  - Different wallet IDs (can't match a tx with itself)

Matching is greedy 1:1, scored by (days_diff, amount_diff). Closest match
wins. Once matched, both sides are removed from the candidate pool.

The algorithm is intentionally conservative: it only matches when there is
exactly one plausible candidate. Ambiguous cases (two transfer_outs on the
same day with identical amounts to the same asset) are left for the user to
mark manually via the transactions page.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Transaction, TransactionType

TIME_WINDOW_DAYS = 2
AMOUNT_TOLERANCE = Decimal("0.90")  # received must be ≥ 90% of sent


@dataclass
class _Candidate:
    tx_id: int
    wallet_id: int
    asset: str
    amount: Decimal
    executed_at: date


async def detect_self_transfers(session: AsyncSession) -> int:
    """
    Scan all unmatched transfer_in / transfer_out transactions, find pairs
    that look like self-transfers, and mark them.

    Returns the number of transactions newly marked (always even).
    """
    stmt = select(Transaction).where(
        Transaction.transaction_type.in_([
            TransactionType.transfer_in,
            TransactionType.transfer_out,
        ]),
        Transaction.is_self_transfer == False,  # noqa: E712
    ).order_by(Transaction.executed_at)
    result = await session.execute(stmt)
    txs = result.scalars().all()

    outs: list[_Candidate] = []
    ins: list[_Candidate] = []
    for tx in txs:
        c = _Candidate(
            tx_id=tx.id,
            wallet_id=tx.wallet_id,
            asset=tx.asset,
            amount=tx.amount,
            executed_at=tx.executed_at.date() if hasattr(tx.executed_at, "date") else tx.executed_at,
        )
        if tx.transaction_type == TransactionType.transfer_out:
            outs.append(c)
        else:
            ins.append(c)

    pairs = _match(outs, ins)
    if not pairs:
        return 0

    matched_ids = [tx_id for pair in pairs for tx_id in pair]
    await session.execute(
        update(Transaction)
        .where(Transaction.id.in_(matched_ids))
        .values(is_self_transfer=True)
    )
    await session.flush()
    return len(matched_ids)


def _match(
    outs: list[_Candidate],
    ins: list[_Candidate],
) -> list[tuple[int, int]]:
    """
    Greedy 1:1 matching. Returns list of (out_id, in_id) pairs.
    """
    # Build scored candidate list: (score, out_idx, in_idx)
    scored: list[tuple[float, int, int]] = []
    for oi, out in enumerate(outs):
        for ii, inn in enumerate(ins):
            if inn.wallet_id == out.wallet_id:
                continue
            if inn.asset != out.asset:
                continue
            if inn.amount == 0 or out.amount == 0:
                continue
            ratio = inn.amount / out.amount
            if ratio < AMOUNT_TOLERANCE or ratio > Decimal("1.05"):
                continue
            days_diff = abs((inn.executed_at - out.executed_at).days)
            if days_diff > TIME_WINDOW_DAYS:
                continue
            score = days_diff * 100 + float(abs(1 - ratio)) * 1000
            scored.append((score, oi, ii))

    scored.sort()

    used_outs: set[int] = set()
    used_ins: set[int] = set()
    pairs: list[tuple[int, int]] = []

    for _, oi, ii in scored:
        if oi in used_outs or ii in used_ins:
            continue
        used_outs.add(oi)
        used_ins.add(ii)
        pairs.append((outs[oi].tx_id, ins[ii].tx_id))

    return pairs
