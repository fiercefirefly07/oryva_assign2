# Oryva AI — Demand, Inventory & Supply Planning

End-to-end deterministic synthetic data generator, supply-chain planning engine, anomaly injection/detection harness, and DuckDB SQL validation suite built for the **Oryva AI Student Technical Assignment**.

## Architecture

```text
config/{starter,full}.yaml (fixed seed 20261022)
        |
        v
1. Schema Layer      -> Single source of truth: 11 core entities + 6 bridge/event/derived tables
        |               (fields, enums, zero-padded ID builders, Pydantic v2 models, SQL DDL)
        v
2. Generators        -> Independent SeedSequence(20261022).spawn(13) streams; masters -> bridges
        |               -> vectorized NumPy demand (scales to 7.8M rows) -> inventory -> lead times
        |               -> POs + append-only PurchaseOrderEvents -> SupplierCapacity -> ProductionPlan
        v
3. Planning Engine   -> Strictly isolated from ground truth: week-by-week ProjectedBalance ->
        |               Shortages + explainable RootCause + ShortageEvidence ->
        |               policy- & capacity-checked MitigationOptions (cost/service/lead-time trade-offs)
        v
4. Anomaly Injector  -> 5 modular edge-case injectors run AFTER clean baseline; writes ground_truth.csv
        |               solely to data/ground_truth/; 5 independent detectors score precision/recall
        v
5. Validators        -> DuckDB SQL checks (PK, FK, enum, dates, balance reconciliation, duplicates),
        |               PO lifecycle transitions, Ground Truth Wall, and phase-by-phase pytest suite
        v
6. Exporters         -> PK-sorted deterministic CSV, JSON, SQL DDL/seed, SQLite, SHA-256 checksums,
                        source manifest, data dictionary, ER diagram, and reproducibility report
```

## Quick Start

### Windows (PowerShell)

> Use `python -m pip` and `python -m pytest` on Windows 11 to avoid Smart App Control blocks on unsigned `.venv\Scripts\*.exe` wrappers.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

# Verify starter pipeline, DuckDB validation, tests, and reproducibility
python -m oryva_planning generate --scale starter --seed 20261022 --output-dir data --docs-dir docs
python -m oryva_planning validate --data-dir data --docs-dir docs
python -m pytest -v
python -m oryva_planning repro --scale starter --seed 20261022
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
make setup
make generate-starter
make validate
make test
make repro
```

### Full Assignment Scale (3,000 SKUs, 50 Locations, 500 Suppliers, 10,000 POs, 52 Weeks)

```bash
python -m oryva_planning generate --scale full --seed 20261022 --output-dir data/full_run
python -m oryva_planning validate --data-dir data/full_run
```

> At full scale (`7,800,000` demand rows and `7,800,000` balance rows), vectorized NumPy generation and pre-filtered joins keep runtime fast. To skip multi-GB JSON/SQL dumps during full-scale runs, set `export.formats: [csv]` in `config/full.yaml`.

## Repository Layout

```text
oryva-planning/
├── README.md
├── Makefile
├── pyproject.toml
├── reproducibility_report.md
├── .github/workflows/ci.yml
├── config/
│   ├── starter.yaml
│   └── full.yaml
├── src/oryva_planning/
│   ├── cli.py
│   ├── config.py
│   ├── pipeline.py
│   ├── schema/          # enums.py, ids.py, registry.py, models.py, ground_truth.py
│   ├── generators/      # master.py, demand.py, inventory.py, supply.py, production.py
│   ├── planning/        # balance.py, shortage.py, root_cause.py, mitigation.py
│   ├── anomalies/       # 1 module per edge case + injector.py + detectors.py
│   ├── validation/      # sql_checks.py (DuckDB/SQLite), validator.py
│   └── export/          # writers.py, manifest.py, repro.py
├── tests/               # Phase-by-phase pytest suite (Phases 1-8)
├── data/
│   ├── inputs/          # csv/, json/, sql/ (schema.sql + seed.sql), sqlite/
│   └── ground_truth/    # ground_truth.csv, ground_truth.json, detector_metrics.json
└── docs/                # DATA_DICTIONARY.md, ER_DIAGRAM.md, SOURCE_MANIFEST.md,
                         # VALIDATION_SUMMARY.md, REPRODUCIBILITY_REPORT.md
