"""Edge Case 2: Substitute SKU used without policy approval (`unapproved_substitute`)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from oryva_planning.schema.enums import EntityStatus, IssueType, MitigationStatus, MitigationType
from oryva_planning.schema.ids import make_mitigation_id, make_sku_substitute_id

DETECTION_RULE = (
    "mitigation_options.mitigation_type == 'SUBSTITUTE_SKU' AND "
    "(sku_substitutes.approved == False OR policy_check_passed == False)"
)


def inject(
    tables: dict[str, pd.DataFrame],
    rng: np.random.Generator,
    count: int,
    eff_from: str,
) -> list[dict[str, Any]]:
    sub_df = tables["sku_substitutes"]
    short_df = tables["shortages"]
    mit_df = tables["mitigation_options"]
    sku_df = tables["skus"]

    unapp_subs = sub_df[~sub_df["approved"]].sort_values("sku_substitute_id", kind="mergesort")
    unapp_by_sku: dict[str, list[tuple[str, str, float]]] = {}
    for r in unapp_subs.itertuples(index=False):
        unapp_by_sku.setdefault(r.sku_id, []).append(
            (r.sku_substitute_id, r.substitute_sku_id, float(r.cost_delta_pct))
        )

    eligible_shorts = short_df[short_df["sku_id"].isin(unapp_by_sku.keys())].sort_values(
        "shortage_id", kind="mergesort"
    )
    chosen_shorts = list(eligible_shorts.itertuples(index=False))
    if len(chosen_shorts) > count:
        s_picks = sorted(rng.choice(len(chosen_shorts), size=count, replace=False))
        chosen_shorts = [chosen_shorts[i] for i in s_picks]
    elif len(chosen_shorts) < count:
        existing_pairs = set(zip(sub_df["sku_id"], sub_df["substitute_sku_id"]))
        all_skus = sku_df["sku_id"].tolist()
        picked_sids = {s.shortage_id for s in chosen_shorts}
        new_sub_rows = []
        for s_row in short_df.sort_values("shortage_id", kind="mergesort").itertuples(index=False):
            if len(chosen_shorts) >= count:
                break
            if s_row.shortage_id in picked_sids:
                continue
            cand_sub = next(
                (x for x in all_skus if x != s_row.sku_id and (s_row.sku_id, x) not in existing_pairs),
                None,
            )
            if cand_sub is None:
                continue
            sub_id = make_sku_substitute_id(s_row.sku_id, cand_sub)
            existing_pairs.add((s_row.sku_id, cand_sub))
            new_sub_rows.append(
                {
                    "sku_substitute_id": sub_id,
                    "sku_id": s_row.sku_id,
                    "substitute_sku_id": cand_sub,
                    "approved": False,
                    "conversion_factor": 1.0,
                    "cost_delta_pct": 0.12,
                    "priority_rank": 3,
                    "effective_from": eff_from,
                    "effective_to": None,
                    "lifecycle_state": EntityStatus.ACTIVE.value,
                }
            )
            unapp_by_sku.setdefault(s_row.sku_id, []).append((sub_id, cand_sub, 0.12))
            chosen_shorts.append(s_row)
            picked_sids.add(s_row.shortage_id)
        if new_sub_rows:
            tables["sku_substitutes"] = (
                pd.concat([sub_df, pd.DataFrame(new_sub_rows)], ignore_index=True)
                .sort_values("sku_substitute_id", kind="mergesort")
                .reset_index(drop=True)
            )

    sku_cost_map = dict(zip(sku_df["sku_id"], sku_df["unit_cost"]))
    new_mit_rows: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []

    for s_row in chosen_shorts:
        sid = s_row.shortage_id
        sub_link_id, sub_sku_id, delta_pct = unapp_by_sku[s_row.sku_id][0]
        existing = mit_df[mit_df["shortage_id"] == sid]
        next_num = int(existing["rank"].max()) + 1 if not existing.empty else 1
        mit_id = make_mitigation_id(sid, next_num)
        qty = int(s_row.shortage_qty)
        cost = round(qty * float(sku_cost_map.get(sub_sku_id, 100.0)) * max(0.1, 1.0 + delta_pct) * 0.25, 4)

        new_mit_rows.append(
            {
                "mitigation_id": mit_id,
                "shortage_id": sid,
                "mitigation_type": MitigationType.SUBSTITUTE_SKU.value,
                "target_supplier_id": None,
                "target_sku_id": sub_sku_id,
                "source_location_id": None,
                "mitigation_qty": qty,
                "cost": cost,
                "service_level_impact": 1.0,
                "lead_time_days": 1,
                "capacity_check_passed": True,
                "policy_check_passed": False,
                "score": 45.0,
                "rank": next_num,
                "lifecycle_state": MitigationStatus.PROPOSED.value,
                "effective_from": eff_from,
                "effective_to": None,
            }
        )
        records.append(
            {
                "issue_type": IssueType.UNAPPROVED_SUBSTITUTE.value,
                "target_table": "mitigation_options",
                "affected_id": mit_id,
                "related_ids": ",".join(sorted({sid, sub_link_id, sub_sku_id})),
                "expected_detection_rule": DETECTION_RULE,
                "injected_detail": f"Injected mitigation using unapproved substitute {sub_sku_id} for {s_row.sku_id}",
            }
        )

    if new_mit_rows:
        tables["mitigation_options"] = (
            pd.concat([mit_df, pd.DataFrame(new_mit_rows)], ignore_index=True)
            .sort_values("mitigation_id", kind="mergesort")
            .reset_index(drop=True)
        )
    return records
