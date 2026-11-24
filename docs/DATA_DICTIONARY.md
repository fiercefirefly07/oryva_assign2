# Data Dictionary

Generated directly from `oryva_planning.schema.registry` (single source of truth).
Covers all 11 core entities, 6 bridge/event/derived tables, and the isolated `ground_truth` table.

## Entity Overview

| # | Entity | Table | Layer | Primary Key | Lifecycle Column |
|---:|---|---|---|---|---|
| 1 | `SKU` | `skus` | master | `sku_id` | `lifecycle_state` |
| 2 | `Location` | `locations` | master | `location_id` | `lifecycle_state` |
| 3 | `Supplier` | `suppliers` | master | `supplier_id` | `lifecycle_state` |
| 4 | `SKUSupplier` | `sku_suppliers` | bridge | `sku_supplier_id` | `lifecycle_state` |
| 5 | `SKUSubstitute` | `sku_substitutes` | bridge | `sku_substitute_id` | `lifecycle_state` |
| 6 | `BOMItem` | `bom_items` | bridge | `bom_id` | `lifecycle_state` |
| 7 | `ForecastDemand` | `forecast_demand` | dependent | `demand_id` | `lifecycle_state` |
| 8 | `Inventory` | `inventory` | dependent | `inventory_id` | `lifecycle_state` |
| 9 | `SupplierCapacity` | `supplier_capacity` | dependent | `capacity_id` | `lifecycle_state` |
| 10 | `LeadTime` | `lead_times` | dependent | `lead_time_id` | `lifecycle_state` |
| 11 | `PurchaseOrder` | `purchase_orders` | dependent | `po_id` | `current_status` |
| 12 | `PurchaseOrderEvent` | `purchase_order_events` | event | `event_id` | `lifecycle_state` |
| 13 | `ProductionPlan` | `production_plans` | dependent | `production_id` | `lifecycle_state` |
| 14 | `ProjectedBalance` | `projected_balances` | derived | `balance_id` | `lifecycle_state` |
| 15 | `Shortage` | `shortages` | derived | `shortage_id` | `lifecycle_state` |
| 16 | `ShortageEvidence` | `shortage_evidence` | derived | `evidence_id` | `lifecycle_state` |
| 17 | `MitigationOption` | `mitigation_options` | derived | `mitigation_id` | `lifecycle_state` |

## SKU (`skus`)

Stock Keeping Unit master catalog with costing, sourcing, and Pareto velocity tier.

- **Primary Key**: `sku_id`
- **Layer**: `master`
- **Foreign Keys**: None

| Field | Type | Required | Allowed Values | Units | Unique | Validation Rule |
|---|---|---|---|---|---|---|
| `sku_id` | `str` | Required | SKU-000001 | id | Yes | Regex ^SKU-\d{6}$ |
| `sku_name` | `str` | Required | Non-empty text | text | No | len >= 3 |
| `category` | `str` | Required | ELECTRONICS, INDUSTRIAL, PACKAGING, CONSUMABLES, SPARE_PARTS | none | No | Allowed SKUCategory enum |
| `sourcing_type` | `str` | Required | BUY, MAKE, BOTH | none | No | Allowed SourcingType enum |
| `base_uom` | `str` | Required | EA, KG, L, CASE, PALLET | uom | No | Allowed UOM enum |
| `unit_cost` | `float` | Required | > 0 | INR | No | unit_cost > 0 |
| `unit_price` | `float` | Required | >= unit_cost | INR | No | unit_price >= unit_cost |
| `weight_kg` | `float` | Required | > 0 | kg | No | weight_kg > 0 |
| `popularity_rank` | `int` | Required | >= 1 | rank | Yes | Unique positive rank |
| `popularity_tier` | `str` | Required | A, B, C | none | No | Allowed PopularityTier enum |
| `is_critical` | `bool` | Required | true, false | flag | No | Boolean |
| `effective_from` | `date` | Required | ISO date YYYY-MM-DD | date | No | Valid ISO date |
| `effective_to` | `date` | Optional | ISO date YYYY-MM-DD or NULL | date | No | NULL or >= effective_from |
| `lifecycle_state` | `str` | Required | DRAFT, ACTIVE, SUSPENDED, RETIRED | none | No | Must belong to EntityStatus |

## Location (`locations`)

Warehouses, distribution centres, plants, and regional hubs.

- **Primary Key**: `location_id`
- **Layer**: `master`
- **Foreign Keys**: None

