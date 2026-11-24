"""SQL validation queries executed via DuckDB (with automatic SQLite fallback)."""

from __future__ import annotations

import sqlite3
from typing import Any

import pandas as pd

from oryva_planning.schema.registry import ENTITY_ORDER, ENTITY_REGISTRY

try:
    import duckdb  # type: ignore
except ImportError:  # pragma: no cover
    duckdb = None


def _normalize_df_for_sql(table_name: str, df: pd.DataFrame) -> pd.DataFrame:
    """Ensure all nullable string/date columns have string dtype so DuckDB always binds VARCHAR."""
    spec = ENTITY_REGISTRY[table_name]
    out = df.copy()
    for field in spec.fields:
        if field.name not in out.columns:
            continue
        if field.dtype in ("str", "date", "datetime"):
            out[field.name] = out[field.name].astype("string")
    return out


class SQLValidationRunner:
    def __init__(self, tables: dict[str, pd.DataFrame]) -> None:
        self.tables = tables
        self._normalized: dict[str, pd.DataFrame] = {}
        if duckdb is not None:
            self.backend = "duckdb"
            self._conn: Any = duckdb.connect(database=":memory:")
            for name in ENTITY_ORDER:
                if name in tables:
                    norm = _normalize_df_for_sql(name, tables[name])
                    self._normalized[name] = norm
                    self._conn.register(name, norm)
        else:
            self.backend = "sqlite3"
            self._conn = sqlite3.connect(":memory:")
            for name in ENTITY_ORDER:
                if name in tables:
                    norm = _normalize_df_for_sql(name, tables[name])
                    self._normalized[name] = norm
                    norm.to_sql(name, self._conn, index=False, if_exists="replace")

    def scalar(self, sql: str) -> int:
        row = self._conn.execute(sql).fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    def close(self) -> None:
        self._conn.close()


