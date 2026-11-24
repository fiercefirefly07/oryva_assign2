"""Phase 3 tests: Demand, Inventory, LeadTime, PO + Events, SupplierCapacity, ProductionPlan."""

from __future__ import annotations

import numpy as np

from oryva_planning.config import get_planning_weeks, load_config
from oryva_planning.generators import (
    generate_bom_items,
    generate_forecast_demand,
    generate_inventory,
    generate_lead_times,
    generate_locations,
    generate_production_plans,
    generate_purchase_orders_and_capacity,
    generate_sku_suppliers,
    generate_skus,
    generate_suppliers,
)


def test_dependent_tables_distributions_and_derivations() -> None:
    cfg = load_config("starter", seed_override=20261022)
    rngs = [np.random.default_rng(c) for c in np.random.SeedSequence(cfg.seed).spawn(13)]
    weeks = get_planning_weeks(cfg.planning_year, cfg.start_week, cfg.num_weeks)

    skus = generate_skus(cfg, rngs[0])
    locs = generate_locations(cfg, rngs[1])
    sups = generate_suppliers(cfg, rngs[2])
    sku_sups = generate_sku_suppliers(cfg, rngs[3], skus, sups)
    bom = generate_bom_items(cfg, rngs[5], skus)

    demand = generate_forecast_demand(cfg, rngs[6], skus, locs, weeks)
    inv = generate_inventory(cfg, rngs[7], skus, locs, demand, weeks)
    lts = generate_lead_times(cfg, rngs[8], skus, locs, sups, sku_sups)
    pos, po_events, cap = generate_purchase_orders_and_capacity(
        cfg, rngs[9], rngs[10], skus, locs, sups, sku_sups, lts, demand, weeks
    )
    prod = generate_production_plans(cfg, rngs[11], skus, locs, bom, inv, demand, weeks)

    assert len(demand) == cfg.scale.num_skus * cfg.scale.num_locations * cfg.num_weeks
    assert demand["is_spike_week"].any()
    assert (demand["forecast_qty"] >= 0).all()

    assert len(inv) == cfg.scale.num_skus * cfg.scale.num_locations
    assert (inv["available_qty"] == inv["on_hand_qty"] - inv["reserved_qty"]).all()

    assert (
        lts["total_lead_time_days"]
        == lts["manufacturing_days"] + lts["transit_days"] + lts["customs_buffer_days"]
    ).all()

    assert len(pos) == cfg.scale.num_purchase_orders
    assert (pos["transport_delay_days"] > 0).any()
    assert len(po_events) >= len(pos)
    assert (cap["available_capacity"] == cap["max_weekly_capacity"] - cap["committed_qty"]).all()
    assert (cap["available_capacity"] >= 0).all()

    assert not prod.empty
    assert (
        prod["achievable_qty"]
        == prod[["planned_qty", "capacity_limit_qty", "bom_feasible_qty"]].min(axis=1)
    ).all()