| Field | Type | Required | Allowed Values | Units | Unique | Validation Rule |
|---|---|---|---|---|---|---|
| `location_id` | `str` | Required | LOC-0001 | id | Yes | Regex ^LOC-\d{4}$ |
| `location_name` | `str` | Required | Non-empty text | text | No | len >= 3 |
| `location_type` | `str` | Required | WAREHOUSE, DISTRIBUTION_CENTER, PLANT, REGIONAL_HUB | none | No | Allowed LocationType enum |
| `region` | `str` | Required | NORTH, SOUTH, EAST, WEST, CENTRAL | none | No | Allowed Region enum |
| `storage_capacity_units` | `int` | Required | > 0 | units | No | storage_capacity_units > 0 |
| `daily_production_capacity` | `int` | Required | >= 0 | units/day | No | 0 unless PLANT; >= 0 |
| `holding_cost_per_unit_week` | `float` | Required | > 0 | INR/unit/week | No | holding_cost_per_unit_week > 0 |
| `effective_from` | `date` | Required | ISO date YYYY-MM-DD | date | No | Valid ISO date |
| `effective_to` | `date` | Optional | ISO date YYYY-MM-DD or NULL | date | No | NULL or >= effective_from |
| `lifecycle_state` | `str` | Required | DRAFT, ACTIVE, SUSPENDED, RETIRED | none | No | Must belong to EntityStatus |

## Supplier (`suppliers`)

External vendor master with tiering, reliability, capacity constraint flag, and expedite surcharges.

- **Primary Key**: `supplier_id`
- **Layer**: `master`
- **Foreign Keys**: None

| Field | Type | Required | Allowed Values | Units | Unique | Validation Rule |
|---|---|---|---|---|---|---|
| `supplier_id` | `str` | Required | SUP-0001 | id | Yes | Regex ^SUP-\d{4}$ |
| `supplier_name` | `str` | Required | Non-empty text | text | No | len >= 3 |
| `region` | `str` | Required | NORTH, SOUTH, EAST, WEST, CENTRAL | none | No | Allowed Region enum |
| `supplier_tier` | `str` | Required | STRATEGIC, PREFERRED, APPROVED, CONSTRAINED | none | No | Allowed SupplierTier enum |
| `reliability_tier` | `str` | Required | HIGH, MEDIUM, LOW | none | No | Allowed ReliabilityTier enum |
| `on_time_rate` | `float` | Required | 0.0 to 1.0 | ratio | No | 0 <= on_time_rate <= 1 |
| `is_constrained` | `bool` | Required | true, false | flag | No | Boolean |
| `expedite_surcharge_pct` | `float` | Required | 0.0 to 1.0 | ratio | No | 0 <= expedite_surcharge_pct <= 1 |
| `effective_from` | `date` | Required | ISO date YYYY-MM-DD | date | No | Valid ISO date |
| `effective_to` | `date` | Optional | ISO date YYYY-MM-DD or NULL | date | No | NULL or >= effective_from |
| `lifecycle_state` | `str` | Required | DRAFT, ACTIVE, SUSPENDED, RETIRED | none | No | Must belong to EntityStatus |

## SKUSupplier (`sku_suppliers`)

Many-to-many approved sourcing agreements between SKUs and Suppliers.

- **Primary Key**: `sku_supplier_id`
- **Layer**: `bridge`
- **Foreign Keys**: `sku_id` -> `skus.sku_id`, `supplier_id` -> `suppliers.supplier_id`

| Field | Type | Required | Allowed Values | Units | Unique | Validation Rule |
|---|---|---|---|---|---|---|
| `sku_supplier_id` | `str` | Required | SS-SKU-000001-SUP-0001 | id | Yes | Regex ^SS-SKU-\d{6}-SUP-\d{4}$ |
| `sku_id` | `str` | Required | Valid skus.sku_id | id | No | FK -> skus.sku_id |
| `supplier_id` | `str` | Required | Valid suppliers.supplier_id | id | No | FK -> suppliers.supplier_id |
| `unit_purchase_cost` | `float` | Required | > 0 | INR | No | unit_purchase_cost > 0 |
| `min_order_qty` | `int` | Required | >= 1 | units | No | min_order_qty >= 1 |
| `order_multiple` | `int` | Required | >= 1 | units | No | order_multiple >= 1 |
| `is_primary` | `bool` | Required | true, false | flag | No | Boolean |
| `contract_uom` | `str` | Required | EA, KG, L, CASE, PALLET | uom | No | Allowed UOM enum; matches SKU base_uom in baseline |
| `effective_from` | `date` | Required | ISO date YYYY-MM-DD | date | No | Valid ISO date |
| `effective_to` | `date` | Optional | ISO date YYYY-MM-DD or NULL | date | No | NULL or >= effective_from |
| `lifecycle_state` | `str` | Required | DRAFT, ACTIVE, SUSPENDED, RETIRED | none | No | Must belong to EntityStatus |

## SKUSubstitute (`sku_substitutes`)

Approved and unapproved substitute SKU mappings for shortage mitigation.

