"""Independent anomaly detectors (never read ground_truth) and precision/recall evaluator."""

from __future__ import annotations

from datetime import date

import pandas as pd

from oryva_planning.schema.enums import IssueType, MitigationType, POStatus


def detect_double_counted_inbound(tables: dict[str, pd.DataFrame]) -> set[str]:
    bal = tables["projected_balances"]
    pos = tables["purchase_orders"]
    active = pos[pos["current_status"] != POStatus.CANCELLED.value]
    expected = (
        active.groupby(["sku_id", "location_id", "arrival_week_id"], as_index=False)["order_qty"]
        .sum()
        .rename(columns={"arrival_week_id": "week_id", "order_qty": "expected_inbound"})
    )
    bal_pos = bal.loc[bal["inbound_qty"] > 0, ["balance_id", "sku_id", "location_id", "week_id", "inbound_qty"]]
    merged = bal_pos.merge(expected, on=["sku_id", "location_id", "week_id"], how="left")
    merged["expected_inbound"] = merged["expected_inbound"].fillna(0).astype(int)
    flagged = merged[merged["inbound_qty"] > merged["expected_inbound"]]
    return set(flagged["balance_id"].astype(str))


def detect_unapproved_substitute(tables: dict[str, pd.DataFrame]) -> set[str]:
    mit = tables["mitigation_options"]
    shorts = tables["shortages"][["shortage_id", "sku_id"]]
    subs = tables["sku_substitutes"][["sku_id", "substitute_sku_id", "approved"]]

    sub_mits = mit[mit["mitigation_type"] == MitigationType.SUBSTITUTE_SKU.value].copy()
    if sub_mits.empty:
        return set()

    joined = sub_mits.merge(shorts, on="shortage_id", how="left").merge(
        subs, left_on=["sku_id", "target_sku_id"], right_on=["sku_id", "substitute_sku_id"], how="left"
    )
    flagged = joined[
        (joined["approved"] != True) | (joined["policy_check_passed"] != True)  # noqa: E712
    ]
    return set(flagged["mitigation_id"].astype(str))


def detect_supplier_capacity_exceeded(tables: dict[str, pd.DataFrame]) -> set[str]:
    cap = tables["supplier_capacity"]
    pos = tables["purchase_orders"]
    active = pos[pos["current_status"] != POStatus.CANCELLED.value]
    booked = (
        active.groupby(["supplier_id", "arrival_week_id"], as_index=False)["order_qty"]
        .sum()
        .rename(columns={"arrival_week_id": "week_id", "order_qty": "actual_booked"})
    )
    merged = cap[
        ["capacity_id", "supplier_id", "week_id", "max_weekly_capacity", "available_capacity"]
    ].merge(booked, on=["supplier_id", "week_id"], how="left")
    merged["actual_booked"] = merged["actual_booked"].fillna(0).astype(int)
    flagged = merged[
        (merged["actual_booked"] > merged["max_weekly_capacity"]) | (merged["available_capacity"] < 0)
    ]
    return set(flagged["capacity_id"].astype(str))


def detect_shortage_without_lead_time(tables: dict[str, pd.DataFrame]) -> set[str]:
    shorts = tables["shortages"]
    lts = tables["lead_times"]
    if shorts.empty or lts.empty:
        return set()

    min_lt = (
        lts.groupby(["sku_id", "location_id"], as_index=False)["total_lead_time_days"]
        .min()
        .rename(columns={"total_lead_time_days": "min_lt_days"})
    )
    merged = shorts[
        ["shortage_id", "sku_id", "location_id", "week_start_date", "lead_time_days_used", "required_order_by_date"]
    ].merge(min_lt, on=["sku_id", "location_id"], how="inner")

    flagged: set[str] = set()
    for r in merged.itertuples(index=False):
        if int(r.min_lt_days) <= 0:
            continue
        wk_dt = date.fromisoformat(str(r.week_start_date))
        ord_dt = date.fromisoformat(str(r.required_order_by_date))
        if int(r.lead_time_days_used) == 0 or (wk_dt - ord_dt).days < int(r.min_lt_days):
            flagged.add(str(r.shortage_id))
    return flagged


def detect_uom_mismatch(tables: dict[str, pd.DataFrame]) -> set[str]:
    pos = tables["purchase_orders"][["po_id", "sku_id", "uom"]]
    skus = tables["skus"][["sku_id", "base_uom"]]
    merged = pos.merge(skus, on="sku_id", how="left")
    flagged = merged[merged["uom"] != merged["base_uom"]]
    return set(flagged["po_id"].astype(str))


def run_all_detectors(tables: dict[str, pd.DataFrame]) -> dict[str, set[str]]:
    return {
        IssueType.DOUBLE_COUNTED_INBOUND.value: detect_double_counted_inbound(tables),
        IssueType.UNAPPROVED_SUBSTITUTE.value: detect_unapproved_substitute(tables),
        IssueType.SUPPLIER_CAPACITY_EXCEEDED.value: detect_supplier_capacity_exceeded(tables),
        IssueType.SHORTAGE_WITHOUT_LEAD_TIME.value: detect_shortage_without_lead_time(tables),
        IssueType.UOM_MISMATCH.value: detect_uom_mismatch(tables),
    }


def evaluate_detectors(
    detected: dict[str, set[str]],
    ground_truth_df: pd.DataFrame,
) -> dict[str, dict[str, float | int]]:
    metrics: dict[str, dict[str, float | int]] = {}
    total_tp = total_fp = total_fn = 0

    for issue in IssueType:
        key = issue.value
        actual = set(ground_truth_df[ground_truth_df["issue_type"] == key]["affected_id"].astype(str))
        pred = detected.get(key, set())
        tp = len(actual & pred)
        fp = len(pred - actual)
        fn = len(actual - pred)
        prec = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
        metrics[key] = {
            "expected": len(actual),
            "detected": len(pred),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
        }
        total_tp += tp
        total_fp += fp
        total_fn += fn

    overall_p = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 1.0
    overall_r = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 1.0
    overall_f1 = 2 * overall_p * overall_r / (overall_p + overall_r) if (overall_p + overall_r) > 0 else 0.0
    metrics["overall"] = {
        "expected": total_tp + total_fn,
        "detected": total_tp + total_fp,
        "tp": total_tp,
        "fp": total_fp,
        "fn": total_fn,
        "precision": round(overall_p, 4),
        "recall": round(overall_r, 4),
        "f1": round(overall_f1, 4),
    }
    return metrics
