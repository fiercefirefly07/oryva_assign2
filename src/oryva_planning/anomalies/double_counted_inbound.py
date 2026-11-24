"""Edge Case 1: Inbound inventory counted twice (`double_counted_inbound`)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from oryva_planning.schema.enums import IssueType, POStatus

DETECTION_RULE = (
    "projected_balances.inbound_qty != SUM(active purchase_orders.order_qty "
    "for sku_id, location_id, arrival_week_id)"
)


def inject(
    tables: dict[str, pd.DataFrame],
    rng: np.random.Generator,
    count: int,
    last_week_id: str,
    shortage_balance_ids: set[str],
    used_po_ids: set[str],
    used_balance_ids: set[str],
) -> list[dict[str, Any]]:
    bal_df = tables["projected_balances"]
    po_df = tables["purchase_orders"]
    active_pos = po_df[po_df["current_status"] != POStatus.CANCELLED.value]

    candidates = bal_df[
        (bal_df["week_id"] == last_week_id)
        & (bal_df["inbound_qty"] > 0)
        & (~bal_df["balance_id"].isin(shortage_balance_ids))
        & (~bal_df["balance_id"].isin(used_balance_ids))
    ].sort_values("balance_id", kind="mergesort")
    if len(candidates) < count:
        candidates = bal_df[
            (bal_df["week_id"] == last_week_id)
            & (bal_df["inbound_qty"] > 0)
            & (~bal_df["balance_id"].isin(used_balance_ids))
        ].sort_values("balance_id", kind="mergesort")

    pick_idx = sorted(
        rng.choice(candidates.index.to_numpy(), size=min(count, len(candidates)), replace=False)
    )
    records: list[dict[str, Any]] = []
    for b_idx in pick_idx:
        row = bal_df.loc[b_idx]
        bid = str(row["balance_id"])
        orig_inb = int(row["inbound_qty"])
        linked_pos = active_pos[
            (active_pos["sku_id"] == row["sku_id"])
            & (active_pos["location_id"] == row["location_id"])
            & (active_pos["arrival_week_id"] == row["week_id"])
        ]["po_id"].tolist()

        bal_df.at[b_idx, "inbound_qty"] = orig_inb * 2
        new_closing = int(row["closing_stock"]) + orig_inb
        bal_df.at[b_idx, "closing_stock"] = new_closing
        bal_df.at[b_idx, "below_safety_stock"] = bool(new_closing < int(row["safety_stock_qty"]))

        used_balance_ids.add(bid)
        used_po_ids.update(linked_pos)
        records.append(
            {
                "issue_type": IssueType.DOUBLE_COUNTED_INBOUND.value,
                "target_table": "projected_balances",
                "affected_id": bid,
                "related_ids": ",".join(sorted(set(linked_pos))),
                "expected_detection_rule": DETECTION_RULE,
                "injected_detail": f"Doubled inbound_qty from {orig_inb} to {orig_inb * 2}",
            }
        )
    return records
