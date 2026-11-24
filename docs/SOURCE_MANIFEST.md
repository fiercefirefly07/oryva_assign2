# Source Manifest & Provenance

- **Provenance**: Fully synthetic — no external datasets used.
- **Lawful Use**: 100% programmatically generated with deterministic seeded distributions; zero PII or third-party data.
- **Generator Command**: `python -m oryva_planning generate --scale starter --seed 20261022`
- **Fixed Seed**: `20261022` (via `numpy.random.SeedSequence(20261022).spawn()`)
- **Scale Profile**: `starter`
- **Planning Horizon**: `2026W01..2026W52` (52 ISO weeks)
- **Currency**: `INR`

## Generated Row Counts & SHA-256 Checksums

| Artifact | Rows | SHA-256 |
|---|---:|---|
| `inputs/csv/skus.csv` | 50 | `3f2057f49b14055c...` |
| `inputs/csv/locations.csv` | 5 | `d97653ec31f1d782...` |
| `inputs/csv/suppliers.csv` | 15 | `43c27ce5391e611e...` |
| `inputs/csv/sku_suppliers.csv` | 128 | `5ce007d6d1e6ff32...` |
| `inputs/csv/sku_substitutes.csv` | 39 | `4942b6b9fecdfb1f...` |
| `inputs/csv/bom_items.csv` | 19 | `be0335bbaab79816...` |
| `inputs/csv/forecast_demand.csv` | 13,000 | `8743e045a8ff62ea...` |
| `inputs/csv/inventory.csv` | 250 | `0c5b9eb785b06dac...` |
| `inputs/csv/supplier_capacity.csv` | 780 | `884187b17f6f4a25...` |
| `inputs/csv/lead_times.csv` | 640 | `1c6764a13eca8637...` |
| `inputs/csv/purchase_orders.csv` | 300 | `450b7231bfa8d869...` |
| `inputs/csv/purchase_order_events.csv` | 853 | `161fd427b0820389...` |
| `inputs/csv/production_plans.csv` | 520 | `5d7a8ef26860f3c1...` |
| `inputs/csv/projected_balances.csv` | 13,000 | `3ae95f1aae7d7c0e...` |
| `inputs/csv/shortages.csv` | 326 | `1bde2faf1b772003...` |
| `inputs/csv/shortage_evidence.csv` | 948 | `b8b274fa1f145c11...` |
| `inputs/csv/mitigation_options.csv` | 809 | `d9535aa21944fea1...` |
| `ground_truth/ground_truth.csv` | 15 | `ae4f5760ff36d537...` |
