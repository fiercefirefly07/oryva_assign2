"""Documentation, data dictionary, ER notes, source manifest, and validation summary writers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from oryva_planning.config import PlanningConfig
from oryva_planning.schema.enums import IssueType
from oryva_planning.schema.registry import ENTITY_ORDER, ENTITY_REGISTRY
from oryva_planning.validation.validator import ValidationReport


def write_source_manifest(
    config: PlanningConfig,
    export_meta: dict[str, Any],
    data_dir: Path,
    docs_dir: Path | None = None,
) -> Path:
    cmd = f"python -m oryva_planning generate --scale {config.name} --seed {config.seed}"
    manifest = {
        "project": "Oryva AI — Demand, Inventory & Supply Planning",
        "provenance": "100% synthetic data generated programmatically; zero external datasets used.",
        "lawful_use_statement": (
            "All entities, transactions, events, and anomaly labels are synthetically generated "
            "using seeded NumPy distributions. No personal, proprietary, or scraped data is included."
        ),
        "generator_command": cmd,
        "config_scale": config.name,
        "fixed_seed": config.seed,
        "planning_horizon": f"{config.planning_year}W{config.start_week:02d}..{config.planning_year}W{config.num_weeks:02d}",
        "currency": config.currency,
        "scale_parameters": config.scale.model_dump(),
        "distributions": {
            "demand": config.demand.model_dump(),
            "supplier": config.supplier.model_dump(),
            "inventory": config.inventory.model_dump(),
            "production": config.production.model_dump(),
        },
        "row_counts": export_meta["row_counts"],
        "sha256_checksums": export_meta["checksums"],
    }
    json_path = data_dir / "source_manifest.json"
    json_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    if docs_dir is not None:
        docs_dir.mkdir(parents=True, exist_ok=True)
        md_lines = [
            "# Source Manifest & Provenance",
            "",
            "- **Provenance**: Fully synthetic — no external datasets used.",
            "- **Lawful Use**: 100% programmatically generated with deterministic seeded distributions; zero PII or third-party data.",
            f"- **Generator Command**: `{cmd}`",
            f"- **Fixed Seed**: `{config.seed}` (via `numpy.random.SeedSequence({config.seed}).spawn()`)",
            f"- **Scale Profile**: `{config.name}`",
            f"- **Planning Horizon**: `{manifest['planning_horizon']}` ({config.num_weeks} ISO weeks)",
            f"- **Currency**: `{config.currency}`",
            "",
            "## Generated Row Counts & SHA-256 Checksums",
            "",
            "| Artifact | Rows | SHA-256 |",
            "|---|---:|---|",
        ]
        for table_name in ENTITY_ORDER:
            rel = f"inputs/csv/{table_name}.csv"
            cnt = export_meta["row_counts"].get(table_name, 0)
            sha = export_meta["checksums"].get(rel, "-")
            md_lines.append(f"| `{rel}` | {cnt:,} | `{sha[:16]}...` |")
        gt_rel = "ground_truth/ground_truth.csv"
        md_lines.append(
            f"| `{gt_rel}` | {export_meta['row_counts'].get('ground_truth', 0):,} "
            f"| `{export_meta['checksums'].get(gt_rel, '-')[:16]}...` |"
        )
        md_lines.append("")
        (docs_dir / "SOURCE_MANIFEST.md").write_text("\n".join(md_lines), encoding="utf-8", newline="\n")
    return json_path


def write_data_dictionary(docs_dir: Path) -> Path:
    docs_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Data Dictionary",
        "",
        "Generated directly from `oryva_planning.schema.registry` (single source of truth).",
        "Covers all 11 core entities, 6 bridge/event/derived tables, and the isolated `ground_truth` table.",
        "",
        "## Entity Overview",
        "",
        "| # | Entity | Table | Layer | Primary Key | Lifecycle Column |",
        "|---:|---|---|---|---|---|",
    ]
    for idx, tbl in enumerate(ENTITY_ORDER, start=1):
        spec = ENTITY_REGISTRY[tbl]
        lines.append(
            f"| {idx} | `{spec.name}` | `{spec.table_name}` | {spec.layer} "
            f"| `{spec.primary_key}` | `{spec.lifecycle_column}` |"
        )
    lines.append("")

    for tbl in ENTITY_ORDER:
        spec = ENTITY_REGISTRY[tbl]
        lines.extend(
            [
                f"## {spec.name} (`{spec.table_name}`)",
                "",
                spec.description,
                "",
                f"- **Primary Key**: `{spec.primary_key}`",
                f"- **Layer**: `{spec.layer}`",
                "- **Foreign Keys**: "
                + (
                    ", ".join(
                        f"`{fk.column}` -> `{fk.ref_table}.{fk.ref_column}`"
                        + (" (optional)" if fk.optional else "")
                        for fk in spec.foreign_keys
                    )
                    if spec.foreign_keys
                    else "None"
                ),
                "",
                spec.to_markdown_table(),
                "",
            ]
        )

    issue_vals = ", ".join(m.value for m in IssueType)
    lines.extend(
        [
            "## GroundTruth (`data/ground_truth/ground_truth.csv`)",
            "",
            "Strictly isolated label table recording injected edge cases. Never imported or read by planning code.",
            "",
            "| Field | Type | Required | Allowed Values | Units | Unique | Validation Rule |",
            "|---|---|---|---|---|---|---|",
            "| `ground_truth_id` | `str` | Required | `GT-2026-0001` | id | Yes | Regex `^GT-\d{4}-\d{4}$` |",
            f"| `issue_type` | `str` | Required | {issue_vals} | none | No | Allowed `IssueType` enum |",
            "| `target_table` | `str` | Required | Valid registry table name | table | No | Exists in `ENTITY_REGISTRY` |",
            "| `affected_id` | `str` | Required | Valid PK in `target_table` | id | No | Traceable to mutated row |",
            "| `related_ids` | `str` | Required | Comma-separated parent/child IDs | id_list | No | Valid related record IDs |",
            "| `expected_detection_rule` | `str` | Required | Documented domain SQL/rule | rule | No | Non-empty detection specification |",
            "| `injected_detail` | `str` | Required | Audit description of mutation | text | No | Non-empty explanation |",
            "",
        ]
    )

    out_path = docs_dir / "DATA_DICTIONARY.md"
    out_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return out_path


def write_er_diagram(docs_dir: Path) -> Path:
    docs_dir.mkdir(parents=True, exist_ok=True)
    content = """# Entity-Relationship Model & Lifecycle Design

