"""Phase 6 tests: All 5 labelled edge cases, orthogonal injection, detectors, and GT Wall."""

from __future__ import annotations

import ast
from pathlib import Path

from oryva_planning.config import PROJECT_ROOT, load_config
from oryva_planning.pipeline import run_pipeline
from oryva_planning.schema.enums import IssueType
from oryva_planning.schema.registry import FORBIDDEN_INPUT_COLUMNS


def test_all_five_anomalies_injected_and_detected_with_perfect_precision_recall() -> None:
    cfg = load_config("starter", seed_override=20261022)
    res = run_pipeline(cfg, export_outputs=False, validate_baseline=True)

    assert res.baseline_report.passed, f"Baseline failed: {res.baseline_report.failed_checks}"
    assert res.final_report.passed, f"Final failed: {res.final_report.failed_checks}"

    expected_counts = {
        IssueType.DOUBLE_COUNTED_INBOUND.value: cfg.anomalies.double_counted_inbound,
        IssueType.UNAPPROVED_SUBSTITUTE.value: cfg.anomalies.unapproved_substitute,
        IssueType.SUPPLIER_CAPACITY_EXCEEDED.value: cfg.anomalies.supplier_capacity_exceeded,
        IssueType.SHORTAGE_WITHOUT_LEAD_TIME.value: cfg.anomalies.shortage_without_lead_time,
        IssueType.UOM_MISMATCH.value: cfg.anomalies.uom_mismatch,
    }
    for issue_key, exp_n in expected_counts.items():
        m = res.detector_metrics[issue_key]
        assert m["expected"] == exp_n, f"Expected {exp_n} for {issue_key}, got {m}"
        assert m["tp"] == exp_n
        assert m["fp"] == 0
        assert m["fn"] == 0
        assert m["precision"] == 1.0
        assert m["recall"] == 1.0


def test_ground_truth_wall_columns_files_and_planning_ast(tmp_path: Path) -> None:
    cfg = load_config("starter", seed_override=20261022, output_dir_override=str(tmp_path / "data"))
    res = run_pipeline(cfg, export_outputs=True, output_dir=tmp_path / "data", validate_baseline=False)

    # 1. No ground-truth columns in any input table
    for name, df in res.final_tables.items():
        leaked = FORBIDDEN_INPUT_COLUMNS.intersection(df.columns)
        assert not leaked, f"Leaked columns {leaked} in {name}"

    # 2. Ground truth file lives strictly in data/ground_truth/, never data/inputs/
    assert (tmp_path / "data" / "ground_truth" / "ground_truth.csv").exists()
    input_files = [p.name.lower() for p in (tmp_path / "data" / "inputs").rglob("*") if p.is_file()]
    assert not any("ground_truth" in f for f in input_files)

    # 3. Static AST check: planning/ never imports ground_truth or anomalies
    planning_dir = PROJECT_ROOT / "src" / "oryva_planning" / "planning"
    for py_file in sorted(planning_dir.glob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "ground_truth" not in alias.name
                    assert "anomalies" not in alias.name
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert "ground_truth" not in mod
                assert "anomalies" not in mod
