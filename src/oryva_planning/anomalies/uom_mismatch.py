"""Edge Case 5: Units-of-measure mismatch between PO and SKU master (`uom_mismatch`)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from oryva_planning.schema.enums import IssueType, UOM

DETECTION_RULE = "purchase_orders.uom != skus.base_uom"

_UOM_SWAP: dict[str, str] = {
    UOM.EA.value: UOM.CASE.value,
    UOM.CASE.value: UOM.PALLET.value,
    UOM.PALLET.value: UOM.EA.value,
    UOM.KG.value: UOM.L.value,
    UOM.L.value: UOM.KG.value,
}


def inject(
    tables: dict[str, pd.DataFrame],
    rng: np.random.Generator,
    count: int,
    used_po_ids: set[str],
) -> list[dict[str, Any]]:
    po_df = tables["purchase_orders"]
    candidates = po_df[~po_df["po_id"].isin(used_po_ids)].sort_values("po_id", kind="mergesort")
    picks = sorted(
        rng.choice(candidates.index.to_numpy(), size=min(count, len(candidates)), replace=False)
    )

    records: list[dict[str, Any]] = []
    for po_idx in picks:
        po_id = str(po_df.at[po_idx, "po_id"])
        sku_id = str(po_df.at[po_idx, "sku_id"])
        orig_uom = str(po_df.at[po_idx, "uom"])
        bad_uom = _UOM_SWAP[orig_uom]
        po_df.at[po_idx, "uom"] = bad_uom
        used_po_ids.add(po_id)
        records.append(
            {
                "issue_type": IssueType.UOM_MISMATCH.value,
                "target_table": "purchase_orders",
                "affected_id": po_id,
                "related_ids": sku_id,
                "expected_detection_rule": DETECTION_RULE,
                "injected_detail": f"Changed PO uom from {orig_uom} to {bad_uom} (SKU base_uom={orig_uom})",
            }
        )
    return records