- **Primary Key**: `sku_substitute_id`
- **Layer**: `bridge`
- **Foreign Keys**: `sku_id` -> `skus.sku_id`, `substitute_sku_id` -> `skus.sku_id`

| Field | Type | Required | Allowed Values | Units | Unique | Validation Rule |
|---|---|---|---|---|---|---|
| `sku_substitute_id` | `str` | Required | SUB-SKU-000001-SKU-000002 | id | Yes | Regex ^SUB-SKU-\d{6}-SKU-\d{6}$ |
| `sku_id` | `str` | Required | Valid skus.sku_id | id | No | FK -> skus.sku_id |
| `substitute_sku_id` | `str` | Required | Valid skus.sku_id != sku_id | id | No | FK -> skus.sku_id; != sku_id |
| `approved` | `bool` | Required | true, false | flag | No | Boolean; policy requires true for mitigation |
| `conversion_factor` | `float` | Required | > 0 | ratio | No | conversion_factor > 0 |
| `cost_delta_pct` | `float` | Required | -0.5 to 1.0 | ratio | No | -0.5 <= cost_delta_pct <= 1.0 |
| `priority_rank` | `int` | Required | >= 1 | rank | No | priority_rank >= 1 |
| `effective_from` | `date` | Required | ISO date YYYY-MM-DD | date | No | Valid ISO date |
| `effective_to` | `date` | Optional | ISO date YYYY-MM-DD or NULL | date | No | NULL or >= effective_from |
| `lifecycle_state` | `str` | Required | DRAFT, ACTIVE, SUSPENDED, RETIRED | none | No | Must belong to EntityStatus |

## BOMItem (`bom_items`)

Bill of Materials linking manufactured parent SKUs to component SKUs.

- **Primary Key**: `bom_id`
- **Layer**: `bridge`
- **Foreign Keys**: `parent_sku_id` -> `skus.sku_id`, `component_sku_id` -> `skus.sku_id`

| Field | Type | Required | Allowed Values | Units | Unique | Validation Rule |
|---|---|---|---|---|---|---|
| `bom_id` | `str` | Required | BOM-SKU-000001-SKU-000002 | id | Yes | Regex ^BOM-SKU-\d{6}-SKU-\d{6}$ |
| `parent_sku_id` | `str` | Required | Valid skus.sku_id | id | No | FK -> skus.sku_id (MAKE or BOTH) |
| `component_sku_id` | `str` | Required | Valid skus.sku_id != parent_sku_id | id | No | FK -> skus.sku_id; != parent_sku_id |
| `qty_per_parent` | `float` | Required | > 0 | units/parent | No | qty_per_parent > 0 |
| `uom` | `str` | Required | EA, KG, L, CASE, PALLET | uom | No | Allowed UOM enum |
| `scrap_rate` | `float` | Required | 0.0 to 0.3 | ratio | No | 0 <= scrap_rate <= 0.3 |
| `effective_from` | `date` | Required | ISO date YYYY-MM-DD | date | No | Valid ISO date |
| `effective_to` | `date` | Optional | ISO date YYYY-MM-DD or NULL | date | No | NULL or >= effective_from |
| `lifecycle_state` | `str` | Required | DRAFT, ACTIVE, SUSPENDED, RETIRED | none | No | Must belong to EntityStatus |

## ForecastDemand (`forecast_demand`)

Weekly SKU-location forecast demand generated with Pareto popularity, seasonality, and spikes.

- **Primary Key**: `demand_id`
- **Layer**: `dependent`
- **Foreign Keys**: `sku_id` -> `skus.sku_id`, `location_id` -> `locations.location_id`

| Field | Type | Required | Allowed Values | Units | Unique | Validation Rule |
|---|---|---|---|---|---|---|
| `demand_id` | `str` | Required | DEM-SKU-000001-LOC-0001-2026W01 | id | Yes | Regex ^DEM-SKU-\d{6}-LOC-\d{4}-\d{4}W\d{2}$ |
| `sku_id` | `str` | Required | Valid skus.sku_id | id | No | FK -> skus.sku_id |
| `location_id` | `str` | Required | Valid locations.location_id | id | No | FK -> locations.location_id |
| `week_id` | `str` | Required | 2026W01..2026W52 | iso_week | No | Regex ^\d{4}W\d{2}$ |
| `week_start_date` | `date` | Required | Monday of week_id | date | No | Matches ISO week Monday |
| `forecast_qty` | `int` | Required | >= 0 | units | No | forecast_qty >= 0 |
| `uom` | `str` | Required | EA, KG, L, CASE, PALLET | uom | No | Allowed UOM enum; matches SKU base_uom in baseline |
| `is_spike_week` | `bool` | Required | true, false | flag | No | Boolean |
| `seasonality_factor` | `float` | Required | > 0 | multiplier | No | seasonality_factor > 0 |
| `priority_weight` | `float` | Required | > 0 | score | No | priority_weight > 0 |
| `effective_from` | `date` | Required | ISO date YYYY-MM-DD | date | No | Valid ISO date |
| `effective_to` | `date` | Optional | ISO date YYYY-MM-DD or NULL | date | No | NULL or >= effective_from |
| `lifecycle_state` | `str` | Required | DRAFT, ACTIVE, SUSPENDED, RETIRED | none | No | Must belong to EntityStatus |

