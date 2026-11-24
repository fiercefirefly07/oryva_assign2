"""Edge Case 4: Shortage calculated without lead time (`shortage_without_lead_time`)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from oryva_planning.schema.enums import IssueType

DETECTION_RULE = (
    "lead_times.min_total_lead_time_days > 0 AND (shortages.lead_time_days_used == 0 "
    "OR (week_start_date - required_order_by_date) < min_total_lead_time_days)"
)


def inject(
    tables: dict[str, pd.DataFrame],
    rng: np.random.Generator,
    count: int,
) -> list[dict[str, Any]]:
    short_df = tables["shortages"]
    lt_df = tables["lead_times"]

    lt_shorts = short_df[short_df["lead_time_days_used"] > 0].sort_values(
        "shortage_id", kind="mergesort"
    )
    picks = sorted(
        rng.choice(lt_shorts.index.to_numpy(), size=min(count, len(lt_shorts)), replace=False)
    )
    min_lt_lookup = (
        lt_df.sort_values(["sku_id", "location_id", "total_lead_time_days", "lead_time_id"], kind="mergesort")
        .drop_duplicates(subset=["sku_id", "location_id"], keep="first")
        .set_index(["sku_id", "location_id"])["lead_time_id"]
        .to_dict()
    )

    records: list[dict[str, Any]] = []
    for s_idx in picks:
        sid = str(short_df.at[s_idx, "shortage_id"])
        old_lt = int(short_df.at[s_idx, "lead_time_days_used"])
        wk_start = str(short_df.at[s_idx, "week_start_date"])
        lt_id = str(min_lt_lookup.get((short_df.at[s_idx, "sku_id"], short_df.at[s_idx, "location_id"]), ""))

        short_df.at[s_idx, "lead_time_days_used"] = 0
        short_df.at[s_idx, "required_order_by_date"] = wk_start
        records.append(
            {
                "issue_type": IssueType.SHORTAGE_WITHOUT_LEAD_TIME.value,
                "target_table": "shortages",
                "affected_id": sid,
                "related_ids": lt_id,
                "expected_detection_rule": DETECTION_RULE,
                "injected_detail": (
                    f"Zeroed lead_time_days_used (was {old_lt}d) and set "
                    f"required_order_by_date = week_start_date ({wk_start})"
                ),
            }
        )
    return records
