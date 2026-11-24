"""End-to-end validation orchestrator (SQL checks, lifecycle, GT wall, detector metrics)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from oryva_planning.anomalies.detectors import evaluate_detectors, run_all_detectors
from oryva_planning.schema.enums import PO_TRANSITIONS, POStatus
from oryva_planning.schema.registry import ENTITY_ORDER, ENTITY_REGISTRY, FORBIDDEN_INPUT_COLUMNS
from oryva_planning.validation.sql_checks import run_sql_checks


@dataclass
class ValidationCheckResult:
    category: str
    check: str
    passed: bool
    violations: int
    details: str = ""


@dataclass
class ValidationReport:
    sql_backend: str
    checks: list[ValidationCheckResult] = field(default_factory=list)
    detector_metrics: dict[str, dict[str, float | int]] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def failed_checks(self) -> list[ValidationCheckResult]:
        return [c for c in self.checks if not c.passed]

    def to_markdown(self, title: str = "Validation Summary") -> str:
        total = len(self.checks)
        passed_cnt = sum(1 for c in self.checks if c.passed)
        lines = [
            f"# {title}",
            "",
            f"- **SQL Engine**: `{self.sql_backend}`",
            f"- **Overall Status**: {'PASS' if self.passed else 'FAIL'} ({passed_cnt}/{total} checks passed)",
            "",
            "## Check Results by Category",
            "",
            "| Category | Check | Status | Violations | Rule |",
            "|---|---|---|---|---|",
        ]
        for c in self.checks:
            status = "PASS" if c.passed else "FAIL"
            lines.append(
                f"| `{c.category}` | `{c.check}` | **{status}** | {c.violations} | {c.details} |"
            )

        if self.detector_metrics:
            lines.extend(
                [
                    "",
                    "## Anomaly Detector Precision & Recall",
                    "",
                    "| Issue Type | Expected | Detected | TP | FP | FN | Precision | Recall | F1 |",
                    "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
                ]
            )
            for issue_type, m in self.detector_metrics.items():
                lines.append(
                    f"| `{issue_type}` | {m['expected']} | {m['detected']} | {m['tp']} | {m['fp']} "
                    f"| {m['fn']} | {m['precision']:.4f} | {m['recall']:.4f} | {m['f1']:.4f} |"
                )
        lines.append("")
        return "\n".join(lines)


def _check_po_lifecycle_transitions(
    po_df: pd.DataFrame, events_df: pd.DataFrame
) -> list[ValidationCheckResult]:
    seq_violations = trans_violations = ts_violations = status_mismatch = 0
    po_status_map = dict(zip(po_df["po_id"], po_df["current_status"]))
    grouped = events_df.sort_values(["po_id", "sequence_num"], kind="mergesort").groupby("po_id", sort=False)

    seen_pos: set[str] = set()
    for po_id, grp in grouped:
        seen_pos.add(str(po_id))
        seqs = grp["sequence_num"].tolist()
        if seqs != list(range(1, len(seqs) + 1)):
            seq_violations += 1
        ts_list = grp["event_ts"].tolist()
        if any(ts_list[i] < ts_list[i - 1] for i in range(1, len(ts_list))):
            ts_violations += 1

        prev_state: POStatus | None = None
        for r in grp.itertuples(index=False):
            from_s = POStatus(r.from_status) if pd.notna(r.from_status) else None
            to_s = POStatus(r.to_status)
            if from_s != prev_state or to_s not in PO_TRANSITIONS.get(from_s, frozenset()):
                trans_violations += 1
            prev_state = to_s

        if prev_state is None or po_status_map.get(str(po_id)) != prev_state.value:
            status_mismatch += 1

    missing_events = len(set(po_status_map.keys()) - seen_pos)
    return [
        ValidationCheckResult("lifecycle", "po_events_present", missing_events == 0, missing_events, "Every PurchaseOrder has >= 1 PurchaseOrderEvent"),
        ValidationCheckResult("lifecycle", "po_event_sequence_monotonic", seq_violations == 0, seq_violations, "sequence_num contiguous 1..k per po_id"),
        ValidationCheckResult("lifecycle", "po_event_timestamps_ordered", ts_violations == 0, ts_violations, "event_ts non-decreasing per po_id"),
        ValidationCheckResult("lifecycle", "po_state_transitions_valid", trans_violations == 0, trans_violations, "Every transition obeys PO_TRANSITIONS"),
        ValidationCheckResult("lifecycle", "po_current_status_derived_from_latest_event", status_mismatch == 0, status_mismatch, "current_status == latest event to_status"),
    ]


def _check_ground_truth_wall(tables: dict[str, pd.DataFrame]) -> ValidationCheckResult:
    leaks = [f"{n}:{sorted(FORBIDDEN_INPUT_COLUMNS.intersection(df.columns))}" for n, df in tables.items() if FORBIDDEN_INPUT_COLUMNS.intersection(df.columns)]
    return ValidationCheckResult(
        "ground_truth_wall",
        "no_ground_truth_columns_in_inputs",
        len(leaks) == 0,
        len(leaks),
        "Input tables must never contain issue_type or ground_truth columns" + (f" (leaked: {leaks})" if leaks else ""),
    )


def _check_evidence_targets_exist(tables: dict[str, pd.DataFrame]) -> ValidationCheckResult:
    ev = tables["shortage_evidence"]
    if ev.empty:
        return ValidationCheckResult("foreign_key", "shortage_evidence_polymorphic_fk", True, 0, "Every evidence record links to an existing source row")
    missing = 0
    for src_table, grp in ev.groupby("source_table", sort=True):
        if src_table not in ENTITY_REGISTRY or src_table not in tables:
            missing += len(grp)
            continue
        pk_col = ENTITY_REGISTRY[src_table].primary_key
        valid_ids = set(tables[src_table][pk_col].astype(str))
        missing += int((~grp["source_record_id"].astype(str).isin(valid_ids)).sum())
    return ValidationCheckResult("foreign_key", "shortage_evidence_polymorphic_fk", missing == 0, missing, "Every shortage_evidence.source_record_id exists in source_table")


def validate_tables(
    tables: dict[str, pd.DataFrame],
    ground_truth_df: pd.DataFrame | None = None,
    expect_clean_baseline: bool = False,
) -> ValidationReport:
    backend, sql_dicts = run_sql_checks(tables)
    checks = [ValidationCheckResult(**d) for d in sql_dicts]
    checks.extend(_check_po_lifecycle_transitions(tables["purchase_orders"], tables["purchase_order_events"]))
    checks.append(_check_ground_truth_wall(tables))
    checks.append(_check_evidence_targets_exist(tables))

    detected = run_all_detectors(tables)
    detector_metrics: dict[str, dict[str, float | int]] = {}

    if expect_clean_baseline:
        for issue_type, flagged in detected.items():
            checks.append(
                ValidationCheckResult(
                    "baseline_cleanliness",
                    f"zero_baseline_{issue_type}",
                    len(flagged) == 0,
                    len(flagged),
                    f"Clean baseline must have 0 {issue_type} anomalies before injection",
                )
            )
    elif ground_truth_df is not None:
        detector_metrics = evaluate_detectors(detected, ground_truth_df)
        overall = detector_metrics["overall"]
        exact_match = (overall["fp"] == 0) and (overall["fn"] == 0)
        checks.append(
            ValidationCheckResult(
                "anomaly_detection",
                "detectors_exact_precision_recall",
                exact_match,
                int(overall["fp"]) + int(overall["fn"]),
                f"Detectors matched ground truth with P={overall['precision']:.4f}, R={overall['recall']:.4f}",
            )
        )

    return ValidationReport(sql_backend=backend, checks=checks, detector_metrics=detector_metrics)


def validate_data_directory(data_dir: str | Path) -> ValidationReport:
    base = Path(data_dir)
    csv_dir = base / "inputs" / "csv"
    gt_path = base / "ground_truth" / "ground_truth.csv"

    tables: dict[str, pd.DataFrame] = {}
    for tbl in ENTITY_ORDER:
        path = csv_dir / f"{tbl}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Missing expected table CSV: {path}")
        tables[tbl] = pd.read_csv(path, keep_default_na=True)

    gt_df = pd.read_csv(gt_path) if gt_path.exists() else None
    report = validate_tables(tables, ground_truth_df=gt_df, expect_clean_baseline=False)

    leaked_files = [
        str(p.relative_to(base))
        for p in (base / "inputs").rglob("*")
        if p.is_file() and "ground_truth" in p.name.lower()
    ]
    report.checks.append(
        ValidationCheckResult(
            "ground_truth_wall",
            "no_ground_truth_files_in_inputs_dir",
            len(leaked_files) == 0,
            len(leaked_files),
            "data/inputs/ must not contain any ground_truth files",
        )
    )
    return report
