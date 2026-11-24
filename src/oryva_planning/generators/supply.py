"""LeadTime, PurchaseOrder, PurchaseOrderEvent, and SupplierCapacity generators."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd

from oryva_planning.config import PlanningConfig, PlanningWeek
from oryva_planning.schema.enums import EntityStatus, POStatus, ReliabilityTier
from oryva_planning.schema.ids import make_capacity_id, make_po_event_id, make_po_id


def generate_lead_times(
    config: PlanningConfig,
    rng: np.random.Generator,
    skus: pd.DataFrame,
    locations: pd.DataFrame,
    suppliers: pd.DataFrame,
    sku_suppliers: pd.DataFrame,
) -> pd.DataFrame:
    eff_from = config.reference_date.isoformat()

    loc_meta = locations[["location_id", "region"]].rename(columns={"region": "loc_region"})
    sup_meta = suppliers[["supplier_id", "region", "reliability_tier"]].rename(
        columns={"region": "sup_region"}
    )
    ss = sku_suppliers[["sku_id", "supplier_id", "min_order_qty"]].merge(
        sup_meta, on="supplier_id", how="left"
    )
    ss["_key"] = 1
    loc_meta = loc_meta.copy()
    loc_meta["_key"] = 1
    grid = ss.merge(loc_meta, on="_key").drop(columns=["_key"])
    n = len(grid)

    gamma_total = rng.gamma(
        shape=config.supplier.lead_time_gamma_shape,
        scale=config.supplier.lead_time_gamma_scale,
        size=n,
    )
    unreliable_boost = np.where(
        grid["reliability_tier"].to_numpy() == ReliabilityTier.LOW.value, 1.45, 1.0
    )
    cross_region_days = np.where(
        grid["sup_region"].to_numpy() != grid["loc_region"].to_numpy(), 3, 1
    )

    mfg_days = np.maximum(2, np.rint(gamma_total * 0.55 * unreliable_boost)).astype(np.int64)
    transit_days = np.maximum(1, np.rint(gamma_total * 0.35) + cross_region_days).astype(np.int64)
    customs_days = rng.integers(0, 4, size=n, dtype=np.int64)
    total_days = mfg_days + transit_days + customs_days

    df = pd.DataFrame(
        {
            "lead_time_id": (
                "LT-" + grid["sku_id"] + "-" + grid["supplier_id"] + "-" + grid["location_id"]
            ),
            "sku_id": grid["sku_id"],
            "supplier_id": grid["supplier_id"],
            "location_id": grid["location_id"],
            "manufacturing_days": mfg_days,
            "transit_days": transit_days,
            "customs_buffer_days": customs_days,
            "total_lead_time_days": total_days,
            "min_order_qty": grid["min_order_qty"].astype(np.int64),
            "effective_from": eff_from,
            "effective_to": None,
            "lifecycle_state": EntityStatus.ACTIVE.value,
        }
    )
    return df.sort_values("lead_time_id", kind="mergesort").reset_index(drop=True)


def _date_to_week_id(target_date: date, weeks: list[PlanningWeek]) -> str:
    first = weeks[0].week_start_date
    delta_weeks = (target_date - first).days // 7
    clamped = max(0, min(len(weeks) - 1, delta_weeks))
    return weeks[clamped].week_id


def _build_po_events(
    po_id: str,
    order_date: date,
    promised_date: date,
    actual_date: date | None,
    delay_days: int,
    is_cancelled: bool,
    cutoff_date: date,
    eff_from: str,
    event_counter_start: int,
    year: int,
) -> tuple[list[dict[str, object]], str, int]:
    events: list[dict[str, object]] = []
    seq = 0
    ev_num = event_counter_start
    last_ts: datetime | None = None

    def _add(
        from_s: POStatus | None,
        to_s: POStatus,
        dt: date,
        hour: int,
        actor: str,
        reason: str,
    ) -> None:
        nonlocal seq, ev_num, last_ts
        seq += 1
        ev_num += 1
        cand_ts = datetime(dt.year, dt.month, dt.day, hour, 0, 0, tzinfo=timezone.utc)
        if last_ts is not None and cand_ts <= last_ts:
            cand_ts = last_ts + timedelta(hours=2)
        last_ts = cand_ts
        ts = cand_ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        events.append(
            {
                "event_id": make_po_event_id(year, ev_num),
                "po_id": po_id,
                "sequence_num": seq,
                "from_status": from_s.value if from_s is not None else None,
                "to_status": to_s.value,
                "event_ts": ts,
                "actor": actor,
                "reason": reason,
                "effective_from": eff_from,
                "effective_to": None,
                "lifecycle_state": EntityStatus.ACTIVE.value,
            }
        )

    _add(None, POStatus.CREATED, order_date, 9, "PLANNER", "Replenishment order created")

    if is_cancelled:
        _add(
            POStatus.CREATED,
            POStatus.CANCELLED,
            order_date + timedelta(days=1),
            11,
            "OPS_MANAGER",
            "Order cancelled prior to supplier confirmation",
        )
        return events, POStatus.CANCELLED.value, ev_num

    confirm_dt = order_date + timedelta(days=1)
    _add(POStatus.CREATED, POStatus.CONFIRMED, confirm_dt, 14, "SUPPLIER", "Supplier confirmed PO")

    ship_dt = max(confirm_dt, promised_date - timedelta(days=3))
    if ship_dt <= cutoff_date + timedelta(days=180):
        _add(POStatus.CONFIRMED, POStatus.IN_TRANSIT, ship_dt, 10, "CARRIER", "Shipment dispatched")
        if delay_days > 0:
            delay_dt = max(ship_dt, promised_date)
            _add(
                POStatus.IN_TRANSIT,
                POStatus.DELAYED,
                delay_dt,
                16,
                "CARRIER",
                f"Transport delay of {delay_days} days reported",
            )
            if actual_date is not None and actual_date <= cutoff_date + timedelta(days=120):
                _add(
                    POStatus.DELAYED,
                    POStatus.RECEIVED,
                    actual_date,
                    17,
                    "WAREHOUSE",
                    "Delayed shipment received at warehouse",
                )
        else:
            if actual_date is not None and actual_date <= cutoff_date + timedelta(days=120):
                _add(
                    POStatus.IN_TRANSIT,
                    POStatus.RECEIVED,
                    actual_date,
                    15,
                    "WAREHOUSE",
                    "On-time shipment received at warehouse",
                )

    return events, str(events[-1]["to_status"]), ev_num


def generate_purchase_orders_and_capacity(
    config: PlanningConfig,
    rng_cap: np.random.Generator,
    rng_po: np.random.Generator,
    skus: pd.DataFrame,
    locations: pd.DataFrame,
    suppliers: pd.DataFrame,
    sku_suppliers: pd.DataFrame,
    lead_times: pd.DataFrame,
    demand_df: pd.DataFrame,
    weeks: list[PlanningWeek],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    eff_from = config.reference_date.isoformat()
    n_pos = config.scale.num_purchase_orders
    n_wk = len(weeks)
    year = config.planning_year

    pair_demand = (
        demand_df.groupby(["sku_id", "location_id"], sort=True)["forecast_qty"]
        .agg(["sum", "mean"])
        .reset_index()
    )
    buy_skus = set(skus[skus["sourcing_type"] != "MAKE"]["sku_id"])
    pair_demand_buy = pair_demand[pair_demand["sku_id"].isin(buy_skus)].reset_index(drop=True)
    if pair_demand_buy.empty:
        pair_demand_buy = pair_demand

    pair_weights = np.clip(pair_demand_buy["sum"].to_numpy(dtype=np.float64), 1.0, None)
    pair_probs = pair_weights / pair_weights.sum()
    chosen_pair_idx = rng_po.choice(len(pair_demand_buy), size=n_pos, replace=True, p=pair_probs)

    min_w52 = max(
        (config.anomalies.double_counted_inbound + config.anomalies.supplier_capacity_exceeded) * 2 + 6,
        16,
    )
    min_w52 = min(min_w52, max(1, n_pos // 6))
    chosen_week_idx = rng_po.integers(0, n_wk, size=n_pos)
    chosen_week_idx[:min_w52] = n_wk - 1
    rng_po.shuffle(chosen_week_idx)

    sku_uom_map = dict(zip(skus["sku_id"], skus["base_uom"]))
    sup_rel_map = dict(zip(suppliers["supplier_id"], suppliers["reliability_tier"]))
    sup_constrained_map = dict(zip(suppliers["supplier_id"], suppliers["is_constrained"]))

    sku_sup_options: dict[str, list[tuple[str, float, int, int, bool]]] = {}
    for r in sku_suppliers.itertuples(index=False):
        sku_sup_options.setdefault(r.sku_id, []).append(
            (r.supplier_id, float(r.unit_purchase_cost), int(r.min_order_qty), int(r.order_multiple), bool(r.is_primary))
        )

    lt_map: dict[tuple[str, str, str], int] = {
        (r.sku_id, r.supplier_id, r.location_id): int(r.total_lead_time_days)
        for r in lead_times.itertuples(index=False)
    }

    cancel_draws = rng_po.random(size=n_pos)
    delay_uniform = rng_po.random(size=n_pos)
    delay_lognorm = np.maximum(
        1,
        np.rint(
            rng_po.lognormal(
                mean=config.supplier.transport_delay_lognorm_mean,
                sigma=config.supplier.transport_delay_lognorm_sigma,
                size=n_pos,
            )
        ),
    ).astype(np.int64)
    cover_mult = rng_po.uniform(2.5, 6.5, size=n_pos)
    sup_pick_u = rng_po.random(size=n_pos)

    pair_skus = pair_demand_buy["sku_id"].to_numpy()
    pair_locs = pair_demand_buy["location_id"].to_numpy()
    pair_means = pair_demand_buy["mean"].to_numpy(dtype=np.float64)
    pair_po_counts = np.bincount(chosen_pair_idx, minlength=len(pair_demand_buy))

    po_rows: list[dict[str, object]] = []
    event_rows: list[dict[str, object]] = []
    ev_counter = 0
    cutoff_date = weeks[0].week_start_date

    for i in range(n_pos):
        p_idx = int(chosen_pair_idx[i])
        sku_id = str(pair_skus[p_idx])
        loc_id = str(pair_locs[p_idx])
        wk_idx = int(chosen_week_idx[i])
        target_week = weeks[wk_idx]

        opts = sku_sup_options[sku_id]
        primary_opts = [o for o in opts if o[4]]
        if primary_opts and sup_pick_u[i] < 0.75:
            sup_id, unit_cost, moq, mult, _ = primary_opts[0]
        else:
            sup_id, unit_cost, moq, mult, _ = opts[int(sup_pick_u[i] * len(opts)) % len(opts)]

        lt_days = lt_map.get((sku_id, sup_id, loc_id), 14)
        promised_date = target_week.week_start_date + timedelta(days=int(i % 5))
        order_date = promised_date - timedelta(days=lt_days)

        if wk_idx == n_wk - 1:
            is_cancelled = False
            delay_days = 0
        else:
            is_cancelled = bool(cancel_draws[i] < 0.03)
            base_delay_prob = config.supplier.transport_delay_probability
            if sup_rel_map.get(sup_id) == ReliabilityTier.LOW.value:
                base_delay_prob = min(0.45, base_delay_prob * 2.2)
            delay_days = int(delay_lognorm[i]) if (not is_cancelled and delay_uniform[i] < base_delay_prob) else 0

        if is_cancelled:
            actual_date = None
            arrival_week_id = target_week.week_id
        else:
            actual_date = promised_date + timedelta(days=delay_days)
            arrival_week_id = _date_to_week_id(actual_date, weeks)

        n_pair_pos = max(1, int(pair_po_counts[p_idx]))
        ideal_qty = (pair_means[p_idx] * n_wk * 0.94) / n_pair_pos
        raw_qty = ideal_qty * (cover_mult[i] / 4.5)
        if sup_constrained_map.get(sup_id, False):
            raw_qty *= 0.80
        qty = max(moq, int(round(raw_qty / mult) * mult))
        qty = max(1, qty)
        total_cost = round(qty * unit_cost, 4)

        po_id = make_po_id(year, i + 1)
        evs, current_status, ev_counter = _build_po_events(
            po_id=po_id,
            order_date=order_date,
            promised_date=promised_date,
            actual_date=actual_date,
            delay_days=delay_days,
            is_cancelled=is_cancelled,
            cutoff_date=cutoff_date,
            eff_from=eff_from,
            event_counter_start=ev_counter,
            year=year,
        )
        event_rows.extend(evs)

        po_rows.append(
            {
                "po_id": po_id,
                "sku_id": sku_id,
                "supplier_id": sup_id,
                "location_id": loc_id,
                "order_date": order_date.isoformat(),
                "promised_delivery_date": promised_date.isoformat(),
                "actual_delivery_date": actual_date.isoformat() if actual_date is not None else None,
                "arrival_week_id": arrival_week_id,
                "order_qty": qty,
                "uom": sku_uom_map[sku_id],
                "unit_cost": round(unit_cost, 4),
                "total_cost": total_cost,
                "transport_delay_days": delay_days,
                "current_status": current_status,
                "effective_from": eff_from,
                "effective_to": None,
            }
        )

    po_df = pd.DataFrame(po_rows).sort_values("po_id", kind="mergesort").reset_index(drop=True)
    events_df = pd.DataFrame(event_rows).sort_values("event_id", kind="mergesort").reset_index(drop=True)

    active_pos = po_df[po_df["current_status"] != POStatus.CANCELLED.value]
    committed = (
        active_pos.groupby(["supplier_id", "arrival_week_id"], sort=True)["order_qty"]
        .sum()
        .to_dict()
    )

    cap_rows: list[dict[str, object]] = []
    for s_row in suppliers.itertuples(index=False):
        sup_id = s_row.supplier_id
        is_constrained = bool(s_row.is_constrained)
        base_floor = int(rng_cap.integers(250, 800)) if is_constrained else int(rng_cap.integers(800, 2500))
        for wk in weeks:
            comm_qty = int(committed.get((sup_id, wk.week_id), 0))
            headroom_ratio = float(rng_cap.uniform(0.02, 0.15)) if is_constrained else float(rng_cap.uniform(0.35, 1.10))
            max_cap = max(base_floor, int(np.ceil(comm_qty * (1.0 + headroom_ratio))), comm_qty)
            avail_cap = max_cap - comm_qty
            cap_rows.append(
                {
                    "capacity_id": make_capacity_id(sup_id, wk.week_id),
                    "supplier_id": sup_id,
                    "week_id": wk.week_id,
                    "week_start_date": wk.week_start_date.isoformat(),
                    "max_weekly_capacity": max_cap,
                    "committed_qty": comm_qty,
                    "available_capacity": avail_cap,
                    "effective_from": eff_from,
                    "effective_to": None,
                    "lifecycle_state": EntityStatus.ACTIVE.value,
                }
            )

    cap_df = pd.DataFrame(cap_rows).sort_values("capacity_id", kind="mergesort").reset_index(drop=True)
    return po_df, events_df, cap_df
