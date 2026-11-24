"""Explainable root-cause classification and evidence builder for shortages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from oryva_planning.schema.enums import EvidenceContribution, ShortageRootCause


@dataclass(frozen=True)
class RootCauseContext:
    week_id: str
    week_idx: int
    ref_date: date
    order_by_date: date
    is_spike: bool
    inv_avail: int
    inv_safety_stock: int
    lt_days: int
    lt_id: str | None
    delayed_po: tuple[str, int, str] | None  # (po_id, delay_days, arrival_week_id)
    prod_issue: tuple[str, int, int] | None  # (production_id, planned_qty, achievable_qty)
    cap_tight: bool
    cap_info: tuple[str, int, int] | None  # (capacity_id, available_capacity, max_weekly_capacity)


@dataclass(frozen=True)
class EvidenceItem:
    source_table: str
    source_record_id: str
    contribution_type: EvidenceContribution
    metric_value: float
    explanation: str


def classify_root_cause(ctx: RootCauseContext) -> tuple[ShortageRootCause, list[EvidenceItem]]:
    """Deterministically assign primary root cause and causal evidence rows."""
    extra_evidence: list[EvidenceItem] = []

    if ctx.is_spike:
        return ShortageRootCause.DEMAND_SPIKE, extra_evidence

    if ctx.delayed_po is not None:
        po_id, d_days, arr_wk = ctx.delayed_po
        extra_evidence.append(
            EvidenceItem(
                source_table="purchase_orders",
                source_record_id=po_id,
                contribution_type=EvidenceContribution.INBOUND_DELAY,
                metric_value=float(d_days),
                explanation=f"PO delayed by {d_days} days; arrival slipped to {arr_wk}",
            )
        )
        return ShortageRootCause.LATE_INBOUND, extra_evidence

    if ctx.prod_issue is not None:
        prod_id, planned, achievable = ctx.prod_issue
        extra_evidence.append(
            EvidenceItem(
                source_table="production_plans",
                source_record_id=prod_id,
                contribution_type=EvidenceContribution.PRODUCTION_SHORTFALL,
                metric_value=float(planned - achievable),
                explanation=f"Production constrained: achievable {achievable} < planned {planned}",
            )
        )
        return ShortageRootCause.PRODUCTION_CONSTRAINT, extra_evidence

    if ctx.order_by_date < ctx.ref_date and ctx.lt_id is not None:
        extra_evidence.append(
            EvidenceItem(
                source_table="lead_times",
                source_record_id=ctx.lt_id,
                contribution_type=EvidenceContribution.LEAD_TIME_CONSTRAINT,
                metric_value=float(ctx.lt_days),
                explanation=(
                    f"Minimum lead time ({ctx.lt_days}d) requires order by "
                    f"{ctx.order_by_date.isoformat()} before planning start"
                ),
            )
        )
        return ShortageRootCause.LEAD_TIME_GAP, extra_evidence

    if ctx.cap_tight and ctx.cap_info is not None:
        cap_id, avail_c, max_c = ctx.cap_info
        extra_evidence.append(
            EvidenceItem(
                source_table="supplier_capacity",
                source_record_id=cap_id,
                contribution_type=EvidenceContribution.CAPACITY_BOTTLENECK,
                metric_value=float(avail_c),
                explanation=(
                    f"Primary supplier constrained with {avail_c}/{max_c} units remaining in {ctx.week_id}"
                ),
            )
        )
        return ShortageRootCause.SUPPLIER_CAPACITY_CAP, extra_evidence

    if ctx.week_idx <= 4 and ctx.inv_avail < ctx.inv_safety_stock:
        return ShortageRootCause.LOW_OPENING_INVENTORY, extra_evidence

    if ctx.lt_id is not None:
        extra_evidence.append(
            EvidenceItem(
                source_table="lead_times",
                source_record_id=ctx.lt_id,
                contribution_type=EvidenceContribution.LEAD_TIME_CONSTRAINT,
                metric_value=float(ctx.lt_days),
                explanation=f"Replenishment lead time of {ctx.lt_days} days governs recovery window",
            )
        )
    return ShortageRootCause.COMPOUND_DEFICIT, extra_evidence
