# Entity-Relationship Model & Lifecycle Design

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
