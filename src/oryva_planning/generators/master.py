"""Master entity and M:N bridge table generators (deterministic, SeedSequence-driven)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from oryva_planning.config import PlanningConfig
from oryva_planning.schema.enums import (
    EntityStatus,
    LocationType,
    PopularityTier,
    Region,
    ReliabilityTier,
    SKUCategory,
    SourcingType,
    SupplierTier,
    UOM,
)
from oryva_planning.schema.ids import (
    make_bom_id,
    make_location_id,
    make_sku_id,
    make_sku_substitute_id,
    make_sku_supplier_id,
    make_supplier_id,
)

_CITY_BY_REGION: dict[Region, tuple[str, ...]] = {
    Region.SOUTH: ("Bengaluru", "Chennai", "Hyderabad", "Coimbatore", "Kochi", "Hosur", "Mysuru"),
    Region.WEST: ("Pune", "Mumbai", "Ahmedabad", "Nashik", "Vadodara", "Surat", "Nagpur"),
    Region.NORTH: ("Gurugram", "Noida", "Ludhiana", "Jaipur", "Chandigarh", "Baddi", "Kanpur"),
    Region.EAST: ("Kolkata", "Bhubaneswar", "Jamshedpur", "Guwahati", "Ranchi", "Patna"),
    Region.CENTRAL: ("Indore", "Bhopal", "Raipur", "Jabalpur", "Gwalior"),
}

_CATEGORY_UOMS: dict[SKUCategory, tuple[UOM, ...]] = {
    SKUCategory.ELECTRONICS: (UOM.EA, UOM.CASE),
    SKUCategory.INDUSTRIAL: (UOM.EA, UOM.KG, UOM.PALLET),
    SKUCategory.PACKAGING: (UOM.CASE, UOM.PALLET, UOM.EA),
    SKUCategory.CONSUMABLES: (UOM.KG, UOM.L, UOM.CASE),
    SKUCategory.SPARE_PARTS: (UOM.EA, UOM.CASE),
}

_SUPPLIER_PREFIXES = (
    "Apex", "Bharat", "Deccan", "Vindhya", "Coromandel", "Kaveri", "Sahyadri",
    "Indus", "Trident", "Precision", "Zenith", "Orbit", "Matrix", "Vector", "Prime",
)
_SUPPLIER_SUFFIXES = (
    "Components", "Industries", "Logistics", "Materials", "Systems", "Tech", "Manufacturing",
)


def generate_skus(config: PlanningConfig, rng: np.random.Generator) -> pd.DataFrame:
    n = config.scale.num_skus
    eff_from = config.reference_date.isoformat()

    categories = list(SKUCategory)
    cat_idx = rng.integers(0, len(categories), size=n)

    raw_weights = rng.pareto(config.demand.pareto_alpha, size=n) + 1.0
    order = np.argsort(-raw_weights, kind="mergesort")
    ranks = np.empty(n, dtype=np.int64)
    ranks[order] = np.arange(1, n + 1, dtype=np.int64)

    n_make_total = max(2, int(round(n * config.scale.make_sku_share)))
    n_make_total = min(n_make_total, max(2, n // 2))
    sourcing_arr = np.full(n, SourcingType.BUY.value, dtype=object)
    make_candidates = rng.choice(n, size=n_make_total, replace=False)
    half = max(1, n_make_total // 2)
    sourcing_arr[make_candidates[:half]] = SourcingType.MAKE.value
    sourcing_arr[make_candidates[half:]] = SourcingType.BOTH.value

    unit_costs = np.round(np.clip(rng.lognormal(mean=5.6, sigma=0.75, size=n), 25.0, 25000.0), 4)
    margins = rng.uniform(1.18, 1.65, size=n)
    unit_prices = np.round(unit_costs * margins, 4)
    weights_kg = np.round(np.clip(rng.lognormal(mean=0.4, sigma=0.8, size=n), 0.1, 150.0), 4)

    rows = []
    a_cut = max(1, int(round(n * 0.20)))
    b_cut = max(a_cut + 1, int(round(n * 0.50)))
    for i in range(n):
        sku_id = make_sku_id(i + 1)
        cat = categories[int(cat_idx[i])]
        allowed_uoms = _CATEGORY_UOMS[cat]
        uom = allowed_uoms[int(rng.integers(0, len(allowed_uoms)))]
        rank = int(ranks[i])
        if rank <= a_cut:
            tier = PopularityTier.A.value
            is_critical = True
        elif rank <= b_cut:
            tier = PopularityTier.B.value
            is_critical = bool(rng.random() < 0.25)
        else:
            tier = PopularityTier.C.value
            is_critical = False
        rows.append(
            {
                "sku_id": sku_id,
                "sku_name": f"{cat.value.replace('_', ' ').title()} Item {i + 1:04d}",
                "category": cat.value,
                "sourcing_type": str(sourcing_arr[i]),
                "base_uom": uom.value,
                "unit_cost": float(unit_costs[i]),
                "unit_price": float(unit_prices[i]),
                "weight_kg": float(weights_kg[i]),
                "popularity_rank": rank,
                "popularity_tier": tier,
                "is_critical": is_critical,
                "effective_from": eff_from,
                "effective_to": None,
                "lifecycle_state": EntityStatus.ACTIVE.value,
            }
        )
    return pd.DataFrame(rows).sort_values("sku_id", kind="mergesort").reset_index(drop=True)


def generate_locations(config: PlanningConfig, rng: np.random.Generator) -> pd.DataFrame:
    n = config.scale.num_locations
    eff_from = config.reference_date.isoformat()
    regions = list(Region)
    loc_types = [
        LocationType.PLANT,
        LocationType.DISTRIBUTION_CENTER,
        LocationType.WAREHOUSE,
        LocationType.REGIONAL_HUB,
    ]
    rows = []
    for i in range(n):
        loc_id = make_location_id(i + 1)
        region = regions[i % len(regions)]
        cities = _CITY_BY_REGION[region]
        city = cities[(i // len(regions)) % len(cities)]
        ltype = LocationType.PLANT if (i == 0 or i % 5 == 0) else loc_types[1 + int(rng.integers(0, len(loc_types) - 1))]
        storage_cap = int(rng.integers(15000, 120000))
        daily_prod = int(rng.integers(400, 2500)) if ltype == LocationType.PLANT else 0
        hold_cost = round(float(rng.uniform(1.5, 12.0)), 4)
        rows.append(
            {
                "location_id": loc_id,
                "location_name": f"{city} {ltype.value.replace('_', ' ').title()} {i + 1:02d}",
                "location_type": ltype.value,
                "region": region.value,
                "storage_capacity_units": storage_cap,
                "daily_production_capacity": daily_prod,
                "holding_cost_per_unit_week": hold_cost,
                "effective_from": eff_from,
                "effective_to": None,
                "lifecycle_state": EntityStatus.ACTIVE.value,
            }
        )
    return pd.DataFrame(rows).sort_values("location_id", kind="mergesort").reset_index(drop=True)


def generate_suppliers(config: PlanningConfig, rng: np.random.Generator) -> pd.DataFrame:
    n = config.scale.num_suppliers
    eff_from = config.reference_date.isoformat()
    regions = list(Region)

    n_constrained = max(1, int(round(n * config.supplier.constrained_share)))
    n_unreliable = max(1, int(round(n * config.supplier.unreliable_share)))
    constrained_idx = set(int(x) for x in rng.choice(n, size=n_constrained, replace=False))
    unreliable_idx = set(int(x) for x in rng.choice(n, size=n_unreliable, replace=False))

    rows = []
    for i in range(n):
        sup_id = make_supplier_id(i + 1)
        region = regions[i % len(regions)]
        is_constrained = i in constrained_idx
        is_unreliable = i in unreliable_idx

        if is_constrained:
            tier = SupplierTier.CONSTRAINED.value
        elif i % 5 == 0:
            tier = SupplierTier.STRATEGIC.value
        elif i % 2 == 0:
            tier = SupplierTier.PREFERRED.value
        else:
            tier = SupplierTier.APPROVED.value

        if is_unreliable:
            rel_tier = ReliabilityTier.LOW.value
            on_time = round(float(rng.uniform(0.62, 0.78)), 4)
        elif tier == SupplierTier.STRATEGIC.value:
            rel_tier = ReliabilityTier.HIGH.value
            on_time = round(float(rng.uniform(0.92, 0.99)), 4)
        else:
            rel_tier = ReliabilityTier.MEDIUM.value
            on_time = round(float(rng.uniform(0.82, 0.93)), 4)

        prefix = _SUPPLIER_PREFIXES[i % len(_SUPPLIER_PREFIXES)]
        suffix = _SUPPLIER_SUFFIXES[(i // len(_SUPPLIER_PREFIXES)) % len(_SUPPLIER_SUFFIXES)]
        surcharge = round(float(rng.uniform(0.10, 0.35)), 4)
        rows.append(
            {
                "supplier_id": sup_id,
                "supplier_name": f"{prefix} {suffix} {i + 1:03d}",
                "region": region.value,
                "supplier_tier": tier,
                "reliability_tier": rel_tier,
                "on_time_rate": on_time,
                "is_constrained": is_constrained,
                "expedite_surcharge_pct": surcharge,
                "effective_from": eff_from,
                "effective_to": None,
                "lifecycle_state": EntityStatus.ACTIVE.value,
            }
        )
    return pd.DataFrame(rows).sort_values("supplier_id", kind="mergesort").reset_index(drop=True)


def generate_sku_suppliers(
    config: PlanningConfig,
    rng: np.random.Generator,
    skus: pd.DataFrame,
    suppliers: pd.DataFrame,
) -> pd.DataFrame:
    eff_from = config.reference_date.isoformat()
    sup_ids = suppliers["supplier_id"].to_numpy()
    n_sup = len(sup_ids)
    avg_k = min(config.scale.avg_suppliers_per_sku, n_sup)

    rows = []
    for row in skus.itertuples(index=False):
        k_low = min(2, n_sup)
        k_high = min(max(k_low, avg_k + 1), n_sup)
        k = int(rng.integers(k_low, k_high + 1))
        chosen = sorted(str(x) for x in rng.choice(sup_ids, size=k, replace=False))
        primary_idx = int(rng.integers(0, k))
        for j, sup_id in enumerate(chosen):
            price_mult = float(rng.uniform(0.95, 1.12)) if j != primary_idx else 1.0
            moq = int(rng.choice([10, 20, 25, 50, 100]))
            multiple = int(rng.choice([1, 5, 10]))
            rows.append(
                {
                    "sku_supplier_id": make_sku_supplier_id(row.sku_id, sup_id),
                    "sku_id": row.sku_id,
                    "supplier_id": sup_id,
                    "unit_purchase_cost": round(float(row.unit_cost) * price_mult, 4),
                    "min_order_qty": moq,
                    "order_multiple": multiple,
                    "is_primary": j == primary_idx,
                    "contract_uom": row.base_uom,
                    "effective_from": eff_from,
                    "effective_to": None,
                    "lifecycle_state": EntityStatus.ACTIVE.value,
                }
            )
    return pd.DataFrame(rows).sort_values("sku_supplier_id", kind="mergesort").reset_index(drop=True)


def generate_sku_substitutes(
    config: PlanningConfig,
    rng: np.random.Generator,
    skus: pd.DataFrame,
) -> pd.DataFrame:
    eff_from = config.reference_date.isoformat()
    grouped = skus.groupby(["category", "base_uom"], sort=True)["sku_id"].apply(list)

    rows = []
    seen_pairs: set[tuple[str, str]] = set()
    target_share = config.scale.substitute_sku_share

    for _, sku_list in grouped.items():
        if len(sku_list) < 2:
            continue
        sorted_skus = sorted(sku_list)
        for sku_id in sorted_skus:
            if rng.random() > target_share and len(rows) >= 20:
                continue
            candidates = [s for s in sorted_skus if s != sku_id]
            n_subs = min(2, len(candidates))
            picked = sorted(str(x) for x in rng.choice(candidates, size=n_subs, replace=False))
            for rank_i, sub_id in enumerate(picked, start=1):
                if (sku_id, sub_id) in seen_pairs:
                    continue
                seen_pairs.add((sku_id, sub_id))
                approved = True if rank_i == 1 else bool(rng.random() < 0.30)
                rows.append(
                    {
                        "sku_substitute_id": make_sku_substitute_id(sku_id, sub_id),
                        "sku_id": sku_id,
                        "substitute_sku_id": sub_id,
                        "approved": approved,
                        "conversion_factor": 1.0,
                        "cost_delta_pct": round(float(rng.uniform(-0.08, 0.25)), 4),
                        "priority_rank": rank_i,
                        "effective_from": eff_from,
                        "effective_to": None,
                        "lifecycle_state": EntityStatus.ACTIVE.value,
                    }
                )

    unapproved_count = sum(1 for r in rows if not r["approved"])
    min_needed = max(config.anomalies.unapproved_substitute + 8, 12)
    if unapproved_count < min_needed:
        all_skus = skus["sku_id"].tolist()
        for i in range(len(all_skus) - 1):
            if unapproved_count >= min_needed:
                break
            a, b = all_skus[i], all_skus[i + 1]
            if (a, b) in seen_pairs:
                continue
            seen_pairs.add((a, b))
            rows.append(
                {
                    "sku_substitute_id": make_sku_substitute_id(a, b),
                    "sku_id": a,
                    "substitute_sku_id": b,
                    "approved": False,
                    "conversion_factor": 1.0,
                    "cost_delta_pct": round(float(rng.uniform(0.05, 0.20)), 4),
                    "priority_rank": 2,
                    "effective_from": eff_from,
                    "effective_to": None,
                    "lifecycle_state": EntityStatus.ACTIVE.value,
                }
            )
            unapproved_count += 1

    return pd.DataFrame(rows).sort_values("sku_substitute_id", kind="mergesort").reset_index(drop=True)


def generate_bom_items(
    config: PlanningConfig,
    rng: np.random.Generator,
    skus: pd.DataFrame,
) -> pd.DataFrame:
    eff_from = config.reference_date.isoformat()
    parents = skus[skus["sourcing_type"].isin([SourcingType.MAKE.value, SourcingType.BOTH.value])]
    components = skus[skus["sourcing_type"] == SourcingType.BUY.value]
    if parents.empty or components.empty:
        return pd.DataFrame(
            columns=[
                "bom_id", "parent_sku_id", "component_sku_id", "qty_per_parent",
                "uom", "scrap_rate", "effective_from", "effective_to", "lifecycle_state",
            ]
        )

    comp_ids = components["sku_id"].to_numpy()
    comp_uom_map = dict(zip(components["sku_id"], components["base_uom"]))
    max_comp = min(config.scale.max_bom_components, len(comp_ids))

    rows = []
    for p_row in parents.itertuples(index=False):
        k = int(rng.integers(1, max_comp + 1))
        picked = sorted(str(x) for x in rng.choice(comp_ids, size=k, replace=False))
        for comp_id in picked:
            rows.append(
                {
                    "bom_id": make_bom_id(p_row.sku_id, comp_id),
                    "parent_sku_id": p_row.sku_id,
                    "component_sku_id": comp_id,
                    "qty_per_parent": float(rng.choice([1.0, 2.0, 3.0, 4.0])),
                    "uom": comp_uom_map[comp_id],
                    "scrap_rate": round(float(rng.uniform(0.01, 0.06)), 4),
                    "effective_from": eff_from,
                    "effective_to": None,
                    "lifecycle_state": EntityStatus.ACTIVE.value,
                }
            )
    return pd.DataFrame(rows).sort_values("bom_id", kind="mergesort").reset_index(drop=True)
