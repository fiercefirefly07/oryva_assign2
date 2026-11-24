# Validation Summary

- **SQL Engine**: `duckdb`
- **Overall Status**: PASS (131/131 checks passed)

## Check Results by Category

| Category | Check | Status | Violations | Rule |
|---|---|---|---|---|
| `primary_key` | `pk_unique_nonnull:skus` | **PASS** | 0 | PK sku_id must be non-null and unique |
| `primary_key` | `pk_unique_nonnull:locations` | **PASS** | 0 | PK location_id must be non-null and unique |
| `primary_key` | `pk_unique_nonnull:suppliers` | **PASS** | 0 | PK supplier_id must be non-null and unique |
| `primary_key` | `pk_unique_nonnull:sku_suppliers` | **PASS** | 0 | PK sku_supplier_id must be non-null and unique |
| `primary_key` | `pk_unique_nonnull:sku_substitutes` | **PASS** | 0 | PK sku_substitute_id must be non-null and unique |
| `primary_key` | `pk_unique_nonnull:bom_items` | **PASS** | 0 | PK bom_id must be non-null and unique |
| `primary_key` | `pk_unique_nonnull:forecast_demand` | **PASS** | 0 | PK demand_id must be non-null and unique |
| `primary_key` | `pk_unique_nonnull:inventory` | **PASS** | 0 | PK inventory_id must be non-null and unique |
| `primary_key` | `pk_unique_nonnull:supplier_capacity` | **PASS** | 0 | PK capacity_id must be non-null and unique |
| `primary_key` | `pk_unique_nonnull:lead_times` | **PASS** | 0 | PK lead_time_id must be non-null and unique |
| `primary_key` | `pk_unique_nonnull:purchase_orders` | **PASS** | 0 | PK po_id must be non-null and unique |
| `primary_key` | `pk_unique_nonnull:purchase_order_events` | **PASS** | 0 | PK event_id must be non-null and unique |
| `primary_key` | `pk_unique_nonnull:production_plans` | **PASS** | 0 | PK production_id must be non-null and unique |
| `primary_key` | `pk_unique_nonnull:projected_balances` | **PASS** | 0 | PK balance_id must be non-null and unique |
| `primary_key` | `pk_unique_nonnull:shortages` | **PASS** | 0 | PK shortage_id must be non-null and unique |
| `primary_key` | `pk_unique_nonnull:shortage_evidence` | **PASS** | 0 | PK evidence_id must be non-null and unique |
| `primary_key` | `pk_unique_nonnull:mitigation_options` | **PASS** | 0 | PK mitigation_id must be non-null and unique |
| `foreign_key` | `fk:sku_suppliers.sku_id->skus.sku_id` | **PASS** | 0 | Every non-null sku_suppliers.sku_id must exist in skus.sku_id |
| `foreign_key` | `fk:sku_suppliers.supplier_id->suppliers.supplier_id` | **PASS** | 0 | Every non-null sku_suppliers.supplier_id must exist in suppliers.supplier_id |
| `foreign_key` | `fk:sku_substitutes.sku_id->skus.sku_id` | **PASS** | 0 | Every non-null sku_substitutes.sku_id must exist in skus.sku_id |
| `foreign_key` | `fk:sku_substitutes.substitute_sku_id->skus.sku_id` | **PASS** | 0 | Every non-null sku_substitutes.substitute_sku_id must exist in skus.sku_id |
| `foreign_key` | `fk:bom_items.parent_sku_id->skus.sku_id` | **PASS** | 0 | Every non-null bom_items.parent_sku_id must exist in skus.sku_id |
| `foreign_key` | `fk:bom_items.component_sku_id->skus.sku_id` | **PASS** | 0 | Every non-null bom_items.component_sku_id must exist in skus.sku_id |
| `foreign_key` | `fk:forecast_demand.sku_id->skus.sku_id` | **PASS** | 0 | Every non-null forecast_demand.sku_id must exist in skus.sku_id |
| `foreign_key` | `fk:forecast_demand.location_id->locations.location_id` | **PASS** | 0 | Every non-null forecast_demand.location_id must exist in locations.location_id |
| `foreign_key` | `fk:inventory.sku_id->skus.sku_id` | **PASS** | 0 | Every non-null inventory.sku_id must exist in skus.sku_id |
| `foreign_key` | `fk:inventory.location_id->locations.location_id` | **PASS** | 0 | Every non-null inventory.location_id must exist in locations.location_id |
| `foreign_key` | `fk:supplier_capacity.supplier_id->suppliers.supplier_id` | **PASS** | 0 | Every non-null supplier_capacity.supplier_id must exist in suppliers.supplier_id |
| `foreign_key` | `fk:lead_times.sku_id->skus.sku_id` | **PASS** | 0 | Every non-null lead_times.sku_id must exist in skus.sku_id |
| `foreign_key` | `fk:lead_times.supplier_id->suppliers.supplier_id` | **PASS** | 0 | Every non-null lead_times.supplier_id must exist in suppliers.supplier_id |
| `foreign_key` | `fk:lead_times.location_id->locations.location_id` | **PASS** | 0 | Every non-null lead_times.location_id must exist in locations.location_id |
| `foreign_key` | `fk:purchase_orders.sku_id->skus.sku_id` | **PASS** | 0 | Every non-null purchase_orders.sku_id must exist in skus.sku_id |
| `foreign_key` | `fk:purchase_orders.supplier_id->suppliers.supplier_id` | **PASS** | 0 | Every non-null purchase_orders.supplier_id must exist in suppliers.supplier_id |
| `foreign_key` | `fk:purchase_orders.location_id->locations.location_id` | **PASS** | 0 | Every non-null purchase_orders.location_id must exist in locations.location_id |
| `foreign_key` | `fk:purchase_order_events.po_id->purchase_orders.po_id` | **PASS** | 0 | Every non-null purchase_order_events.po_id must exist in purchase_orders.po_id |
| `foreign_key` | `fk:production_plans.sku_id->skus.sku_id` | **PASS** | 0 | Every non-null production_plans.sku_id must exist in skus.sku_id |
| `foreign_key` | `fk:production_plans.location_id->locations.location_id` | **PASS** | 0 | Every non-null production_plans.location_id must exist in locations.location_id |
| `foreign_key` | `fk:projected_balances.sku_id->skus.sku_id` | **PASS** | 0 | Every non-null projected_balances.sku_id must exist in skus.sku_id |
| `foreign_key` | `fk:projected_balances.location_id->locations.location_id` | **PASS** | 0 | Every non-null projected_balances.location_id must exist in locations.location_id |
| `foreign_key` | `fk:shortages.balance_id->projected_balances.balance_id` | **PASS** | 0 | Every non-null shortages.balance_id must exist in projected_balances.balance_id |
| `foreign_key` | `fk:shortages.sku_id->skus.sku_id` | **PASS** | 0 | Every non-null shortages.sku_id must exist in skus.sku_id |
| `foreign_key` | `fk:shortages.location_id->locations.location_id` | **PASS** | 0 | Every non-null shortages.location_id must exist in locations.location_id |
| `foreign_key` | `fk:shortage_evidence.shortage_id->shortages.shortage_id` | **PASS** | 0 | Every non-null shortage_evidence.shortage_id must exist in shortages.shortage_id |
| `foreign_key` | `fk:mitigation_options.shortage_id->shortages.shortage_id` | **PASS** | 0 | Every non-null mitigation_options.shortage_id must exist in shortages.shortage_id |
| `foreign_key` | `fk:mitigation_options.target_supplier_id->suppliers.supplier_id` | **PASS** | 0 | Every non-null mitigation_options.target_supplier_id must exist in suppliers.supplier_id |
| `foreign_key` | `fk:mitigation_options.target_sku_id->skus.sku_id` | **PASS** | 0 | Every non-null mitigation_options.target_sku_id must exist in skus.sku_id |
| `foreign_key` | `fk:mitigation_options.source_location_id->locations.location_id` | **PASS** | 0 | Every non-null mitigation_options.source_location_id must exist in locations.location_id |
| `enum` | `enum:skus.category` | **PASS** | 0 | Values must be in SKUCategory |
| `enum` | `enum:skus.sourcing_type` | **PASS** | 0 | Values must be in SourcingType |
| `enum` | `enum:skus.base_uom` | **PASS** | 0 | Values must be in UOM |
| `enum` | `enum:skus.popularity_tier` | **PASS** | 0 | Values must be in PopularityTier |
| `enum` | `enum:skus.lifecycle_state` | **PASS** | 0 | Values must be in EntityStatus |
| `enum` | `enum:locations.location_type` | **PASS** | 0 | Values must be in LocationType |
| `enum` | `enum:locations.region` | **PASS** | 0 | Values must be in Region |
| `enum` | `enum:locations.lifecycle_state` | **PASS** | 0 | Values must be in EntityStatus |
| `enum` | `enum:suppliers.region` | **PASS** | 0 | Values must be in Region |
| `enum` | `enum:suppliers.supplier_tier` | **PASS** | 0 | Values must be in SupplierTier |
| `enum` | `enum:suppliers.reliability_tier` | **PASS** | 0 | Values must be in ReliabilityTier |
| `enum` | `enum:suppliers.lifecycle_state` | **PASS** | 0 | Values must be in EntityStatus |
| `enum` | `enum:sku_suppliers.contract_uom` | **PASS** | 0 | Values must be in UOM |
| `enum` | `enum:sku_suppliers.lifecycle_state` | **PASS** | 0 | Values must be in EntityStatus |
| `enum` | `enum:sku_substitutes.lifecycle_state` | **PASS** | 0 | Values must be in EntityStatus |
| `enum` | `enum:bom_items.uom` | **PASS** | 0 | Values must be in UOM |
| `enum` | `enum:bom_items.lifecycle_state` | **PASS** | 0 | Values must be in EntityStatus |
| `enum` | `enum:forecast_demand.uom` | **PASS** | 0 | Values must be in UOM |
| `enum` | `enum:forecast_demand.lifecycle_state` | **PASS** | 0 | Values must be in EntityStatus |
| `enum` | `enum:inventory.uom` | **PASS** | 0 | Values must be in UOM |
| `enum` | `enum:inventory.lifecycle_state` | **PASS** | 0 | Values must be in EntityStatus |
| `enum` | `enum:supplier_capacity.lifecycle_state` | **PASS** | 0 | Values must be in EntityStatus |
| `enum` | `enum:lead_times.lifecycle_state` | **PASS** | 0 | Values must be in EntityStatus |
| `enum` | `enum:purchase_orders.uom` | **PASS** | 0 | Values must be in UOM |
| `enum` | `enum:purchase_orders.current_status` | **PASS** | 0 | Values must be in POStatus |
| `enum` | `enum:purchase_order_events.to_status` | **PASS** | 0 | Values must be in POStatus |
| `enum` | `enum:purchase_order_events.lifecycle_state` | **PASS** | 0 | Values must be in EntityStatus |
| `enum` | `enum:production_plans.uom` | **PASS** | 0 | Values must be in UOM |
| `enum` | `enum:production_plans.lifecycle_state` | **PASS** | 0 | Values must be in ProductionStatus |
| `enum` | `enum:projected_balances.lifecycle_state` | **PASS** | 0 | Values must be in EntityStatus |
| `enum` | `enum:shortages.root_cause` | **PASS** | 0 | Values must be in ShortageRootCause |
| `enum` | `enum:shortages.severity` | **PASS** | 0 | Values must be in ShortageSeverity |
| `enum` | `enum:shortages.lifecycle_state` | **PASS** | 0 | Values must be in ShortageStatus |
| `enum` | `enum:shortage_evidence.contribution_type` | **PASS** | 0 | Values must be in EvidenceContribution |
| `enum` | `enum:shortage_evidence.lifecycle_state` | **PASS** | 0 | Values must be in EntityStatus |
| `enum` | `enum:mitigation_options.mitigation_type` | **PASS** | 0 | Values must be in MitigationType |
| `enum` | `enum:mitigation_options.lifecycle_state` | **PASS** | 0 | Values must be in MitigationStatus |
| `date_ordering` | `effective_dates:skus` | **PASS** | 0 | effective_to must be NULL or >= effective_from |
| `date_ordering` | `effective_dates:locations` | **PASS** | 0 | effective_to must be NULL or >= effective_from |
| `date_ordering` | `effective_dates:suppliers` | **PASS** | 0 | effective_to must be NULL or >= effective_from |
| `date_ordering` | `effective_dates:sku_suppliers` | **PASS** | 0 | effective_to must be NULL or >= effective_from |
| `date_ordering` | `effective_dates:sku_substitutes` | **PASS** | 0 | effective_to must be NULL or >= effective_from |
| `date_ordering` | `effective_dates:bom_items` | **PASS** | 0 | effective_to must be NULL or >= effective_from |
| `date_ordering` | `effective_dates:forecast_demand` | **PASS** | 0 | effective_to must be NULL or >= effective_from |
| `date_ordering` | `effective_dates:inventory` | **PASS** | 0 | effective_to must be NULL or >= effective_from |
| `date_ordering` | `effective_dates:supplier_capacity` | **PASS** | 0 | effective_to must be NULL or >= effective_from |
| `date_ordering` | `effective_dates:lead_times` | **PASS** | 0 | effective_to must be NULL or >= effective_from |
| `date_ordering` | `effective_dates:purchase_orders` | **PASS** | 0 | effective_to must be NULL or >= effective_from |
| `date_ordering` | `effective_dates:purchase_order_events` | **PASS** | 0 | effective_to must be NULL or >= effective_from |
| `date_ordering` | `effective_dates:production_plans` | **PASS** | 0 | effective_to must be NULL or >= effective_from |
| `date_ordering` | `effective_dates:projected_balances` | **PASS** | 0 | effective_to must be NULL or >= effective_from |
| `date_ordering` | `effective_dates:shortages` | **PASS** | 0 | effective_to must be NULL or >= effective_from |
| `date_ordering` | `effective_dates:shortage_evidence` | **PASS** | 0 | effective_to must be NULL or >= effective_from |
| `date_ordering` | `effective_dates:mitigation_options` | **PASS** | 0 | effective_to must be NULL or >= effective_from |
| `date_ordering` | `po_date_order` | **PASS** | 0 | order_date <= promised_delivery_date and actual_delivery_date >= order_date |
| `date_ordering` | `shortage_order_by_date` | **PASS** | 0 | required_order_by_date <= week_start_date |
| `reconciliation` | `inventory_available_qty` | **PASS** | 0 | available_qty = on_hand_qty - reserved_qty |
| `reconciliation` | `lead_time_total_days` | **PASS** | 0 | total_lead_time_days = manufacturing + transit + customs |
| `reconciliation` | `po_total_cost` | **PASS** | 0 | total_cost = round(order_qty * unit_cost, 4) |
| `reconciliation` | `production_achievable_qty` | **PASS** | 0 | achievable_qty = min(planned_qty, capacity_limit_qty, bom_feasible_qty) |
| `reconciliation` | `supplier_capacity_available` | **PASS** | 0 | available_capacity = max_weekly_capacity - committed_qty |
| `reconciliation` | `balance_row_equation` | **PASS** | 0 | closing_stock = opening_stock + inbound_qty + production_qty - demand_qty |
| `reconciliation` | `balance_week_carryover` | **PASS** | 0 | opening_stock(t) == closing_stock(t-1) week by week |
| `reconciliation` | `balance_w01_matches_inventory` | **PASS** | 0 | W01 opening_stock == inventory.available_qty |
| `reconciliation` | `shortage_qty_matches_balance` | **PASS** | 0 | shortage_qty == abs(projected_balances.closing_stock) |
| `reconciliation` | `shortage_revenue_at_risk` | **PASS** | 0 | revenue_at_risk == round(shortage_qty * unit_price, 4) |
| `reconciliation` | `shortage_has_evidence` | **PASS** | 0 | Every shortage must have >= 1 traceability evidence row |
| `duplicates` | `natural_key_unique:forecast_demand(sku_id, location_id, week_id)` | **PASS** | 0 | Unique composite business key (sku_id, location_id, week_id) |
| `duplicates` | `natural_key_unique:inventory(sku_id, location_id)` | **PASS** | 0 | Unique composite business key (sku_id, location_id) |
| `duplicates` | `natural_key_unique:supplier_capacity(supplier_id, week_id)` | **PASS** | 0 | Unique composite business key (supplier_id, week_id) |
| `duplicates` | `natural_key_unique:lead_times(sku_id, supplier_id, location_id)` | **PASS** | 0 | Unique composite business key (sku_id, supplier_id, location_id) |
| `duplicates` | `natural_key_unique:projected_balances(sku_id, location_id, week_id)` | **PASS** | 0 | Unique composite business key (sku_id, location_id, week_id) |
| `duplicates` | `natural_key_unique:sku_suppliers(sku_id, supplier_id)` | **PASS** | 0 | Unique composite business key (sku_id, supplier_id) |
| `duplicates` | `natural_key_unique:sku_substitutes(sku_id, substitute_sku_id)` | **PASS** | 0 | Unique composite business key (sku_id, substitute_sku_id) |
| `duplicates` | `natural_key_unique:bom_items(parent_sku_id, component_sku_id)` | **PASS** | 0 | Unique composite business key (parent_sku_id, component_sku_id) |
| `lifecycle` | `po_events_present` | **PASS** | 0 | Every PurchaseOrder has >= 1 PurchaseOrderEvent |
| `lifecycle` | `po_event_sequence_monotonic` | **PASS** | 0 | sequence_num contiguous 1..k per po_id |
| `lifecycle` | `po_event_timestamps_ordered` | **PASS** | 0 | event_ts non-decreasing per po_id |
| `lifecycle` | `po_state_transitions_valid` | **PASS** | 0 | Every transition obeys PO_TRANSITIONS |
| `lifecycle` | `po_current_status_derived_from_latest_event` | **PASS** | 0 | current_status == latest event to_status |
| `ground_truth_wall` | `no_ground_truth_columns_in_inputs` | **PASS** | 0 | Input tables must never contain issue_type or ground_truth columns |
| `foreign_key` | `shortage_evidence_polymorphic_fk` | **PASS** | 0 | Every shortage_evidence.source_record_id exists in source_table |
| `anomaly_detection` | `detectors_exact_precision_recall` | **PASS** | 0 | Detectors matched ground truth with P=1.0000, R=1.0000 |
| `ground_truth_wall` | `no_ground_truth_files_in_inputs_dir` | **PASS** | 0 | data/inputs/ must not contain any ground_truth files |

## Anomaly Detector Precision & Recall

| Issue Type | Expected | Detected | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `double_counted_inbound` | 3 | 3 | 3 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| `unapproved_substitute` | 3 | 3 | 3 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| `supplier_capacity_exceeded` | 3 | 3 | 3 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| `shortage_without_lead_time` | 3 | 3 | 3 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| `uom_mismatch` | 3 | 3 | 3 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| `overall` | 15 | 15 | 15 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
