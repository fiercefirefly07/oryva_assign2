"""ProductionPlan generator constrained by plant capacity and BOM component availability."""

from __future__ import annotations

import numpy as np
import pandas as pd

from oryva_planning.config import PlanningConfig, PlanningWeek
from oryva_planning.schema.enums import LocationType, ProductionStatus, SourcingType
from oryva_planning.schema.ids import make_production_id


def generate_production_plans(
    config: PlanningConfig,
    rng: np.random.Generator,
    skus: pd.DataFrame,
    locations: pd.DataFrame,
    bom_items: pd.DataFrame,
    inventory: pd.DataFrame,
    demand_df: pd.DataFrame,
    weeks: list[PlanningWeek],
) -> pd.DataFrame:
    eff_from = config.reference_date.isoformat()
    year = config.planning_year

    plants = locations[locations["location_type"] == LocationType.PLANT.value].sort_values(
        "location_id", kind="mergesort"
    )
    make_skus = skus[
        skus["sourcing_type"].isin([SourcingType.MAKE.value, SourcingType.BOTH.value])
    ].sort_values("sku_id", kind="mergesort")

    if plants.empty or make_skus.empty:
        return pd.DataFrame(
            columns=[
                "production_id", "sku_id", "location_id", "week_id", "week_start_date",
                "planned_qty", "capacity_limit_qty", "bom_feasible_qty", "achievable_qty",
                "uom", "unit_production_cost", "lifecycle_state", "effective_from", "effective_to",
            ]
        )

    plant_ids = plants["location_id"].tolist()
    plant_weekly_cap = {
        r.location_id: int(r.daily_production_capacity) * 6
        for r in plants.itertuples(index=False)
    }

    plant_demand = demand_df[
        demand_df["sku_id"].isin(make_skus["sku_id"])
        & demand_df["location_id"].isin(plant_ids)
    ]
    dem_lookup = dict(
        zip(
            zip(plant_demand["sku_id"], plant_demand["location_id"], plant_demand["week_id"]),
            plant_demand["forecast_qty"],
        )
    )
    comp_inv = dict(zip(zip(inventory["sku_id"], inventory["location_id"]), inventory["available_qty"]))
    bom_by_parent: dict[str, list[tuple[str, float, float]]] = {}
    for b in bom_items.itertuples(index=False):
        bom_by_parent.setdefault(b.parent_sku_id, []).append(
            (b.component_sku_id, float(b.qty_per_parent), float(b.scrap_rate))
        )

    rows: list[dict[str, object]] = []
    seq = 0
    n_make = len(make_skus)

    for s_idx, s_row in enumerate(make_skus.itertuples(index=False)):
        plant_id = plant_ids[s_idx % len(plant_ids)]
        sku_cap_share = max(20, plant_weekly_cap[plant_id] // max(1, (n_make // len(plant_ids) + 1)))
        comp_reqs = bom_by_parent.get(s_row.sku_id, [])

        for w_idx, wk in enumerate(weeks):
            local_dem = int(dem_lookup.get((s_row.sku_id, plant_id, wk.week_id), 0))
            if local_dem <= 0:
                continue
            build_share = 0.96 if s_row.sourcing_type == SourcingType.MAKE.value else 0.50
            planned = max(1, int(round(local_dem * build_share)))

            if rng.random() < config.production.constrained_week_share:
                cap_limit = max(1, int(round(planned * float(rng.uniform(0.55, 0.85)))))
            else:
                cap_limit = max(sku_cap_share, int(round(planned * config.production.capacity_buffer_ratio)))

            if comp_reqs:
                feas_candidates = []
                for comp_id, q_per, scrap in comp_reqs:
                    avail_comp = int(comp_inv.get((comp_id, plant_id), 0)) + int(planned * q_per * 1.15)
                    if rng.random() < 0.08:
                        avail_comp = int(planned * q_per * float(rng.uniform(0.6, 0.9)))
                    eff_req = q_per * (1.0 + scrap)
                    feas_candidates.append(max(0, int(avail_comp // eff_req)))
                bom_feasible = min(feas_candidates)
            else:
                bom_feasible = planned

            achievable = min(planned, cap_limit, bom_feasible)
            if achievable < planned:
                status = ProductionStatus.CONSTRAINED.value
            elif w_idx < 8:
                status = ProductionStatus.COMPLETED.value
            elif w_idx < 12:
                status = ProductionStatus.IN_PROGRESS.value
            elif w_idx < 26:
                status = ProductionStatus.SCHEDULED.value
            else:
                status = ProductionStatus.PLANNED.value

            seq += 1
            rows.append(
                {
                    "production_id": make_production_id(year, seq),
                    "sku_id": s_row.sku_id,
                    "location_id": plant_id,
                    "week_id": wk.week_id,
                    "week_start_date": wk.week_start_date.isoformat(),
                    "planned_qty": planned,
                    "capacity_limit_qty": cap_limit,
                    "bom_feasible_qty": bom_feasible,
                    "achievable_qty": achievable,
                    "uom": s_row.base_uom,
                    "unit_production_cost": round(float(s_row.unit_cost) * 0.88, 4),
                    "lifecycle_state": status,
                    "effective_from": eff_from,
                    "effective_to": None,
                }
            )

    return pd.DataFrame(rows).sort_values("production_id", kind="mergesort").reset_index(drop=True)