## Inventory (`inventory`)

Opening SKU-location inventory snapshot with derived available stock.

- **Primary Key**: `inventory_id`
- **Layer**: `dependent`
- **Foreign Keys**: `sku_id` -> `skus.sku_id`, `location_id` -> `locations.location_id`

| Field | Type | Required | Allowed Values | Units | Unique | Validation Rule |
|---|---|---|---|---|---|---|
| `inventory_id` | `str` | Required | INV-SKU-000001-LOC-0001 | id | Yes | Regex ^INV-SKU-\d{6}-LOC-\d{4}$ |
| `sku_id` | `str` | Required | Valid skus.sku_id | id | No | FK -> skus.sku_id |
| `location_id` | `str` | Required | Valid locations.location_id | id | No | FK -> locations.location_id |
| `snapshot_date` | `date` | Required | ISO date | date | No | Matches planning start date |
| `on_hand_qty` | `int` | Required | >= 0 | units | No | on_hand_qty >= 0 |
| `reserved_qty` | `int` | Required | 0..on_hand_qty | units | No | 0 <= reserved_qty <= on_hand_qty |
| `available_qty` | `int` | Required | on_hand_qty - reserved_qty | units | No | Derived == on_hand_qty - reserved_qty |
| `safety_stock_qty` | `int` | Required | >= 0 | units | No | safety_stock_qty >= 0 |
| `reorder_point_qty` | `int` | Required | >= safety_stock_qty | units | No | reorder_point_qty >= safety_stock_qty |
| `uom` | `str` | Required | EA, KG, L, CASE, PALLET | uom | No | Allowed UOM enum; matches SKU base_uom in baseline |
| `effective_from` | `date` | Required | ISO date YYYY-MM-DD | date | No | Valid ISO date |
| `effective_to` | `date` | Optional | ISO date YYYY-MM-DD or NULL | date | No | NULL or >= effective_from |
| `lifecycle_state` | `str` | Required | DRAFT, ACTIVE, SUSPENDED, RETIRED | none | No | Must belong to EntityStatus |

## SupplierCapacity (`supplier_capacity`)

Weekly supplier output ceilings and derived committed/available capacity.

- **Primary Key**: `capacity_id`
- **Layer**: `dependent`
- **Foreign Keys**: `supplier_id` -> `suppliers.supplier_id`

| Field | Type | Required | Allowed Values | Units | Unique | Validation Rule |
|---|---|---|---|---|---|---|
| `capacity_id` | `str` | Required | CAP-SUP-0001-2026W01 | id | Yes | Regex ^CAP-SUP-\d{4}-\d{4}W\d{2}$ |
| `supplier_id` | `str` | Required | Valid suppliers.supplier_id | id | No | FK -> suppliers.supplier_id |
| `week_id` | `str` | Required | 2026W01..2026W52 | iso_week | No | Regex ^\d{4}W\d{2}$ |
| `week_start_date` | `date` | Required | Monday of week_id | date | No | Matches ISO week Monday |
| `max_weekly_capacity` | `int` | Required | > 0 | units | No | max_weekly_capacity > 0 |
| `committed_qty` | `int` | Required | >= 0 | units | No | Derived sum of active POs for supplier-week |
| `available_capacity` | `int` | Required | max - committed | units | No | Derived == max_weekly_capacity - committed_qty; >= 0 in baseline |
| `effective_from` | `date` | Required | ISO date YYYY-MM-DD | date | No | Valid ISO date |
| `effective_to` | `date` | Optional | ISO date YYYY-MM-DD or NULL | date | No | NULL or >= effective_from |
| `lifecycle_state` | `str` | Required | DRAFT, ACTIVE, SUSPENDED, RETIRED | none | No | Must belong to EntityStatus |

## LeadTime (`lead_times`)

SKU-supplier-location replenishment lead times and MOQ constraints.

- **Primary Key**: `lead_time_id`
- **Layer**: `dependent`
- **Foreign Keys**: `sku_id` -> `skus.sku_id`, `supplier_id` -> `suppliers.supplier_id`, `location_id` -> `locations.location_id`