```

## CLI Reference

| Command | Purpose |
|---|---|
| `python -m oryva_planning schema-info` | List all 17 registered tables, layers, primary keys, and field counts |
| `python -m oryva_planning check-config --scale full --seed 20261022` | Validate YAML config and print resolved scale parameters |
| `python -m oryva_planning generate --scale starter --seed 20261022` | Generate, plan, inject anomalies, validate, export, and refresh `docs/` |
| `python -m oryva_planning validate --data-dir data` | Run DuckDB SQL checks, lifecycle checks, Ground Truth Wall, and detectors |
| `python -m oryva_planning repro --scale starter --seed 20261022` | Run twice into isolated folders, compare row counts & SHA-256 checksums |
| `python -m oryva_planning export-docs --data-dir data --docs-dir docs` | Regenerate Data Dictionary, ER diagram, and Validation Summary |

## Five Labelled Edge Cases & Ground Truth Wall

Injected **after** clean baseline validation and isolated in `data/ground_truth/ground_truth.csv`:

| `issue_type` | Module | Target Table | Detection Rule |
|---|---|---|---|
| `double_counted_inbound` | `anomalies/double_counted_inbound.py` | `projected_balances` | `inbound_qty` exceeds sum of active PO `order_qty` |
| `unapproved_substitute` | `anomalies/unapproved_substitute.py` | `mitigation_options` | `SUBSTITUTE_SKU` referencing `sku_substitutes.approved = False` |
| `supplier_capacity_exceeded` | `anomalies/supplier_capacity_exceeded.py` | `supplier_capacity` | Active PO sum exceeds `max_weekly_capacity` or `available_capacity < 0` |
| `shortage_without_lead_time` | `anomalies/shortage_without_lead_time.py` | `shortages` | Positive lead time exists yet `lead_time_days_used == 0` |
| `uom_mismatch` | `anomalies/uom_mismatch.py` | `purchase_orders` | `purchase_orders.uom != skus.base_uom` |

- `src/oryva_planning/planning/` never imports or reads `ground_truth` or `anomalies` (enforced by static AST tests).
- No `issue_type` or ground-truth columns appear in any table under `data/inputs/`.

## Documentation Deliverables

- `docs/DATA_DICTIONARY.md` — Type, required/optional, allowed values, units, uniqueness, and validation rule per field (auto-generated from the schema registry).
- `docs/ER_DIAGRAM.md` — Mermaid ER diagram, cardinality matrix, effective-dating policy, and PO event state machine.
- `docs/SOURCE_MANIFEST.md` & `data/source_manifest.json` — Lawful-use provenance ("100% synthetic, no external data"), generator command, fixed seed, row counts, and SHA-256 digests.
- `docs/VALIDATION_SUMMARY.md` — Complete SQL check report and per-anomaly detector precision/recall/F1 table.
- `reproducibility_report.md` & `docs/REPRODUCIBILITY_REPORT.md` — Two-run bit-for-bit SHA-256 verification proof.

## Visual Dashboard (Static HTML Report & Streamlit App)

Both read-only visual interfaces read directly from `data/inputs/csv/` (preserving the Ground Truth Wall):

### Option A — Instant Static HTML Report (Zero Extra Dependencies)

Open `docs/planning_dashboard.html` directly in Chrome/Edge, or regenerate it after any run:

```powershell
python -m oryva_planning report --data-dir data --output docs/planning_dashboard.html
```

Includes interactive shortage search/filtering, expandable `shortage_evidence` and ranked `mitigation_options` trade-offs, weekly Demand vs. Supply SVG charts, PO lifecycle history viewer, and an isolated anomaly audit scorecard.

### Option B — Interactive Streamlit Dashboard

```powershell
python -m pip install -e ".[ui]"
python -m streamlit run src/oryva_planning/dashboard/app.py
```
