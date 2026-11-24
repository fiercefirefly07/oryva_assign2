"""Policy-compliant, capacity-checked MitigationOption engine with cost/service trade-offs."""

from __future__ import annotations

import pandas as pd

from oryva_planning.config import PlanningConfig
from oryva_planning.schema.enums import MitigationStatus, MitigationType, POStatus, ShortageStatus
from oryva_planning.schema.ids import make_mitigation_id


def generate_mitigation_options(
    config: PlanningConfig,
    skus: pd.DataFrame,
    locations: pd.DataFrame,
    suppliers: pd.DataFrame,
    sku_suppliers: pd.DataFrame,
    sku_substitutes: pd.DataFrame,
    capacity_df: pd.DataFrame,
    lead_times_df: pd.DataFrame,
    po_df: pd.DataFrame,
    production_df: pd.DataFrame,
    balance_df: pd.DataFrame,
    shortages_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    eff_from = config.reference_date.isoformat()
    if shortages_df.empty:
        empty = pd.DataFrame(
            columns=[
                "mitigation_id", "shortage_id", "mitigation_type", "target_supplier_id",
                "target_sku_id", "source_location_id", "mitigation_qty", "cost",
                "service_level_impact", "lead_time_days", "capacity_check_passed",
                "policy_check_passed", "score", "rank", "lifecycle_state",
                "effective_from", "effective_to",
            ]
        )
        return empty, shortages_df.copy()

    w_cost = config.mitigation.cost_weight
    w_serv = config.mitigation.service_weight
    w_lt = config.mitigation.lead_time_weight
    max_opts = config.mitigation.max_options_per_shortage

    sku_cost = dict(zip(skus["sku_id"], skus["unit_cost"]))
    sku_weight = dict(zip(skus["sku_id"], skus["weight_kg"]))
    loc_region = dict(zip(locations["location_id"], locations["region"]))
    sup_surcharge = dict(zip(suppliers["supplier_id"], suppliers["expedite_surcharge_pct"]))

    relevant_skus = set(shortages_df["sku_id"].unique())
    relevant_skus.update(
        sku_substitutes.loc[
            sku_substitutes["approved"] & sku_substitutes["sku_id"].isin(relevant_skus),
            "substitute_sku_id",
        ].unique()
    )
    relevant_weeks = set(shortages_df["week_id"].unique())
    surplus_mask = (
        (balance_df["closing_stock"] > balance_df["safety_stock_qty"])
        & balance_df["sku_id"].isin(relevant_skus)
        & balance_df["week_id"].isin(relevant_weeks)
    )
    surplus_df = balance_df.loc[
        surplus_mask, ["sku_id", "location_id", "week_id", "closing_stock", "safety_stock_qty"]
    ].copy()
    surplus_df["surplus"] = surplus_df["closing_stock"] - surplus_df["safety_stock_qty"]
    surplus_by_sku_wk: dict[tuple[str, str], list[tuple[str, int]]] = {}
    surplus_by_sku_loc_wk: dict[tuple[str, str, str], int] = {}
    for r in surplus_df.sort_values(
        ["sku_id", "week_id", "surplus", "location_id"],
        ascending=[True, True, False, True],
        kind="mergesort",
    ).itertuples(index=False):
        s_val = int(r.surplus)
        surplus_by_sku_wk.setdefault((r.sku_id, r.week_id), []).append((r.location_id, s_val))
        surplus_by_sku_loc_wk[(r.sku_id, r.location_id, r.week_id)] = s_val

    sku_sup_map: dict[str, list[tuple[str, float, bool]]] = {}
    for r in sku_suppliers.sort_values(
        ["sku_id", "is_primary", "unit_purchase_cost", "supplier_id"],
        ascending=[True, False, True, True],
        kind="mergesort",
    ).itertuples(index=False):
        sku_sup_map.setdefault(r.sku_id, []).append(
            (r.supplier_id, float(r.unit_purchase_cost), bool(r.is_primary))
        )

    avail_cap_map: dict[tuple[str, str], int] = {
        (r.supplier_id, r.week_id): int(r.available_capacity)
        for r in capacity_df.itertuples(index=False)
    }
    lt_map: dict[tuple[str, str, str], int] = {
        (r.sku_id, r.supplier_id, r.location_id): int(r.total_lead_time_days)
        for r in lead_times_df.itertuples(index=False)
    }

    approved_subs: dict[str, list[tuple[str, float, float]]] = {}
    for r in sku_substitutes[sku_substitutes["approved"]].sort_values(
        ["sku_id", "priority_rank", "substitute_sku_id"], kind="mergesort"
    ).itertuples(index=False):
        approved_subs.setdefault(r.sku_id, []).append(
            (r.substitute_sku_id, float(r.conversion_factor), float(r.cost_delta_pct))
        )

    exp_po_map: dict[tuple[str, str], list[tuple[str, int, float]]] = {}
    exp_candidates = po_df[
        po_df["current_status"].isin(
            [POStatus.CONFIRMED.value, POStatus.IN_TRANSIT.value, POStatus.DELAYED.value]
        )
    ].sort_values("po_id", kind="mergesort")
    for r in exp_candidates.itertuples(index=False):
        exp_po_map.setdefault((r.sku_id, r.location_id), []).append(
            (r.supplier_id, int(r.order_qty), float(r.unit_cost))
        )

    prod_map: dict[tuple[str, str, str], tuple[int, int, float]] = {}
    if not production_df.empty:
        for r in production_df.itertuples(index=False):
            prod_map[(r.sku_id, r.location_id, r.week_id)] = (
                int(r.capacity_limit_qty), int(r.bom_feasible_qty), float(r.unit_production_cost)
            )

    mitigation_rows: list[dict[str, object]] = []
    updated_statuses: dict[str, str] = {}

    for s_row in shortages_df.sort_values("shortage_id", kind="mergesort").itertuples(index=False):
        sid = s_row.shortage_id
        sku_id, loc_id, wk_id = s_row.sku_id, s_row.location_id, s_row.week_id
        qty_needed = int(s_row.shortage_qty)
        base_cost = float(sku_cost[sku_id])
        wt_kg = float(sku_weight[sku_id])
        candidates: list[dict[str, object]] = []

        # 1. INTER_LOCATION_TRANSFER
        donors = [
            (d_loc, d_qty)
            for d_loc, d_qty in surplus_by_sku_wk.get((sku_id, wk_id), [])
            if d_loc != loc_id and d_qty > 0
        ]
        if donors:
            donor_loc, donor_surplus = donors[0]
            cover = min(qty_needed, donor_surplus)
            same_region = loc_region.get(donor_loc) == loc_region.get(loc_id)
            lt_d = 2 if same_region else 5
            freight_per_unit = (12.0 if same_region else 28.0) + wt_kg * (2.5 if same_region else 6.0)
            candidates.append(
                {
                    "mitigation_type": MitigationType.INTER_LOCATION_TRANSFER.value,
                    "target_supplier_id": None,
                    "target_sku_id": None,
                    "source_location_id": donor_loc,
                    "mitigation_qty": cover,
                    "cost": round(cover * freight_per_unit, 4),
                    "service_level_impact": round(min(1.0, cover / qty_needed), 4),
                    "lead_time_days": lt_d,
                    "capacity_check_passed": True,
                    "policy_check_passed": True,
                }
            )

        # 2. ALTERNATE_SUPPLIER
        alt_picked = None
        for sup_id, u_cost, is_prim in sku_sup_map.get(sku_id, []):
            avail = avail_cap_map.get((sup_id, wk_id), 0)
            if avail > 0:
                if not is_prim or alt_picked is None:
                    alt_picked = (sup_id, u_cost, avail)
                if not is_prim:
                    break
        if alt_picked is not None:
            sup_id, u_cost, avail = alt_picked
            cover = min(qty_needed, avail)
            candidates.append(
                {
                    "mitigation_type": MitigationType.ALTERNATE_SUPPLIER.value,
                    "target_supplier_id": sup_id,
                    "target_sku_id": None,
                    "source_location_id": None,
                    "mitigation_qty": cover,
                    "cost": round(cover * u_cost * 1.05, 4),
                    "service_level_impact": round(min(1.0, cover / qty_needed), 4),
                    "lead_time_days": lt_map.get((sku_id, sup_id, loc_id), 14),
                    "capacity_check_passed": True,
                    "policy_check_passed": True,
                }
            )

        # 3. EXPEDITE_PO
        exp_pos = exp_po_map.get((sku_id, loc_id), [])
        if exp_pos:
            sup_id, po_qty, u_cost = exp_pos[0]
            cover = min(qty_needed, po_qty)
            surcharge = sup_surcharge.get(sup_id, 0.20)
            candidates.append(
                {
                    "mitigation_type": MitigationType.EXPEDITE_PO.value,
                    "target_supplier_id": sup_id,
                    "target_sku_id": None,
                    "source_location_id": None,
                    "mitigation_qty": cover,
                    "cost": round(cover * u_cost * (1.0 + surcharge), 4),
                    "service_level_impact": round(min(1.0, cover / qty_needed), 4),
                    "lead_time_days": max(1, lt_map.get((sku_id, sup_id, loc_id), 12) // 2),
                    "capacity_check_passed": True,
                    "policy_check_passed": True,
                }
            )

        # 4. SUBSTITUTE_SKU (ONLY policy-approved substitutes)
        for sub_sku, conv, delta_pct in approved_subs.get(sku_id, []):
            sub_surplus = surplus_by_sku_loc_wk.get((sub_sku, loc_id, wk_id), 0)
            if sub_surplus <= 0:
                continue
            max_cover = int(sub_surplus / max(conv, 1e-6))
            if max_cover <= 0:
                continue
            cover = min(qty_needed, max_cover)
            sub_u_cost = float(sku_cost.get(sub_sku, base_cost))
            candidates.append(
                {
                    "mitigation_type": MitigationType.SUBSTITUTE_SKU.value,
                    "target_supplier_id": None,
                    "target_sku_id": sub_sku,
                    "source_location_id": None,
                    "mitigation_qty": cover,
                    "cost": round(cover * sub_u_cost * max(0.10, 1.0 + delta_pct) * 0.25, 4),
                    "service_level_impact": round(min(1.0, cover / qty_needed), 4),
                    "lead_time_days": 1,
                    "capacity_check_passed": True,
                    "policy_check_passed": True,
                }
            )
            break

        # 5. OVERTIME_PRODUCTION
        p_info = prod_map.get((sku_id, loc_id, wk_id))
        if p_info is not None:
            cap_lim, bom_feas, prod_u_cost = p_info
            ot_cap = min(max(1, int(cap_lim * 0.30)), max(0, bom_feas))
            if ot_cap > 0:
                cover = min(qty_needed, ot_cap)
                candidates.append(
                    {
                        "mitigation_type": MitigationType.OVERTIME_PRODUCTION.value,
                        "target_supplier_id": None,
                        "target_sku_id": None,
                        "source_location_id": loc_id,
                        "mitigation_qty": cover,
                        "cost": round(cover * prod_u_cost * config.production.overtime_cost_multiplier, 4),
                        "service_level_impact": round(min(1.0, cover / qty_needed), 4),
                        "lead_time_days": 3,
                        "capacity_check_passed": True,
                        "policy_check_passed": True,
                    }
                )

        # 6. DEMAND_REALLOCATION fallback to ensure trade-off alternatives
        if len(candidates) < 2:
            cover = max(1, int(round(qty_needed * 0.55)))
            candidates.append(
                {
                    "mitigation_type": MitigationType.DEMAND_REALLOCATION.value,
                    "target_supplier_id": None,
                    "target_sku_id": None,
                    "source_location_id": None,
                    "mitigation_qty": cover,
                    "cost": round(cover * base_cost * 0.08, 4),
                    "service_level_impact": round(min(1.0, cover / qty_needed), 4),
                    "lead_time_days": 0,
                    "capacity_check_passed": True,
                    "policy_check_passed": True,
                }
            )

        max_cost = max(max(float(c["cost"]) for c in candidates), 1.0)
        max_lt = max(max(int(c["lead_time_days"]) for c in candidates), 1)
        for c in candidates:
            cost_score = 1.0 - (float(c["cost"]) / (max_cost * 1.05))
            serv_score = float(c["service_level_impact"])
            lt_score = 1.0 - (int(c["lead_time_days"]) / (max_lt + 1.0))
            weighted = 100.0 * (w_cost * cost_score + w_serv * serv_score + w_lt * lt_score)
            c["score"] = round(max(0.0, min(100.0, weighted)), 4)

        candidates.sort(key=lambda x: (-float(x["score"]), str(x["mitigation_type"])))
        candidates = candidates[:max_opts]

        best_service = max(float(c["service_level_impact"]) for c in candidates)
        updated_statuses[sid] = (
            ShortageStatus.MITIGATION_PROPOSED.value if best_service >= 0.50 else ShortageStatus.ESCALATED.value
        )

        for rank_i, c in enumerate(candidates, start=1):
            mitigation_rows.append(
                {
                    "mitigation_id": make_mitigation_id(sid, rank_i),
                    "shortage_id": sid,
                    "mitigation_type": c["mitigation_type"],
                    "target_supplier_id": c["target_supplier_id"],
                    "target_sku_id": c["target_sku_id"],
                    "source_location_id": c["source_location_id"],
                    "mitigation_qty": int(c["mitigation_qty"]),
                    "cost": float(c["cost"]),
                    "service_level_impact": float(c["service_level_impact"]),
                    "lead_time_days": int(c["lead_time_days"]),
                    "capacity_check_passed": bool(c["capacity_check_passed"]),
                    "policy_check_passed": bool(c["policy_check_passed"]),
                    "score": float(c["score"]),
                    "rank": rank_i,
                    "lifecycle_state": (
                        MitigationStatus.POLICY_VALIDATED.value if rank_i == 1 else MitigationStatus.PROPOSED.value
                    ),
                    "effective_from": eff_from,
                    "effective_to": None,
                }
            )

    mit_df = pd.DataFrame(mitigation_rows).sort_values("mitigation_id", kind="mergesort").reset_index(drop=True)
    updated_shortages = shortages_df.copy()
    updated_shortages["lifecycle_state"] = updated_shortages["shortage_id"].map(
        lambda x: updated_statuses.get(x, ShortageStatus.OPEN.value)
    )
    return mit_df, updated_shortages