| Field | Type | Required | Allowed Values | Units | Unique | Validation Rule |
|---|---|---|---|---|---|---|
| `lead_time_id` | `str` | Required | LT-SKU-000001-SUP-0001-LOC-0001 | id | Yes | Regex ^LT-SKU-\d{6}-SUP-\d{4}-LOC-\d{4}$ |
| `sku_id` | `str` | Required | Valid skus.sku_id | id | No | FK -> skus.sku_id |
| `supplier_id` | `str` | Required | Valid suppliers.supplier_id | id | No | FK -> suppliers.supplier_id |
| `location_id` | `str` | Required | Valid locations.location_id | id | No | FK -> locations.location_id |
| `manufacturing_days` | `int` | Required | >= 1 | days | No | manufacturing_days >= 1 |
| `transit_days` | `int` | Required | >= 1 | days | No | transit_days >= 1 |
| `customs_buffer_days` | `int` | Required | >= 0 | days | No | customs_buffer_days >= 0 |
| `total_lead_time_days` | `int` | Required | sum of components | days | No | Derived == manufacturing + transit + customs |
| `min_order_qty` | `int` | Required | >= 1 | units | No | min_order_qty >= 1 |
| `effective_from` | `date` | Required | ISO date YYYY-MM-DD | date | No | Valid ISO date |
| `effective_to` | `date` | Optional | ISO date YYYY-MM-DD or NULL | date | No | NULL or >= effective_from |
| `lifecycle_state` | `str` | Required | DRAFT, ACTIVE, SUSPENDED, RETIRED | none | No | Must belong to EntityStatus |

## PurchaseOrder (`purchase_orders`)

Inbound supplier purchase orders with derived costs and event-sourced status.

- **Primary Key**: `po_id`
- **Layer**: `dependent`
- **Foreign Keys**: `sku_id` -> `skus.sku_id`, `supplier_id` -> `suppliers.supplier_id`, `location_id` -> `locations.location_id`

| Field | Type | Required | Allowed Values | Units | Unique | Validation Rule |
|---|---|---|---|---|---|---|
| `po_id` | `str` | Required | PO-2026-000001 | id | Yes | Regex ^PO-\d{4}-\d{6}$ |
| `sku_id` | `str` | Required | Valid skus.sku_id | id | No | FK -> skus.sku_id |
| `supplier_id` | `str` | Required | Valid suppliers.supplier_id | id | No | FK -> suppliers.supplier_id |
| `location_id` | `str` | Required | Valid locations.location_id | id | No | FK -> locations.location_id |
| `order_date` | `date` | Required | ISO date | date | No | order_date <= promised_delivery_date |
| `promised_delivery_date` | `date` | Required | ISO date | date | No | >= order_date |
| `actual_delivery_date` | `date` | Optional | ISO date or NULL | date | No | NULL if cancelled; >= order_date |
| `arrival_week_id` | `str` | Required | 2026W01..2026W52 | iso_week | No | Derived ISO week of effective delivery date |
| `order_qty` | `int` | Required | > 0 | units | No | order_qty > 0 |
| `uom` | `str` | Required | EA, KG, L, CASE, PALLET | uom | No | Allowed UOM enum; matches SKU base_uom in baseline |
| `unit_cost` | `float` | Required | > 0 | INR | No | unit_cost > 0 |
| `total_cost` | `float` | Required | order_qty * unit_cost | INR | No | Derived == round(order_qty * unit_cost, 4) |
| `transport_delay_days` | `int` | Required | >= 0 | days | No | transport_delay_days >= 0 |
| `current_status` | `str` | Required | CREATED, CONFIRMED, IN_TRANSIT, DELAYED, RECEIVED, CANCELLED | none | No | Must belong to POStatus |
| `effective_from` | `date` | Required | ISO date YYYY-MM-DD | date | No | Valid ISO date |
| `effective_to` | `date` | Optional | ISO date YYYY-MM-DD or NULL | date | No | NULL or >= effective_from |

## PurchaseOrderEvent (`purchase_order_events`)

Append-only state transition history for PurchaseOrder lifecycle.

- **Primary Key**: `event_id`
- **Layer**: `event`
- **Foreign Keys**: `po_id` -> `purchase_orders.po_id`

