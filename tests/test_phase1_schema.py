"""Phase 1 tests: single-source schema registry, enums, ID builders, configs, and SQL DDL."""

from __future__ import annotations

from oryva_planning.config import get_planning_weeks, load_config
from oryva_planning.schema.ids import (
    make_balance_id,
    make_bom_id,
    make_capacity_id,
    make_demand_id,
    make_evidence_id,
    make_ground_truth_id,
    make_inventory_id,
    make_lead_time_id,
    make_location_id,
    make_mitigation_id,
    make_po_event_id,
    make_po_id,
    make_production_id,
    make_shortage_id,
    make_sku_id,
    make_sku_substitute_id,
    make_sku_supplier_id,
    make_supplier_id,
    make_week_id,
    validate_id,
)
from oryva_planning.schema.registry import ENTITY_ORDER, ENTITY_REGISTRY, generate_full_sql_ddl


def test_registry_contains_all_11_core_and_6_supporting_tables() -> None:
    expected = {
        "skus",
        "locations",
        "suppliers",
        "sku_suppliers",
        "sku_substitutes",
        "bom_items",
        "forecast_demand",
        "inventory",
        "supplier_capacity",
        "lead_times",
        "purchase_orders",
        "purchase_order_events",
        "production_plans",
        "projected_balances",
        "shortages",
        "shortage_evidence",
        "mitigation_options",
    }
    assert set(ENTITY_ORDER) == expected
    for tbl, spec in ENTITY_REGISTRY.items():
        cols = spec.column_names()
        assert spec.primary_key in cols
        assert "effective_from" in cols
        assert "effective_to" in cols
        assert spec.lifecycle_column in cols


def test_id_formats_match_assignment_specification() -> None:
    sku = make_sku_id(1)
    loc = make_location_id(1)
    sup = make_supplier_id(1)
    wk = make_week_id(2026, 1)
    dem = make_demand_id(sku, loc, wk)
    po = make_po_id(2026, 1)
    short = make_shortage_id(2026, 1)
    mit = make_mitigation_id(short, 1)

    assert sku == "SKU-000001"
    assert dem == "DEM-SKU-000001-LOC-0001-2026W01"
    assert po == "PO-2026-000001"
    assert short == "SHORT-2026-000001"
    assert mit == "MIT-SHORT-2026-000001-01"

    checks = {
        "sku_id": sku,
        "location_id": loc,
        "supplier_id": sup,
        "week_id": wk,
        "demand_id": dem,
        "inventory_id": make_inventory_id(sku, loc),
        "capacity_id": make_capacity_id(sup, wk),
        "lead_time_id": make_lead_time_id(sku, sup, loc),
        "po_id": po,
        "event_id": make_po_event_id(2026, 1),
        "production_id": make_production_id(2026, 1),
        "balance_id": make_balance_id(sku, loc, wk),
        "shortage_id": short,
        "mitigation_id": mit,
        "evidence_id": make_evidence_id(2026, 1),
        "sku_supplier_id": make_sku_supplier_id(sku, sup),
        "sku_substitute_id": make_sku_substitute_id(sku, make_sku_id(2)),
        "bom_id": make_bom_id(sku, make_sku_id(2)),
        "ground_truth_id": make_ground_truth_id(2026, 1),
    }
    for kind, val in checks.items():
        assert validate_id(kind, val), f"{kind} failed regex: {val}"


def test_starter_and_full_configs_and_sql_ddl() -> None:
    starter = load_config("starter")
    full = load_config("full")
    assert starter.seed == 20261022
    assert starter.scale.num_skus == 50
    assert starter.scale.num_locations == 5
    assert full.scale.num_skus == 3000
    assert full.scale.num_locations == 50
    assert full.scale.num_suppliers == 500
    assert full.scale.num_purchase_orders == 10000
    assert len(get_planning_weeks(2026, 1, 52)) == 52

    ddl = generate_full_sql_ddl()
    for tbl in ENTITY_ORDER:
        assert f"CREATE TABLE {tbl}" in ddl
