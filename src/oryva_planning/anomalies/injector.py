"""Orchestrator invoking all 5 isolated anomaly injectors and emitting ground_truth.csv rows."""

from __future__ import annotations

import numpy as np
import pandas as pd

from oryva_planning.anomalies import (
    double_counted_inbound,
    shortage_without_lead_time,
    supplier_capacity_exceeded,
    unapproved_substitute,
    uom_mismatch,
)
from oryva_planning.config import PlanningConfig
from oryva_planning.schema.ground_truth import GROUND_TRUTH_COLUMNS
from oryva_planning.schema.ids import make_ground_truth_id


def inject_all_anomalies(
    config: PlanningConfig,
    rng: np.random.Generator,
    tables: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Apply all 5 labelled edge cases orthogonally and return (mutated_tables, ground_truth_df)."""
    out = {name: df.copy(deep=True) for name, df in tables.items()}
    year = config.planning_year
    eff_from = config.reference_date.isoformat()

    last_week_id = sorted(out["projected_balances"]["week_id"].unique())[-1]
    shortage_balance_ids = set(out["shortages"]["balance_id"].astype(str))
    used_po_ids: set[str] = set()
    used_balance_ids: set[str] = set()
    used_supplier_weeks: set[tuple[str, str]] = set()

    raw_records: list[dict[str, object]] = []
    raw_records.extend(
        double_counted_inbound.inject(
            out,
            rng,
            config.anomalies.double_counted_inbound,
            last_week_id,
            shortage_balance_ids,
            used_po_ids,
            used_balance_ids,
        )
    )
    raw_records.extend(
        unapproved_substitute.inject(
            out,
            rng,
            config.anomalies.unapproved_substitute,
            eff_from,
        )
    )
    raw_records.extend(
        supplier_capacity_exceeded.inject(
            out,
            config.anomalies.supplier_capacity_exceeded,
            last_week_id,
            shortage_balance_ids,
            used_po_ids,
            used_balance_ids,
            used_supplier_weeks,
        )
    )
    raw_records.extend(
        shortage_without_lead_time.inject(
            out,
            rng,
            config.anomalies.shortage_without_lead_time,
        )
    )
    raw_records.extend(
        uom_mismatch.inject(
            out,
            rng,
            config.anomalies.uom_mismatch,
            used_po_ids,
        )
    )

    gt_rows = []
    for seq, rec in enumerate(raw_records, start=1):
        gt_rows.append(
            {
                "ground_truth_id": make_ground_truth_id(year, seq),
                "issue_type": str(rec["issue_type"]),
                "target_table": str(rec["target_table"]),
                "affected_id": str(rec["affected_id"]),
                "related_ids": str(rec["related_ids"]),
                "expected_detection_rule": str(rec["expected_detection_rule"]),
                "injected_detail": str(rec["injected_detail"]),
            }
        )

    gt_df = (
        pd.DataFrame(gt_rows, columns=list(GROUND_TRUTH_COLUMNS))
        .sort_values("ground_truth_id", kind="mergesort")
        .reset_index(drop=True)
    )
    return out, gt_df
