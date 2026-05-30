from decimal import Decimal
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Transaction, Wallet
from app.schemas.tax import GainReport, AssetGain, DARFReport, DARFObligation, IRPFReport, IRPFAsset, EarnIncomeEntry, IN1888Report, IN1888Entry, COAFAlert
from app.services import tax_engine
from app.services.tax_engine import TxRecord

router = APIRouter(prefix="/tax", tags=["tax"])


async def _load_tx_records(session: AsyncSession, year: int | None = None) -> list[TxRecord]:
    stmt = select(Transaction, Wallet).join(Wallet, Transaction.wallet_id == Wallet.id)
    if year:
        from sqlalchemy import func
        stmt = stmt.where(func.strftime("%Y", Transaction.executed_at) == str(year))
    result = await session.execute(stmt)
    records = []
    for tx, wallet in result.all():
        records.append(TxRecord(
            id=tx.id,
            wallet_id=tx.wallet_id,
            wallet_name=wallet.name,
            is_brazilian_exchange=wallet.is_brazilian_exchange,
            executed_at=tx.executed_at.date() if hasattr(tx.executed_at, 'date') else tx.executed_at,
            transaction_type=tx.transaction_type.value,
            asset=tx.asset,
            amount=tx.amount,
            total_brl=tx.total_brl,
            is_self_transfer=tx.is_self_transfer,
        ))
    return records


@router.get("/gains", response_model=GainReport)
async def gains(
    year: int = Query(...),
    month: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    records = await _load_tx_records(db)
    monthly = tax_engine.compute_gains(records)
    mk = tax_engine.MonthKey(year, month)
    month_data = monthly.get(mk, {})

    assets = []
    total_gain = Decimal(0)
    total_loss = Decimal(0)

    for asset, data in month_data.items():
        assets.append(AssetGain(
            asset=asset,
            buy_amount=data["buy_amount"],
            sell_amount=data["sell_amount"],
            avg_cost_brl=data["avg_cost_at_sale"],
            proceeds_brl=data["proceeds"],
            gain_brl=data["gain"] - data["loss"],
            is_taxable=data["gain"] > 0,
        ))
        total_gain += data["gain"]
        total_loss += data["loss"]

    net = total_gain - total_loss
    month_txs = [r for r in records if r.executed_at.year == year and r.executed_at.month == month]
    has_foreign = any(not r.is_brazilian_exchange for r in month_txs)
    is_taxable = net > 0 and (has_foreign or net > tax_engine.DARF_EXEMPT_BRL)
    reason = None
    if is_taxable:
        if has_foreign:
            reason = "Operações em exchanges estrangeiras: ganhos sempre tributáveis independente do valor"
        else:
            reason = f"Ganho líquido de R${net:,.2f} supera o limite de isenção de R$35.000"

    return GainReport(
        year=year, month=month, assets=assets,
        total_gain_brl=total_gain, total_loss_brl=total_loss, net_gain_brl=net,
        is_taxable=is_taxable, taxable_reason=reason,
    )


@router.get("/darf", response_model=DARFReport)
async def darf(year: int = Query(...), db: AsyncSession = Depends(get_db)):
    records = await _load_tx_records(db)
    obligations_raw = tax_engine.darf_obligations(records, year)

    obligations = [
        DARFObligation(
            year=o["year"], month=o["month"],
            darf_code=o["darf_code"],
            is_foreign=o["is_foreign"],
            net_gain_brl=o["net_gain_brl"],
            carryforward_applied_brl=o["carryforward_applied_brl"],
            exempt_threshold_brl=o["exempt_threshold_brl"],
            taxable_gain_brl=o["taxable_gain_brl"],
            tax_due_brl=o["tax_due_brl"],
            effective_rate=o["effective_rate"],
            due_date=o["due_date"],
        )
        for o in obligations_raw
    ]
    total = sum(o.tax_due_brl for o in obligations)
    return DARFReport(year=year, obligations=obligations, total_tax_due_brl=total)


@router.get("/irpf", response_model=IRPFReport)
async def irpf(year: int = Query(...), db: AsyncSession = Depends(get_db)):
    records = await _load_tx_records(db)
    snapshot = tax_engine.get_cost_basis_snapshot(records)

    assets = [
        IRPFAsset(
            asset=asset,
            quantity=cb["quantity"],
            avg_cost_brl=cb["total_cost"] / cb["quantity"] if cb["quantity"] > 0 else Decimal(0),
            total_cost_brl=cb["total_cost"],
            description=f"Criptomoeda {asset} — custo de aquisição em BRL",
        )
        for asset, cb in snapshot.items()
    ]

    obligations_raw = tax_engine.darf_obligations(records, year)
    taxable_total = sum(Decimal(str(o["taxable_gain_brl"])) for o in obligations_raw)

    monthly = tax_engine.compute_gains(records)
    exempt_total = Decimal(0)
    for mk, month_data in monthly.items():
        if mk.year != year:
            continue
        net = sum(d["gain"] - d["loss"] for d in month_data.values())
        if net > 0 and net <= tax_engine.DARF_EXEMPT_BRL:
            exempt_total += net

    earn_raw = tax_engine.earn_income_by_year(records, year)
    earn_entries = [
        EarnIncomeEntry(asset=e["asset"], total_brl=e["total_brl"], transaction_count=e["transaction_count"])
        for e in earn_raw
    ]

    return IRPFReport(
        year=year, assets=assets,
        total_cost_brl=sum(a.total_cost_brl for a in assets),
        exempt_gains_brl=exempt_total,
        taxable_gains_brl=taxable_total,
        earn_income=earn_entries,
        earn_income_total_brl=sum(e.total_brl for e in earn_entries),
    )


@router.get("/1888", response_model=IN1888Report)
async def in1888(year: int = Query(...), month: int | None = Query(None), db: AsyncSession = Depends(get_db)):
    records = await _load_tx_records(db)
    entries_raw = tax_engine.in1888_report(records, year)
    if month:
        entries_raw = [e for e in entries_raw if e["month"] == month]

    entries = [
        IN1888Entry(
            year=e["year"], month=e["month"],
            wallet_name=e["wallet_name"], wallet_type="exchange",
            transaction_count=e["transaction_count"],
            total_volume_brl=e["total_volume_brl"],
            must_report=e["must_report"],
        )
        for e in entries_raw
    ]
    must_report_months = sorted({e.month for e in entries if e.must_report})
    return IN1888Report(year=year, entries=entries, months_requiring_report=must_report_months)


@router.get("/coaf", response_model=list[COAFAlert])
async def coaf(year: int = Query(...), db: AsyncSession = Depends(get_db)):
    records = await _load_tx_records(db, year=year)
    alerts_raw = tax_engine.coaf_alerts(records)
    return [
        COAFAlert(
            alert_type=a["alert_type"],
            transaction_ids=a["transaction_ids"],
            executed_at=a["executed_at"],
            asset=a["asset"],
            amount=a["amount"],
            total_brl=a["total_brl"],
            wallet_name=a["wallet_name"],
            reason=a["reason"],
        )
        for a in alerts_raw
    ]