def run_sql_checks(tables: dict[str, pd.DataFrame]) -> tuple[str, list[dict[str, Any]]]:
    runner = SQLValidationRunner(tables)
    results: list[dict[str, Any]] = []

    def _add(category: str, name: str, sql: str, details: str = "") -> None:
        violations = runner.scalar(sql)
        results.append(
            {
                "category": category,
                "check": name,
                "passed": violations == 0,
                "violations": violations,
                "details": details,
            }
        )

    try:
        for tbl in ENTITY_ORDER:
            spec = ENTITY_REGISTRY[tbl]
            pk = spec.primary_key
            _add(
                "primary_key",
                f"pk_unique_nonnull:{tbl}",
                (
                    f"SELECT (COUNT(*) - COUNT(DISTINCT {pk})) "
                    f"+ COALESCE(SUM(CASE WHEN {pk} IS NULL THEN 1 ELSE 0 END), 0) FROM {tbl}"
                ),
                f"PK {pk} must be non-null and unique",
            )

        for tbl in ENTITY_ORDER:
            spec = ENTITY_REGISTRY[tbl]
            for fk in spec.foreign_keys:
                _add(
                    "foreign_key",
                    f"fk:{tbl}.{fk.column}->{fk.ref_table}.{fk.ref_column}",
                    (
                        f"SELECT COUNT(*) FROM {tbl} c "
                        f"LEFT JOIN {fk.ref_table} p ON CAST(c.{fk.column} AS VARCHAR) = CAST(p.{fk.ref_column} AS VARCHAR) "
                        f"WHERE c.{fk.column} IS NOT NULL AND p.{fk.ref_column} IS NULL"
                    ),
                    f"Every non-null {tbl}.{fk.column} must exist in {fk.ref_table}.{fk.ref_column}",
                )

        for tbl in ENTITY_ORDER:
            spec = ENTITY_REGISTRY[tbl]
            for field in spec.enum_fields():
                assert field.enum_cls is not None
                allowed_sql = ", ".join(f"'{m.value}'" for m in field.enum_cls)
                _add(
                    "enum",
                    f"enum:{tbl}.{field.name}",
                    f"SELECT COUNT(*) FROM {tbl} WHERE {field.name} IS NOT NULL AND CAST({field.name} AS VARCHAR) NOT IN ({allowed_sql})",
                    f"Values must be in {field.enum_cls.__name__}",
                )

        for tbl in ENTITY_ORDER:
            _add(
                "date_ordering",
                f"effective_dates:{tbl}",
                f"SELECT COUNT(*) FROM {tbl} WHERE effective_to IS NOT NULL AND CAST(effective_to AS VARCHAR) < CAST(effective_from AS VARCHAR)",
                "effective_to must be NULL or >= effective_from",
            )

        _add(
            "date_ordering",
            "po_date_order",
            (
                "SELECT COUNT(*) FROM purchase_orders "
                "WHERE CAST(promised_delivery_date AS VARCHAR) < CAST(order_date AS VARCHAR) "
                "OR (actual_delivery_date IS NOT NULL AND CAST(actual_delivery_date AS VARCHAR) < CAST(order_date AS VARCHAR))"
            ),
            "order_date <= promised_delivery_date and actual_delivery_date >= order_date",
        )
        _add(
            "date_ordering",
            "shortage_order_by_date",
            "SELECT COUNT(*) FROM shortages WHERE CAST(required_order_by_date AS VARCHAR) > CAST(week_start_date AS VARCHAR)",
            "required_order_by_date <= week_start_date",
        )

        _add(
            "reconciliation",
            "inventory_available_qty",
            "SELECT COUNT(*) FROM inventory WHERE available_qty != (on_hand_qty - reserved_qty) OR reserved_qty > on_hand_qty",
            "available_qty = on_hand_qty - reserved_qty",
        )
        _add(
            "reconciliation",
            "lead_time_total_days",
            "SELECT COUNT(*) FROM lead_times WHERE total_lead_time_days != (manufacturing_days + transit_days + customs_buffer_days)",
            "total_lead_time_days = manufacturing + transit + customs",
        )
        _add(
            "reconciliation",
            "po_total_cost",
            "SELECT COUNT(*) FROM purchase_orders WHERE ABS(CAST(total_cost AS DOUBLE) - ROUND(CAST(order_qty * unit_cost AS DOUBLE), 4)) > 0.01",
            "total_cost = round(order_qty * unit_cost, 4)",
        )
        _add(
            "reconciliation",
            "production_achievable_qty",
            (
                "SELECT COUNT(*) FROM production_plans "
                "WHERE achievable_qty != ("
                "  CASE WHEN planned_qty <= capacity_limit_qty AND planned_qty <= bom_feasible_qty THEN planned_qty "
                "       WHEN capacity_limit_qty <= bom_feasible_qty THEN capacity_limit_qty "
                "       ELSE bom_feasible_qty END)"
            ),
            "achievable_qty = min(planned_qty, capacity_limit_qty, bom_feasible_qty)",
        )
        _add(
            "reconciliation",
            "supplier_capacity_available",
            "SELECT COUNT(*) FROM supplier_capacity WHERE available_capacity != (max_weekly_capacity - committed_qty)",
            "available_capacity = max_weekly_capacity - committed_qty",
        )
        _add(
            "reconciliation",
            "balance_row_equation",
            "SELECT COUNT(*) FROM projected_balances WHERE closing_stock != (opening_stock + inbound_qty + production_qty - demand_qty)",
            "closing_stock = opening_stock + inbound_qty + production_qty - demand_qty",
        )
        _add(
            "reconciliation",
            "balance_week_carryover",
            (
                "WITH ordered AS ("
                "  SELECT sku_id, location_id, week_id, opening_stock, closing_stock, "
                "         LAG(closing_stock) OVER (PARTITION BY sku_id, location_id ORDER BY week_id) AS prev_close "
                "  FROM projected_balances"
                ") "
                "SELECT COUNT(*) FROM ordered WHERE prev_close IS NOT NULL AND opening_stock != prev_close"
            ),
            "opening_stock(t) == closing_stock(t-1) week by week",
        )
        _add(
            "reconciliation",
            "balance_w01_matches_inventory",
            (
                "WITH first_wk AS (SELECT MIN(week_id) AS w0 FROM projected_balances) "
                "SELECT COUNT(*) FROM projected_balances b "
                "JOIN first_wk f ON b.week_id = f.w0 "
                "JOIN inventory i ON b.sku_id = i.sku_id AND b.location_id = i.location_id "
                "WHERE b.opening_stock != i.available_qty"
            ),
            "W01 opening_stock == inventory.available_qty",
        )
        _add(
            "reconciliation",
            "shortage_qty_matches_balance",
            "SELECT COUNT(*) FROM shortages s JOIN projected_balances b ON s.balance_id = b.balance_id WHERE s.shortage_qty != ABS(b.closing_stock)",
            "shortage_qty == abs(projected_balances.closing_stock)",
        )
        _add(
            "reconciliation",
            "shortage_revenue_at_risk",
            "SELECT COUNT(*) FROM shortages s JOIN skus k ON s.sku_id = k.sku_id WHERE ABS(CAST(s.revenue_at_risk AS DOUBLE) - ROUND(CAST(s.shortage_qty * k.unit_price AS DOUBLE), 4)) > 0.01",
            "revenue_at_risk == round(shortage_qty * unit_price, 4)",
        )
        _add(
            "reconciliation",
            "shortage_has_evidence",
            "SELECT COUNT(*) FROM shortages s LEFT JOIN (SELECT DISTINCT shortage_id FROM shortage_evidence) e ON s.shortage_id = e.shortage_id WHERE e.shortage_id IS NULL",
            "Every shortage must have >= 1 traceability evidence row",
        )

        natural_keys = [
            ("forecast_demand", "sku_id, location_id, week_id"),
            ("inventory", "sku_id, location_id"),
            ("supplier_capacity", "supplier_id, week_id"),
            ("lead_times", "sku_id, supplier_id, location_id"),
            ("projected_balances", "sku_id, location_id, week_id"),
            ("sku_suppliers", "sku_id, supplier_id"),
            ("sku_substitutes", "sku_id, substitute_sku_id"),
            ("bom_items", "parent_sku_id, component_sku_id"),
        ]
        for tbl, cols in natural_keys:
            _add(
                "duplicates",
                f"natural_key_unique:{tbl}({cols})",
                f"SELECT COUNT(*) FROM (SELECT {cols}, COUNT(*) AS cnt FROM {tbl} GROUP BY {cols} HAVING COUNT(*) > 1) t",
                f"Unique composite business key ({cols})",
            )

        return runner.backend, results
    finally:
        runner.close()
