"""Phase 4 & 5 tests: ProjectedBalance reconciliation, Shortages, Evidence, and Mitigations."""

from __future__ import annotations

from oryva_planning.config import load_config
from oryva_planning.pipeline import run_pipeline


def test_planning_engine_reconciliation_evidence_and_mitigations() -> None:
    cfg = load_config("starter", seed_override=20261022)
    res = run_pipeline(cfg, export_outputs=False, validate_baseline=True)
    bt = res.baseline_tables

    bal = bt["projected_balances"]
    shorts = bt["shortages"]
    ev = bt["shortage_evidence"]
    mits = bt["mitigation_options"]

    # Exact week-by-week arithmetic equation
    assert (
        bal["closing_stock"]
        == bal["opening_stock"] + bal["inbound_qty"] + bal["production_qty"] - bal["demand_qty"]
    ).all()

    # Every shortage is backed by >= 2 evidence rows and explainable root_cause
    assert len(shorts) > 0
    assert shorts["root_cause"].notna().all()
    ev_counts = ev.groupby("shortage_id").size()
    assert (ev_counts >= 2).all()
    assert set(shorts["shortage_id"]) == set(ev["shortage_id"])

    # Every baseline mitigation passes policy and capacity checks with valid trade-off fields
    assert len(mits) >= len(shorts)
    assert mits["capacity_check_passed"].all()
    assert mits["policy_check_passed"].all()
    assert (mits["service_level_impact"].between(0.0, 1.0)).all()
    assert (mits["score"].between(0.0, 100.0)).all()
    assert set(shorts["shortage_id"]) == set(mits["shortage_id"])