| Field | Type | Required | Allowed Values | Units | Unique | Validation Rule |
|---|---|---|---|---|---|---|
| `event_id` | `str` | Required | POE-2026-0000001 | id | Yes | Regex ^POE-\d{4}-\d{7}$ |
| `po_id` | `str` | Required | Valid purchase_orders.po_id | id | No | FK -> purchase_orders.po_id |
| `sequence_num` | `int` | Required | >= 1 | seq | No | Monotonic 1..k per po_id |
| `from_status` | `str` | Optional | NULL or CREATED, CONFIRMED, IN_TRANSIT, DELAYED, RECEIVED, CANCELLED | none | No | Valid transition predecessor |
| `to_status` | `str` | Required | CREATED, CONFIRMED, IN_TRANSIT, DELAYED, RECEIVED, CANCELLED | none | No | Valid transition target |
| `event_ts` | `datetime` | Required | ISO-8601 UTC timestamp | timestamp | No | Non-decreasing per po_id |
| `actor` | `str` | Required | PLANNER, SUPPLIER, CARRIER, WAREHOUSE, OPS_MANAGER | role | No | Non-empty system actor |
| `reason` | `str` | Required | Non-empty text | text | No | len >= 3 |
| `effective_from` | `date` | Required | ISO date YYYY-MM-DD | date | No | Valid ISO date |
| `effective_to` | `date` | Optional | ISO date YYYY-MM-DD or NULL | date | No | NULL or >= effective_from |
| `lifecycle_state` | `str` | Required | DRAFT, ACTIVE, SUSPENDED, RETIRED | none | No | Must belong to EntityStatus |

## ProductionPlan (`production_plans`)

Weekly internal production schedule constrained by plant capacity and BOM availability.

- **Primary Key**: `production_id`
- **Layer**: `dependent`
- **Foreign Keys**: `sku_id` -> `skus.sku_id`, `location_id` -> `locations.location_id`

| Field | Type | Required | Allowed Values | Units | Unique | Validation Rule |
|---|---|---|---|---|---|---|
| `production_id` | `str` | Required | PROD-2026-000001 | id | Yes | Regex ^PROD-\d{4}-\d{6}$ |
| `sku_id` | `str` | Required | Valid skus.sku_id | id | No | FK -> skus.sku_id |
| `location_id` | `str` | Required | Valid locations.location_id | id | No | FK -> locations.location_id (PLANT) |
| `week_id` | `str` | Required | 2026W01..2026W52 | iso_week | No | Regex ^\d{4}W\d{2}$ |
| `week_start_date` | `date` | Required | Monday of week_id | date | No | Matches ISO week Monday |
| `planned_qty` | `int` | Required | > 0 | units | No | planned_qty > 0 |
| `capacity_limit_qty` | `int` | Required | >= 0 | units | No | capacity_limit_qty >= 0 |
| `bom_feasible_qty` | `int` | Required | >= 0 | units | No | bom_feasible_qty >= 0 |
| `achievable_qty` | `int` | Required | min(planned, capacity, bom) | units | No | Derived == min(planned_qty, capacity_limit_qty, bom_feasible_qty) |
| `uom` | `str` | Required | EA, KG, L, CASE, PALLET | uom | No | Allowed UOM enum |
| `unit_production_cost` | `float` | Required | > 0 | INR | No | unit_production_cost > 0 |
| `lifecycle_state` | `str` | Required | PLANNED, SCHEDULED, IN_PROGRESS, COMPLETED, CONSTRAINED, CANCELLED | none | No | Must belong to ProductionStatus |
| `effective_from` | `date` | Required | ISO date YYYY-MM-DD | date | No | Valid ISO date |
| `effective_to` | `date` | Optional | ISO date YYYY-MM-DD or NULL | date | No | NULL or >= effective_from |

## ProjectedBalance (`projected_balances`)

Week-by-week inventory ledger reconciling opening stock, inbound POs, production, and forecast demand.

- **Primary Key**: `balance_id`
- **Layer**: `derived`
- **Foreign Keys**: `sku_id` -> `skus.sku_id`, `location_id` -> `locations.location_id`

| Field | Type | Required | Allowed Values | Units | Unique | Validation Rule |
|---|---|---|---|---|---|---|
| `balance_id` | `str` | Required | BAL-SKU-000001-LOC-0001-2026W01 | id | Yes | Regex ^BAL-SKU-\d{6}-LOC-\d{4}-\d{4}W\d{2}$ |
| `sku_id` | `str` | Required | Valid skus.sku_id | id | No | FK -> skus.sku_id |
| `location_id` | `str` | Required | Valid locations.location_id | id | No | FK -> locations.location_id |
| `week_id` | `str` | Required | 2026W01..2026W52 | iso_week | No | Regex ^\d{4}W\d{2}$ |
| `week_start_date` | `date` | Required | Monday of week_id | date | No | Matches ISO week Monday |
| `opening_stock` | `int` | Required | Derived carry-over | units | No | W01 == inventory.available_qty; Wt == closing_{t-1} |
| `inbound_qty` | `int` | Required | >= 0 | units | No | Derived sum of non-cancelled POs arriving in week |
| `production_qty` | `int` | Required | >= 0 | units | No | Derived sum of production achievable_qty in week |
| `demand_qty` | `int` | Required | >= 0 | units | No | Derived == forecast_demand.forecast_qty |
| `closing_stock` | `int` | Required | opening + inbound + prod - demand | units | No | Derived == opening_stock + inbound_qty + production_qty - demand_qty |
| `safety_stock_qty` | `int` | Required | >= 0 | units | No | Matches inventory.safety_stock_qty |
| `below_safety_stock` | `bool` | Required | true, false | flag | No | Derived == (closing_stock < safety_stock_qty) |
| `effective_from` | `date` | Required | ISO date YYYY-MM-DD | date | No | Valid ISO date |
| `effective_to` | `date` | Optional | ISO date YYYY-MM-DD or NULL | date | No | NULL or >= effective_from |
| `lifecycle_state` | `str` | Required | DRAFT, ACTIVE, SUSPENDED, RETIRED | none | No | Must belong to EntityStatus |

