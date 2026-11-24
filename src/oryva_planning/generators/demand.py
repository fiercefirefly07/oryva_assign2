"""Vectorized NumPy ForecastDemand generator (Pareto velocity, seasonality, NegBin, spikes)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from oryva_planning.config import PlanningConfig, PlanningWeek
from oryva_planning.schema.enums import EntityStatus, PopularityTier


def generate_forecast_demand(
    config: PlanningConfig,
    rng: np.random.Generator,
    skus: pd.DataFrame,
    locations: pd.DataFrame,
    weeks: list[PlanningWeek],
) -> pd.DataFrame:
    """Generate SKU x Location x Week forecast demand with vectorized NumPy (scales to 7.8M rows)."""
    n_sku = len(skus)
    n_loc = len(locations)
    n_wk = len(weeks)
    total_rows = n_sku * n_loc * n_wk
    eff_from = config.reference_date.isoformat()

    ranks = skus["popularity_rank"].to_numpy(dtype=np.float64)
    sku_weights = np.power(ranks, -0.55)
    sku_weights = sku_weights / sku_weights.mean()

    cap = locations["storage_capacity_units"].to_numpy(dtype=np.float64)
    loc_weights = cap / cap.mean()

    week_idx = np.arange(n_wk, dtype=np.float64)
    sku_phase = rng.uniform(0.0, 2.0 * np.pi, size=n_sku)
    seasonality = 1.0 + config.demand.seasonality_amplitude * np.sin(
        2.0 * np.pi * week_idx[None, :] / max(n_wk, 1) + sku_phase[:, None]
    )

    mu = (
        config.demand.base_weekly_mean
        * sku_weights[:, None, None]
        * loc_weights[None, :, None]
        * seasonality[:, None, :]
    )
    mu = np.clip(mu, 1.0, None)

    spike_mask = rng.random(size=(n_sku, n_loc, n_wk)) < config.demand.spike_probability
    spike_mult = rng.uniform(
        config.demand.spike_min_multiplier,
        config.demand.spike_max_multiplier,
        size=(n_sku, n_loc, n_wk),
    )
    mu_spiked = np.where(spike_mask, mu * spike_mult, mu)

    k = config.demand.dispersion_k
    gamma_rate = rng.gamma(shape=k, scale=mu_spiked / k)
    qty = rng.poisson(lam=np.clip(gamma_rate, 0.0, 1e6)).astype(np.int64)

    sku_ids = skus["sku_id"].to_numpy()
    sku_uoms = skus["base_uom"].to_numpy()
    tier_priority_map = {
        PopularityTier.A.value: 1.5,
        PopularityTier.B.value: 1.0,
        PopularityTier.C.value: 0.6,
    }
    sku_priority = (
        skus["popularity_tier"].map(tier_priority_map).to_numpy(dtype=np.float64)
        + np.where(skus["is_critical"].to_numpy(), 0.5, 0.0)
    )

    loc_ids = locations["location_id"].to_numpy()
    wk_ids = np.array([w.week_id for w in weeks], dtype=object)
    wk_starts = np.array([w.week_start_date.isoformat() for w in weeks], dtype=object)

    sku_col = np.repeat(sku_ids, n_loc * n_wk)
    uom_col = np.repeat(sku_uoms, n_loc * n_wk)
    prio_col = np.repeat(sku_priority, n_loc * n_wk)
    loc_col = np.tile(np.repeat(loc_ids, n_wk), n_sku)
    wk_col = np.tile(wk_ids, n_sku * n_loc)
    wk_start_col = np.tile(wk_starts, n_sku * n_loc)
    seas_col = np.round(np.repeat(seasonality, n_loc, axis=0).reshape(total_rows), 4)

    df = pd.DataFrame(
        {
            "sku_id": sku_col,
            "location_id": loc_col,
            "week_id": wk_col,
            "week_start_date": wk_start_col,
            "forecast_qty": qty.reshape(total_rows),
            "uom": uom_col,
            "is_spike_week": spike_mask.reshape(total_rows),
            "seasonality_factor": seas_col,
            "priority_weight": np.round(prio_col, 4),
            "effective_from": eff_from,
            "effective_to": None,
            "lifecycle_state": EntityStatus.ACTIVE.value,
        }
    )
    df.insert(
        0,
        "demand_id",
        "DEM-" + df["sku_id"] + "-" + df["location_id"] + "-" + df["week_id"],
    )
    return df.sort_values("demand_id", kind="mergesort").reset_index(drop=True)
