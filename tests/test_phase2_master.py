"""Phase 2 tests: Master and M:N bridge table generators."""

from __future__ import annotations

import numpy as np

from oryva_planning.config import load_config
from oryva_planning.generators.master import (
    generate_bom_items,
    generate_locations,
    generate_sku_substitutes,
    generate_sku_suppliers,
    generate_skus,
    generate_suppliers,
)


def _build_masters():
    cfg = load_config("starter", seed_override=20261022)
    rngs = [np.random.default_rng(c) for c in np.random.SeedSequence(cfg.seed).spawn(13)]
    skus = generate_skus(cfg, rngs[0])
    locs = generate_locations(cfg, rngs[1])
    sups = generate_suppliers(cfg, rngs[2])
    sku_sups = generate_sku_suppliers(cfg, rngs[3], skus, sups)
    sku_subs = generate_sku_substitutes(cfg, rngs[4], skus)
    bom = generate_bom_items(cfg, rngs[5], skus)
    return cfg, skus, locs, sups, sku_sups, sku_subs, bom


def test_master_counts_pks_and_business_invariants() -> None:
    cfg, skus, locs, sups, _, _, _ = _build_masters()
    assert len(skus) == cfg.scale.num_skus
    assert len(locs) == cfg.scale.num_locations
    assert len(sups) == cfg.scale.num_suppliers

    assert skus["sku_id"].is_unique
    assert skus["popularity_rank"].is_unique
    assert (skus["unit_price"] >= skus["unit_cost"]).all()
    assert set(skus["popularity_tier"]) == {"A", "B", "C"}

    assert (locs["location_type"] == "PLANT").any()
    assert (locs.loc[locs["location_type"] != "PLANT", "daily_production_capacity"] == 0).all()

    assert sups["is_constrained"].any()
    assert (sups["reliability_tier"] == "LOW").any()


def test_bridge_tables_referential_integrity_and_substitute_flags() -> None:
    _, skus, _, sups, sku_sups, sku_subs, bom = _build_masters()
    sku_set = set(skus["sku_id"])
    sup_set = set(sups["supplier_id"])

    assert set(sku_sups["sku_id"]) == sku_set
    assert set(sku_sups["supplier_id"]).issubset(sup_set)
    assert sku_sups.groupby("sku_id")["is_primary"].sum().eq(1).all()

    assert set(sku_subs["sku_id"]).issubset(sku_set)
    assert set(sku_subs["substitute_sku_id"]).issubset(sku_set)
    assert (sku_subs["sku_id"] != sku_subs["substitute_sku_id"]).all()
    assert sku_subs["approved"].any() and (~sku_subs["approved"]).any()

    assert set(bom["parent_sku_id"]).issubset(sku_set)
    assert set(bom["component_sku_id"]).issubset(sku_set)
    assert (bom["parent_sku_id"] != bom["component_sku_id"]).all()