## Shortage (`shortages`)

Derived inventory deficit with explainable root cause, lead-time order-by date, and priority score.

- **Primary Key**: `shortage_id`
- **Layer**: `derived`
- **Foreign Keys**: `balance_id` -> `projected_balances.balance_id`, `sku_id` -> `skus.sku_id`, `location_id` -> `locations.location_id`

| Field | Type | Required | Allowed Values | Units | Unique | Validation Rule |
|---|---|---|---|---|---|---|
| `shortage_id` | `str` | Required | SHORT-2026-000001 | id | Yes | Regex ^SHORT-\d{4}-\d{6}$ |
| `balance_id` | `str` | Required | Valid projected_balances.balance_id | id | No | FK -> projected_balances.balance_id |
| `sku_id` | `str` | Required | Valid skus.sku_id | id | No | FK -> skus.sku_id |
| `location_id` | `str` | Required | Valid locations.location_id | id | No | FK -> locations.location_id |
| `week_id` | `str` | Required | 2026W01..2026W52 | iso_week | No | Regex ^\d{4}W\d{2}$ |
| `week_start_date` | `date` | Required | Monday of week_id | date | No | Matches ISO week Monday |
| `shortage_qty` | `int` | Required | > 0 | units | No | Derived == abs(closing_stock) |
| `revenue_at_risk` | `float` | Required | > 0 | INR | No | Derived == round(shortage_qty * sku.unit_price, 4) |
| `lead_time_days_used` | `int` | Required | >= 0 | days | No | Derived min supplier lead time (0 only if MAKE-only) |
| `required_order_by_date` | `date` | Required | week_start_date - lead_time_days_used | date | No | Derived == week_start_date - lead_time_days_used |
| `root_cause` | `str` | Required | DEMAND_SPIKE, LATE_INBOUND, SUPPLIER_CAPACITY_CAP, LEAD_TIME_GAP, PRODUCTION_CONSTRAINT, LOW_OPENING_INVENTORY, COMPOUND_DEFICIT | none | No | Allowed ShortageRootCause enum |
| `severity` | `str` | Required | CRITICAL, HIGH, MEDIUM, LOW | none | No | Allowed ShortageSeverity enum |
| `priority_score` | `float` | Required | 0.0 to 100.0 | score | No | 0 <= priority_score <= 100 |
| `priority_rank` | `int` | Required | >= 1 | rank | Yes | Unique dense rank 1..N |
| `lifecycle_state` | `str` | Required | OPEN, MITIGATION_PROPOSED, MITIGATED, RESOLVED, ESCALATED | none | No | Must belong to ShortageStatus |
| `effective_from` | `date` | Required | ISO date YYYY-MM-DD | date | No | Valid ISO date |
| `effective_to` | `date` | Optional | ISO date YYYY-MM-DD or NULL | date | No | NULL or >= effective_from |

## ShortageEvidence (`shortage_evidence`)

Traceability bridge linking each Shortage to the exact source rows explaining its root cause.

- **Primary Key**: `evidence_id`
- **Layer**: `derived`
- **Foreign Keys**: `shortage_id` -> `shortages.shortage_id`

| Field | Type | Required | Allowed Values | Units | Unique | Validation Rule |
|---|---|---|---|---|---|---|
| `evidence_id` | `str` | Required | EVID-2026-000001 | id | Yes | Regex ^EVID-\d{4}-\d{6}$ |
| `shortage_id` | `str` | Required | Valid shortages.shortage_id | id | No | FK -> shortages.shortage_id |
| `source_table` | `str` | Required | forecast_demand, inventory, purchase_orders, supplier_capacity, lead_times, production_plans | table | No | Valid source table name |
| `source_record_id` | `str` | Required | Valid PK in source_table | id | No | Must exist in source_table |
| `contribution_type` | `str` | Required | DEMAND_DRIVER, INVENTORY_BASELINE, INBOUND_DELAY, CAPACITY_BOTTLENECK, LEAD_TIME_CONSTRAINT, PRODUCTION_SHORTFALL | none | No | Allowed EvidenceContribution enum |
| `metric_value` | `float` | Required | Numeric | mixed | No | Finite number |
| `explanation` | `str` | Required | Non-empty text | text | No | len >= 5 |
| `effective_from` | `date` | Required | ISO date YYYY-MM-DD | date | No | Valid ISO date |
| `effective_to` | `date` | Optional | ISO date YYYY-MM-DD or NULL | date | No | NULL or >= effective_from |
| `lifecycle_state` | `str` | Required | DRAFT, ACTIVE, SUSPENDED, RETIRED | none | No | Must belong to EntityStatus |

