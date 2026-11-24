"""Opening Inventory snapshot generator (derived available_qty = on_hand - reserved)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from oryva_planning.config import PlanningConfig, PlanningWeek
from oryva_planning.schema.enums import EntityStatus


def generate_inventory(
    config: PlanningConfig,
    rng: np.random.Generator,
    skus: pd.DataFrame,
    locations: pd.DataFrame,
    demand_df: pd.DataFrame,
    weeks: list[PlanningWeek],
) -> pd.DataFrame:
    eff_from = config.reference_date.isoformat()
    snapshot_date = weeks[0].week_start_date.isoformat()

    mean_demand = (
        demand_df.groupby(["sku_id", "location_id"], sort=True)["forecast_qty"]
        .mean()
        .reset_index()
        .rename(columns={"forecast_qty": "mean_weekly_demand"})
    )
    base = mean_demand.merge(skus[["sku_id", "base_uom"]], on="sku_id", how="left")
    n = len(base)

    coverage_weeks = rng.uniform(
        config.inventory.initial_coverage_min_weeks,
        config.inventory.initial_coverage_max_weeks,
        size=n,
    )
    lean_mask = rng.random(size=n) < 0.12
    coverage_weeks = np.where(lean_mask, rng.uniform(0.2, 0.8, size=n), coverage_weeks)

    mean_vec = base["mean_weekly_demand"].to_numpy(dtype=np.float64)
    on_hand = np.maximum(0, np.rint(mean_vec * coverage_weeks)).astype(np.int64)
    reserved_share = rng.uniform(0.0, config.inventory.reserved_share_max, size=n)
    reserved = np.minimum(on_hand, np.floor(on_hand * reserved_share).astype(np.int64))
    available = on_hand - reserved

    safety_stock = np.maximum(
        1, np.rint(mean_vec * config.inventory.safety_stock_weeks)
    ).astype(np.int64)
    reorder_point = safety_stock + np.maximum(1, np.rint(mean_vec * 1.0)).astype(np.int64)

    df = pd.DataFrame(
        {
            "inventory_id": "INV-" + base["sku_id"] + "-" + base["location_id"],
            "sku_id": base["sku_id"],
            "location_id": base["location_id"],
            "snapshot_date": snapshot_date,
            "on_hand_qty": on_hand,
            "reserved_qty": reserved,
            "available_qty": available,
            "safety_stock_qty": safety_stock,
            "reorder_point_qty": reorder_point,
            "uom": base["base_uom"],
            "effective_from": eff_from,
            "effective_to": None,
            "lifecycle_state": EntityStatus.ACTIVE.value,
        }
    )
    return df.sort_values("inventory_id", kind="mergesort").reset_index(drop=True)
