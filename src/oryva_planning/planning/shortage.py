"""Shortage detection, prioritization, and evidence traceability (full-scale optimized)."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from oryva_planning.config import PlanningConfig, PlanningWeek
from oryva_planning.planning.root_cause import RootCauseContext, classify_root_cause
from oryva_planning.schema.enums import (
    EntityStatus,
    EvidenceContribution,
    POStatus,
    ShortageSeverity,
    ShortageStatus,
)
from oryva_planning.schema.ids import make_evidence_id, make_shortage_id


def detect_shortages_and_evidence(
    config: PlanningConfig,
    skus: pd.DataFrame,
    suppliers: pd.DataFrame,
    sku_suppliers: pd.DataFrame,
    demand_df: pd.DataFrame,
    inventory_df: pd.DataFrame,
    capacity_df: pd.DataFrame,
    lead_times_df: pd.DataFrame,
    po_df: pd.DataFrame,
    production_df: pd.DataFrame,
    balance_df: pd.DataFrame,
    weeks: list[PlanningWeek],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    eff_from = config.reference_date.isoformat()
    year = config.planning_year
    ref_date = config.reference_date

    onset_mask = (balance_df["closing_stock"] < 0) & (balance_df["opening_stock"] >= 0)
    deficit_df = (
        balance_df.loc[onset_mask, ["balance_id", "sku_id", "location_id", "week_id", "closing_stock"]]
        .sort_values("balance_id", kind="mergesort")
        .reset_index(drop=True)
    )

    if deficit_df.empty:
        empty_short = pd.DataFrame(
            columns=[
                "shortage_id", "balance_id", "sku_id", "location_id", "week_id",
                "week_start_date", "shortage_qty", "revenue_at_risk", "lead_time_days_used",
                "required_order_by_date", "root_cause", "severity", "priority_score",
                "priority_rank", "lifecycle_state", "effective_from", "effective_to",
            ]
        )
        empty_ev = pd.DataFrame(
            columns=[
                "evidence_id", "shortage_id", "source_table", "source_record_id",
                "contribution_type", "metric_value", "explanation",
                "effective_from", "effective_to", "lifecycle_state",
            ]
        )
        return empty_short, empty_ev

    # Vectorized merge of demand & inventory onto onset rows (fast even at 7.8M demand rows)
    enriched = deficit_df.merge(
        demand_df[
            ["sku_id", "location_id", "week_id", "demand_id", "forecast_qty", "is_spike_week", "priority_weight"]
        ],
        on=["sku_id", "location_id", "week_id"],
        how="left",
    ).merge(
        inventory_df[["sku_id", "location_id", "inventory_id", "available_qty", "safety_stock_qty"]],
        on=["sku_id", "location_id"],
        how="left",
    )

    wk_idx_map = {w.week_id: w.week_index for w in weeks}
    wk_start_map = {w.week_id: w.week_start_date for w in weeks}
    sku_price = dict(zip(skus["sku_id"], skus["unit_price"]))
    sku_critical = dict(zip(skus["sku_id"], skus["is_critical"]))

    lt_sorted = lead_times_df.sort_values(
        ["sku_id", "location_id", "total_lead_time_days", "lead_time_id"], kind="mergesort"
    )
    min_lt_df = lt_sorted.drop_duplicates(subset=["sku_id", "location_id"], keep="first")
    min_lt_map: dict[tuple[str, str], tuple[int, str]] = {
        (r.sku_id, r.location_id): (int(r.total_lead_time_days), r.lead_time_id)
        for r in min_lt_df.itertuples(index=False)
    }

    prim_ss = sku_suppliers.sort_values(
        ["sku_id", "is_primary", "supplier_id"], ascending=[True, False, True], kind="mergesort"
    ).drop_duplicates(subset=["sku_id"], keep="first")
    primary_sup_map = dict(zip(prim_ss["sku_id"], prim_ss["supplier_id"]))
    sup_constrained_map = dict(zip(suppliers["supplier_id"], suppliers["is_constrained"]))

    cap_map: dict[tuple[str, str], tuple[str, int, int]] = {
        (r.supplier_id, r.week_id): (r.capacity_id, int(r.available_capacity), int(r.max_weekly_capacity))
        for r in capacity_df.itertuples(index=False)
    }

    delayed_pos = po_df[
        (po_df["transport_delay_days"] > 0) & (po_df["current_status"] != POStatus.CANCELLED.value)
    ]
    delayed_by_pair: dict[tuple[str, str], list[tuple[str, date, str, int]]] = {}
    for r in delayed_pos.itertuples(index=False):
        delayed_by_pair.setdefault((r.sku_id, r.location_id), []).append(
            (r.po_id, date.fromisoformat(str(r.promised_delivery_date)), r.arrival_week_id, int(r.transport_delay_days))
        )

    prod_constrained: dict[tuple[str, str, str], tuple[str, int, int]] = {}
    if not production_df.empty:
        c_prod = production_df[production_df["achievable_qty"] < production_df["planned_qty"]]
        for r in c_prod.itertuples(index=False):
            prod_constrained[(r.sku_id, r.location_id, r.week_id)] = (
                r.production_id, int(r.planned_qty), int(r.achievable_qty)
            )

    shortage_rows: list[dict[str, object]] = []
    evidence_rows: list[dict[str, object]] = []
    ev_seq = 0

    def _add_ev(shortage_id: str, src_table: str, src_id: str, contrib: EvidenceContribution, metric: float, expl: str) -> None:
        nonlocal ev_seq
        ev_seq += 1
        evidence_rows.append(
            {
                "evidence_id": make_evidence_id(year, ev_seq),
                "shortage_id": shortage_id,
                "source_table": src_table,
                "source_record_id": src_id,
                "contribution_type": contrib.value,
                "metric_value": round(float(metric), 4),
                "explanation": expl,
                "effective_from": eff_from,
                "effective_to": None,
                "lifecycle_state": EntityStatus.ACTIVE.value,
            }
        )

    raw_scores: list[float] = []
    n_weeks = max(1, len(weeks))

    for idx, row in enumerate(enriched.itertuples(index=False), start=1):
        shortage_id = make_shortage_id(year, idx)
        sku_id, loc_id, wk_id = row.sku_id, row.location_id, row.week_id
        wk_idx = wk_idx_map[wk_id]
        wk_start = wk_start_map[wk_id]

        shortage_qty = int(abs(row.closing_stock))
        rev_at_risk = round(shortage_qty * float(sku_price[sku_id]), 4)

        lt_info = min_lt_map.get((sku_id, loc_id))
        lt_days = lt_info[0] if lt_info is not None else 0
        lt_id = lt_info[1] if lt_info is not None else None
        order_by_date = wk_start - timedelta(days=lt_days)

        is_spike = bool(row.is_spike_week)
        prio_wt = float(row.priority_weight)
        inv_avail = int(row.available_qty)
        inv_ss = int(row.safety_stock_qty)
        f_qty = int(row.forecast_qty)

        _add_ev(
            shortage_id, "forecast_demand", str(row.demand_id),
            EvidenceContribution.DEMAND_DRIVER, float(f_qty),
            f"Weekly demand of {f_qty} units" + (" (demand spike week)" if is_spike else ""),
        )
        _add_ev(
            shortage_id, "inventory", str(row.inventory_id),
            EvidenceContribution.INVENTORY_BASELINE, float(inv_avail),
            f"Opening available stock {inv_avail} vs safety stock {inv_ss}",
        )

        matching_delay = None
        wk_end = wk_start + timedelta(days=6)
        for po_id, prom_dt, arr_wk, d_days in delayed_by_pair.get((sku_id, loc_id), []):
            if prom_dt <= wk_end and wk_idx_map.get(arr_wk, 999) > wk_idx:
                matching_delay = (po_id, d_days, arr_wk)
                break

        prod_issue = prod_constrained.get((sku_id, loc_id, wk_id))
        prim_sup = primary_sup_map.get(sku_id)
        cap_info = cap_map.get((prim_sup, wk_id)) if prim_sup else None
        cap_tight = False
        if cap_info is not None:
            _, avail_c, max_c = cap_info
            util = 1.0 - (avail_c / max(1, max_c))
            cap_tight = bool(util >= 0.85 or sup_constrained_map.get(prim_sup, False))

        root_cause, extra_evs = classify_root_cause(
            RootCauseContext(
                week_id=wk_id,
                week_idx=wk_idx,
                ref_date=ref_date,
                order_by_date=order_by_date,
                is_spike=is_spike,
                inv_avail=inv_avail,
                inv_safety_stock=inv_ss,
                lt_days=lt_days,
                lt_id=lt_id,
                delayed_po=matching_delay,
                prod_issue=prod_issue,
                cap_tight=cap_tight,
                cap_info=cap_info,
            )
        )
        for ev in extra_evs:
            _add_ev(shortage_id, ev.source_table, ev.source_record_id, ev.contribution_type, ev.metric_value, ev.explanation)

        urgency = max(0.0, 1.0 - wk_idx / n_weeks)
        crit_bonus = 20.0 if sku_critical[sku_id] else 0.0
        raw_p = np.log1p(rev_at_risk) * 4.5 + prio_wt * 10.0 + urgency * 25.0 + crit_bonus
        raw_scores.append(float(raw_p))

        shortage_rows.append(
            {
                "shortage_id": shortage_id,
                "balance_id": row.balance_id,
                "sku_id": sku_id,
                "location_id": loc_id,
                "week_id": wk_id,
                "week_start_date": wk_start.isoformat(),
                "shortage_qty": shortage_qty,
                "revenue_at_risk": rev_at_risk,
                "lead_time_days_used": lt_days,
                "required_order_by_date": order_by_date.isoformat(),
                "root_cause": root_cause.value,
                "severity": ShortageSeverity.MEDIUM.value,
                "priority_score": 0.0,
                "priority_rank": 1,
                "lifecycle_state": ShortageStatus.OPEN.value,
                "effective_from": eff_from,
                "effective_to": None,
            }
        )

    short_df = pd.DataFrame(shortage_rows)
    raw_arr = np.array(raw_scores, dtype=np.float64)
    r_min, r_max = float(raw_arr.min()), float(raw_arr.max())
    norm_scores = 15.0 + 85.0 * (raw_arr - r_min) / (r_max - r_min) if r_max > r_min else np.full_like(raw_arr, 65.0)
    short_df["priority_score"] = np.round(norm_scores, 4)

    def _to_sev(s: float) -> str:
        if s >= 80.0:
            return ShortageSeverity.CRITICAL.value
        if s >= 60.0:
            return ShortageSeverity.HIGH.value
        if s >= 40.0:
            return ShortageSeverity.MEDIUM.value
        return ShortageSeverity.LOW.value

    short_df["severity"] = [_to_sev(s) for s in short_df["priority_score"]]

    rank_order = short_df.sort_values(
        ["priority_score", "shortage_id"], ascending=[False, True], kind="mergesort"
    ).index
    ranks = np.empty(len(short_df), dtype=np.int64)
    ranks[rank_order] = np.arange(1, len(short_df) + 1, dtype=np.int64)
    short_df["priority_rank"] = ranks

    short_df = short_df.sort_values("shortage_id", kind="mergesort").reset_index(drop=True)
    ev_df = pd.DataFrame(evidence_rows).sort_values("evidence_id", kind="mergesort").reset_index(drop=True)
    return short_df, ev_df
