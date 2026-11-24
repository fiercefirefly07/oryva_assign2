"""Edge Case 3: PO volume exceeds weekly supplier capacity (`supplier_capacity_exceeded`)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from oryva_planning.schema.enums import IssueType, POStatus

DETECTION_RULE = (
    "SUM(active purchase_orders.order_qty for supplier_id, arrival_week_id) "
    "> supplier_capacity.max_weekly_capacity OR available_capacity < 0"
)


def inject(
    tables: dict[str, pd.DataFrame],
    count: int,
    last_week_id: str,
    shortage_balance_ids: set[str],
    used_po_ids: set[str],
    used_balance_ids: set[str],
    used_supplier_weeks: set[tuple[str, str]],
) -> list[dict[str, Any]]:
    po_df = tables["purchase_orders"]
    bal_df = tables["projected_balances"]
    cap_df = tables["supplier_capacity"]

    # Filter to last_week_id first for O(N_pairs) performance even at 7.8M balance rows
    w_last_bal = bal_df[bal_df["week_id"] == last_week_id]
    bal_idx_map: dict[tuple[str, str, str], tuple[int, str]] = {
        (r.sku_id, r.location_id, r.week_id): (int(idx), str(r.balance_id))
        for idx, r in zip(w_last_bal.index, w_last_bal.itertuples(index=False))
    }
    w_last_cap = cap_df[cap_df["week_id"] == last_week_id]
    cap_idx_map: dict[tuple[str, str], int] = {
        (r.supplier_id, r.week_id): int(idx)
        for idx, r in zip(w_last_cap.index, w_last_cap.itertuples(index=False))
    }

    w_last_pos = po_df[
        (po_df["arrival_week_id"] == last_week_id)
        & (po_df["current_status"] != POStatus.CANCELLED.value)
        & (~po_df["po_id"].isin(used_po_ids))
    ].sort_values("po_id", kind="mergesort")

    candidates: list[int] = []
    seen_sw: set[tuple[str, str]] = set()
    for po_idx, p_row in w_last_pos.iterrows():
        b_key = (p_row["sku_id"], p_row["location_id"], p_row["arrival_week_id"])
        sw_key = (p_row["supplier_id"], p_row["arrival_week_id"])
        if sw_key in seen_sw or sw_key in used_supplier_weeks:
            continue
        if b_key not in bal_idx_map or sw_key not in cap_idx_map:
            continue
        _, bid = bal_idx_map[b_key]
        if bid in used_balance_ids or bid in shortage_balance_ids:
            continue
        seen_sw.add(sw_key)
        candidates.append(int(po_idx))
        if len(candidates) >= count:
            break

    records: list[dict[str, Any]] = []
    for po_idx in candidates[:count]:
        p_row = po_df.loc[po_idx]
        po_id = str(p_row["po_id"])
        sup_id = str(p_row["supplier_id"])
        wk_id = str(p_row["arrival_week_id"])
        sku_id = str(p_row["sku_id"])
        loc_id = str(p_row["location_id"])

        c_idx = cap_idx_map[(sup_id, wk_id)]
        b_idx, bid = bal_idx_map[(sku_id, loc_id, wk_id)]

        max_cap = int(cap_df.at[c_idx, "max_weekly_capacity"])
        avail_cap = int(cap_df.at[c_idx, "available_capacity"])
        overrun = max(30, int(round(max_cap * 0.25)))
        delta_qty = avail_cap + overrun

        old_qty = int(po_df.at[po_idx, "order_qty"])
        new_qty = old_qty + delta_qty
        unit_cost = float(po_df.at[po_idx, "unit_cost"])

        po_df.at[po_idx, "order_qty"] = new_qty
        po_df.at[po_idx, "total_cost"] = round(new_qty * unit_cost, 4)

        new_committed = int(cap_df.at[c_idx, "committed_qty"]) + delta_qty
        cap_df.at[c_idx, "committed_qty"] = new_committed
        cap_df.at[c_idx, "available_capacity"] = max_cap - new_committed

        # Keep projected_balances strictly reconciled so double_counted_inbound stays orthogonal
        bal_df.at[b_idx, "inbound_qty"] = int(bal_df.at[b_idx, "inbound_qty"]) + delta_qty
        new_close = int(bal_df.at[b_idx, "closing_stock"]) + delta_qty
        bal_df.at[b_idx, "closing_stock"] = new_close
        bal_df.at[b_idx, "below_safety_stock"] = bool(new_close < int(bal_df.at[b_idx, "safety_stock_qty"]))

        cap_id = str(cap_df.at[c_idx, "capacity_id"])
        used_po_ids.add(po_id)
        used_balance_ids.add(bid)
        used_supplier_weeks.add((sup_id, wk_id))
        records.append(
            {
                "issue_type": IssueType.SUPPLIER_CAPACITY_EXCEEDED.value,
                "target_table": "supplier_capacity",
                "affected_id": cap_id,
                "related_ids": ",".join(sorted({po_id, sup_id})),
                "expected_detection_rule": DETECTION_RULE,
                "injected_detail": (
                    f"Increased {po_id} qty from {old_qty} to {new_qty}; "
                    f"committed={new_committed} > max_weekly_capacity={max_cap}"
                ),
            }
        )
    return records
