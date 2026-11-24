"""Vectorized week-by-week Projected Available Balance (PAB) engine."""

from __future__ import annotations

import numpy as np
import pandas as pd

from oryva_planning.config import PlanningConfig, PlanningWeek
from oryva_planning.schema.enums import EntityStatus, POStatus, ProductionStatus


def compute_projected_balances(
    config: PlanningConfig,
    skus: pd.DataFrame,
    locations: pd.DataFrame,
    demand_df: pd.DataFrame,
    inventory_df: pd.DataFrame,
    po_df: pd.DataFrame,
    production_df: pd.DataFrame,
    weeks: list[PlanningWeek],
) -> pd.DataFrame:
    eff_from = config.reference_date.isoformat()

    sku_ids = skus["sku_id"].sort_values(kind="mergesort").to_numpy()
    loc_ids = locations["location_id"].sort_values(kind="mergesort").to_numpy()
    wk_ids = np.array([w.week_id for w in weeks], dtype=object)
    wk_starts = np.array([w.week_start_date.isoformat() for w in weeks], dtype=object)

    n_sku, n_loc, n_wk = len(sku_ids), len(loc_ids), len(wk_ids)
    n_pairs = n_sku * n_loc

    sku_to_idx = {s: i for i, s in enumerate(sku_ids)}
    loc_to_idx = {loc: i for i, loc in enumerate(loc_ids)}
    wk_to_idx = {w: i for i, w in enumerate(wk_ids)}

    demand_mat = np.zeros((n_pairs, n_wk), dtype=np.int64)
    d_pair = (
        demand_df["sku_id"].map(sku_to_idx).to_numpy(dtype=np.int64) * n_loc
        + demand_df["location_id"].map(loc_to_idx).to_numpy(dtype=np.int64)
    )
    d_wk = demand_df["week_id"].map(wk_to_idx).to_numpy(dtype=np.int64)
    np.add.at(demand_mat, (d_pair, d_wk), demand_df["forecast_qty"].to_numpy(dtype=np.int64))

    open_0 = np.zeros(n_pairs, dtype=np.int64)
    safety_vec = np.zeros(n_pairs, dtype=np.int64)
    inv_pair = (
        inventory_df["sku_id"].map(sku_to_idx).to_numpy(dtype=np.int64) * n_loc
        + inventory_df["location_id"].map(loc_to_idx).to_numpy(dtype=np.int64)
    )
    open_0[inv_pair] = inventory_df["available_qty"].to_numpy(dtype=np.int64)
    safety_vec[inv_pair] = inventory_df["safety_stock_qty"].to_numpy(dtype=np.int64)

    inbound_mat = np.zeros((n_pairs, n_wk), dtype=np.int64)
    active_pos = po_df[po_df["current_status"] != POStatus.CANCELLED.value]
    if not active_pos.empty:
        p_pair = (
            active_pos["sku_id"].map(sku_to_idx).to_numpy(dtype=np.int64) * n_loc
            + active_pos["location_id"].map(loc_to_idx).to_numpy(dtype=np.int64)
        )
        p_wk = active_pos["arrival_week_id"].map(wk_to_idx).to_numpy(dtype=np.int64)
        np.add.at(inbound_mat, (p_pair, p_wk), active_pos["order_qty"].to_numpy(dtype=np.int64))

    prod_mat = np.zeros((n_pairs, n_wk), dtype=np.int64)
    if not production_df.empty:
        active_prod = production_df[production_df["lifecycle_state"] != ProductionStatus.CANCELLED.value]
        if not active_prod.empty:
            pr_pair = (
                active_prod["sku_id"].map(sku_to_idx).to_numpy(dtype=np.int64) * n_loc
                + active_prod["location_id"].map(loc_to_idx).to_numpy(dtype=np.int64)
            )
            pr_wk = active_prod["week_id"].map(wk_to_idx).to_numpy(dtype=np.int64)
            np.add.at(prod_mat, (pr_pair, pr_wk), active_prod["achievable_qty"].to_numpy(dtype=np.int64))

    net_mat = inbound_mat + prod_mat - demand_mat
    closing_mat = open_0[:, None] + np.cumsum(net_mat, axis=1)
    opening_mat = np.empty_like(closing_mat)
    opening_mat[:, 0] = open_0
    if n_wk > 1:
        opening_mat[:, 1:] = closing_mat[:, :-1]

    safety_mat = np.broadcast_to(safety_vec[:, None], (n_pairs, n_wk))
    below_ss = closing_mat < safety_mat

    total_rows = n_pairs * n_wk
    df = pd.DataFrame(
        {
            "sku_id": np.repeat(sku_ids, n_loc * n_wk),
            "location_id": np.tile(np.repeat(loc_ids, n_wk), n_sku),
            "week_id": np.tile(wk_ids, n_pairs),
            "week_start_date": np.tile(wk_starts, n_pairs),
            "opening_stock": opening_mat.reshape(total_rows),
            "inbound_qty": inbound_mat.reshape(total_rows),
            "production_qty": prod_mat.reshape(total_rows),
            "demand_qty": demand_mat.reshape(total_rows),
            "closing_stock": closing_mat.reshape(total_rows),
            "safety_stock_qty": safety_mat.reshape(total_rows),
            "below_safety_stock": below_ss.reshape(total_rows),
            "effective_from": eff_from,
            "effective_to": None,
            "lifecycle_state": EntityStatus.ACTIVE.value,
        }
    )
    df.insert(0, "balance_id", "BAL-" + df["sku_id"] + "-" + df["location_id"] + "-" + df["week_id"])
    return df.sort_values("balance_id", kind="mergesort").reset_index(drop=True)