## Mermaid ER Diagram

```mermaid
erDiagram
    SKU ||--o{ SKU_SUPPLIER : sourced_by
    SUPPLIER ||--o{ SKU_SUPPLIER : supplies
    SKU ||--o{ SKU_SUBSTITUTE : primary_for
    SKU ||--o{ SKU_SUBSTITUTE : substitutes_as
    SKU ||--o{ BOM_ITEM : parent_of
    SKU ||--o{ BOM_ITEM : component_in

    SKU ||--o{ FORECAST_DEMAND : demanded_in
    LOCATION ||--o{ FORECAST_DEMAND : experiences

    SKU ||--o{ INVENTORY : stocked_as
    LOCATION ||--o{ INVENTORY : holds

    SUPPLIER ||--o{ SUPPLIER_CAPACITY : provides_weekly
    SKU ||--o{ LEAD_TIME : has_lead_time
    SUPPLIER ||--o{ LEAD_TIME : quotes_lead_time
    LOCATION ||--o{ LEAD_TIME : destination_for

    SKU ||--o{ PURCHASE_ORDER : ordered_in
    SUPPLIER ||--o{ PURCHASE_ORDER : fulfills
    LOCATION ||--o{ PURCHASE_ORDER : receives
    PURCHASE_ORDER ||--|{ PURCHASE_ORDER_EVENT : transitions_via

    SKU ||--o{ PRODUCTION_PLAN : manufactured_in
    LOCATION ||--o{ PRODUCTION_PLAN : produced_at

    SKU ||--o{ PROJECTED_BALANCE : tracked_in
    LOCATION ||--o{ PROJECTED_BALANCE : balanced_at
    PROJECTED_BALANCE ||--o| SHORTAGE : triggers_when_negative

    SHORTAGE ||--|{ SHORTAGE_EVIDENCE : explained_by
    SHORTAGE ||--o{ MITIGATION_OPTION : resolved_by
    SUPPLIER |o--o{ MITIGATION_OPTION : alternate_or_expedite
    SKU |o--o{ MITIGATION_OPTION : substitute_target
    LOCATION |o--o{ MITIGATION_OPTION : transfer_donor
```

## Cardinality & Optionality Matrix

| Parent | Child / Bridge | Cardinality | Optional? | Foreign Key(s) |
|---|---|---:|---|---|
| `SKU` | `Supplier` via `sku_suppliers` | N:M | No | `sku_id`, `supplier_id` |
| `SKU` | `SKU` via `sku_substitutes` | N:M | Yes | `sku_id`, `substitute_sku_id` |
| `SKU` | `SKU` via `bom_items` | N:M | Yes (MAKE/BOTH only) | `parent_sku_id`, `component_sku_id` |
| `SKU`, `Location` | `ForecastDemand` | 1:N | No | `sku_id`, `location_id` |
| `SKU`, `Location` | `Inventory` | 1:1 per pair | No | `sku_id`, `location_id` |
| `Supplier` | `SupplierCapacity` | 1:N (52 weeks) | No | `supplier_id` |
| `SKU`, `Supplier`, `Location` | `LeadTime` | 1:N | No | `sku_id`, `supplier_id`, `location_id` |
| `PurchaseOrder` | `PurchaseOrderEvent` | 1:N (append-only) | No | `po_id` |
| `ProjectedBalance` | `Shortage` | 1:0..1 | Yes (deficit onset only) | `balance_id` |
| `Shortage` | `ShortageEvidence` | 1:N (>= 2 rows) | No | `shortage_id` |
| `Shortage` | `MitigationOption` | 1:N (1..4 ranked) | No | `shortage_id` |

## Effective Dates & History Preservation

- Every entity carries `effective_from` (required ISO date) and `effective_to` (optional, `>= effective_from`).
- `purchase_order_events` is strictly append-only (`sequence_num = 1..k`, non-decreasing UTC timestamps). `purchase_orders.current_status` is derived directly from the latest event's `to_status` and never overwritten without an audit event.

## PurchaseOrder State Machine

```text
NULL -> CREATED -> CONFIRMED -> IN_TRANSIT -> RECEIVED
                |            |             \-> DELAYED -> RECEIVED | IN_TRANSIT | CANCELLED
                \-> CANCELLED \-> DELAYED / CANCELLED
```
"""
    out_path = docs_dir / "ER_DIAGRAM.md"
    out_path.write_text(content.lstrip("\n"), encoding="utf-8", newline="\n")
    return out_path


def write_validation_summary(report: ValidationReport, docs_dir: Path, data_dir: Path) -> Path:
    docs_dir.mkdir(parents=True, exist_ok=True)
    md = report.to_markdown("Validation Summary")
    docs_path = docs_dir / "VALIDATION_SUMMARY.md"
    docs_path.write_text(md, encoding="utf-8", newline="\n")
    (data_dir / "validation_summary.md").write_text(md, encoding="utf-8", newline="\n")
    return docs_path