## MitigationOption (`mitigation_options`)

Policy-checked, capacity-checked shortage mitigation alternatives with cost/service trade-offs.

- **Primary Key**: `mitigation_id`
- **Layer**: `derived`
- **Foreign Keys**: `shortage_id` -> `shortages.shortage_id`, `target_supplier_id` -> `suppliers.supplier_id` (optional), `target_sku_id` -> `skus.sku_id` (optional), `source_location_id` -> `locations.location_id` (optional)

| Field | Type | Required | Allowed Values | Units | Unique | Validation Rule |
|---|---|---|---|---|---|---|
| `mitigation_id` | `str` | Required | MIT-SHORT-2026-000001-01 | id | Yes | Regex ^MIT-SHORT-\d{4}-\d{6}-\d{2}$ |
| `shortage_id` | `str` | Required | Valid shortages.shortage_id | id | No | FK -> shortages.shortage_id |
| `mitigation_type` | `str` | Required | EXPEDITE_PO, ALTERNATE_SUPPLIER, SUBSTITUTE_SKU, INTER_LOCATION_TRANSFER, OVERTIME_PRODUCTION, DEMAND_REALLOCATION | none | No | Allowed MitigationType enum |
| `target_supplier_id` | `str` | Optional | Valid suppliers.supplier_id or NULL | id | No | Optional FK -> suppliers.supplier_id |
| `target_sku_id` | `str` | Optional | Valid skus.sku_id or NULL | id | No | Optional FK -> skus.sku_id |
| `source_location_id` | `str` | Optional | Valid locations.location_id or NULL | id | No | Optional FK -> locations.location_id |
| `mitigation_qty` | `int` | Required | > 0 | units | No | mitigation_qty > 0 |
| `cost` | `float` | Required | >= 0 | INR | No | cost >= 0 |
| `service_level_impact` | `float` | Required | 0.0 to 1.0 | ratio | No | 0 <= service_level_impact <= 1 |
| `lead_time_days` | `int` | Required | >= 0 | days | No | lead_time_days >= 0 |
| `capacity_check_passed` | `bool` | Required | true, false | flag | No | True in clean baseline |
| `policy_check_passed` | `bool` | Required | true, false | flag | No | True in clean baseline |
| `score` | `float` | Required | 0.0 to 100.0 | score | No | Derived weighted cost/service/lead-time score |
| `rank` | `int` | Required | >= 1 | rank | No | Unique rank 1..k per shortage_id |
| `lifecycle_state` | `str` | Required | PROPOSED, POLICY_VALIDATED, APPROVED, REJECTED, EXECUTED | none | No | Must belong to MitigationStatus |
| `effective_from` | `date` | Required | ISO date YYYY-MM-DD | date | No | Valid ISO date |
| `effective_to` | `date` | Optional | ISO date YYYY-MM-DD or NULL | date | No | NULL or >= effective_from |

## GroundTruth (`data/ground_truth/ground_truth.csv`)

Strictly isolated label table recording injected edge cases. Never imported or read by planning code.

| Field | Type | Required | Allowed Values | Units | Unique | Validation Rule |
|---|---|---|---|---|---|---|
| `ground_truth_id` | `str` | Required | `GT-2026-0001` | id | Yes | Regex `^GT-\d{4}-\d{4}$` |
| `issue_type` | `str` | Required | double_counted_inbound, unapproved_substitute, supplier_capacity_exceeded, shortage_without_lead_time, uom_mismatch | none | No | Allowed `IssueType` enum |
| `target_table` | `str` | Required | Valid registry table name | table | No | Exists in `ENTITY_REGISTRY` |
| `affected_id` | `str` | Required | Valid PK in `target_table` | id | No | Traceable to mutated row |
| `related_ids` | `str` | Required | Comma-separated parent/child IDs | id_list | No | Valid related record IDs |
| `expected_detection_rule` | `str` | Required | Documented domain SQL/rule | rule | No | Non-empty detection specification |
| `injected_detail` | `str` | Required | Audit description of mutation | text | No | Non-empty explanation |
