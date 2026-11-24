# Reproducibility Report

- **Scale Profile**: `starter`
- **Fixed Seed**: `20261022`
- **Command Verified**: `python -m oryva_planning generate --scale starter --seed 20261022`
- **Verdict**: **PASS — 100% BIT-FOR-BIT IDENTICAL**

## Run 1 vs Run 2 Comparison

| Artifact | Run 1 Rows | Run 2 Rows | SHA-256 (first 16 hex) | Match |
|---|---:|---:|---|---|
| `ground_truth/ground_truth.csv` | 15 | 15 | `ae4f5760ff36d537...` | PASS |
| `inputs/csv/bom_items.csv` | 19 | 19 | `be0335bbaab79816...` | PASS |
| `inputs/csv/forecast_demand.csv` | 13,000 | 13,000 | `8743e045a8ff62ea...` | PASS |
| `inputs/csv/inventory.csv` | 250 | 250 | `0c5b9eb785b06dac...` | PASS |
| `inputs/csv/lead_times.csv` | 640 | 640 | `1c6764a13eca8637...` | PASS |
| `inputs/csv/locations.csv` | 5 | 5 | `d97653ec31f1d782...` | PASS |
| `inputs/csv/mitigation_options.csv` | 809 | 809 | `d9535aa21944fea1...` | PASS |
| `inputs/csv/production_plans.csv` | 520 | 520 | `5d7a8ef26860f3c1...` | PASS |
| `inputs/csv/projected_balances.csv` | 13,000 | 13,000 | `3ae95f1aae7d7c0e...` | PASS |
| `inputs/csv/purchase_order_events.csv` | 853 | 853 | `161fd427b0820389...` | PASS |
| `inputs/csv/purchase_orders.csv` | 300 | 300 | `450b7231bfa8d869...` | PASS |
| `inputs/csv/shortage_evidence.csv` | 948 | 948 | `b8b274fa1f145c11...` | PASS |
| `inputs/csv/shortages.csv` | 326 | 326 | `1bde2faf1b772003...` | PASS |
| `inputs/csv/sku_substitutes.csv` | 39 | 39 | `4942b6b9fecdfb1f...` | PASS |
| `inputs/csv/sku_suppliers.csv` | 128 | 128 | `5ce007d6d1e6ff32...` | PASS |
| `inputs/csv/skus.csv` | 50 | 50 | `3f2057f49b14055c...` | PASS |
| `inputs/csv/supplier_capacity.csv` | 780 | 780 | `884187b17f6f4a25...` | PASS |
| `inputs/csv/suppliers.csv` | 15 | 15 | `43c27ce5391e611e...` | PASS |
