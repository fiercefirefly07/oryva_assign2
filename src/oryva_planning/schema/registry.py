"""Single source of truth for all entities, fields, relationships, SQL DDL, and data dictionary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from oryva_planning.schema.enums import (
    EntityStatus,
    EvidenceContribution,
    LocationType,
    MitigationStatus,
    MitigationType,
    PopularityTier,
    POStatus,
    ProductionStatus,
    Region,
    ReliabilityTier,
    ShortageRootCause,
    ShortageSeverity,
    ShortageStatus,
    SKUCategory,
    SourcingType,
    SupplierTier,
    UOM,
)

FORBIDDEN_INPUT_COLUMNS: frozenset[str] = frozenset(
    {
        "issue_type",
        "ground_truth",
        "ground_truth_id",
        "expected_detection_rule",
        "is_anomaly",
    }
)


def _enum_values(enum_cls: type[Enum]) -> str:
    return ", ".join(member.value for member in enum_cls)


@dataclass(frozen=True)
class FieldSpec:
    name: str
    dtype: str
    sql_type: str
    required: bool
    allowed_values: str
    units: str
    unique: bool
    validation_rule: str
    description: str
    primary_key: bool = False
    enum_cls: type[Enum] | None = None


@dataclass(frozen=True)
class ForeignKeySpec:
    column: str
    ref_table: str
    ref_column: str
    optional: bool = False


@dataclass(frozen=True)
class RelationshipSpec:
    target_entity: str
    cardinality: str
    via_column: str
    optional: bool = False
    notes: str = ""


@dataclass(frozen=True)
class EntitySpec:
    name: str
    table_name: str
    layer: str
    primary_key: str
    lifecycle_column: str
    description: str
    fields: tuple[FieldSpec, ...]
    foreign_keys: tuple[ForeignKeySpec, ...]
    relationships: tuple[RelationshipSpec, ...]

    def column_names(self) -> list[str]:
        return [field.name for field in self.fields]

    def enum_fields(self) -> list[FieldSpec]:
        return [field for field in self.fields if field.enum_cls is not None]

    def to_sql_ddl(self) -> str:
        lines: list[str] = []
        for field in self.fields:
            null_sql = " NOT NULL" if field.required else ""
            unique_sql = " UNIQUE" if (field.unique and not field.primary_key) else ""
            lines.append(f"    {field.name} {field.sql_type}{null_sql}{unique_sql}")
        lines.append(f"    PRIMARY KEY ({self.primary_key})")
        for fk in self.foreign_keys:
            lines.append(
                f"    FOREIGN KEY ({fk.column}) REFERENCES {fk.ref_table}({fk.ref_column})"
            )
        body = ",\n".join(lines)
        return f"CREATE TABLE {self.table_name} (\n{body}\n);"

    def to_markdown_table(self) -> str:
        header = (
            "| Field | Type | Required | Allowed Values | Units | Unique | Validation Rule |\n"
            "|---|---|---|---|---|---|---|"
        )
        rows = [
            f"| `{f.name}` | `{f.dtype}` | {'Required' if f.required else 'Optional'} "
            f"| {f.allowed_values} | {f.units} | {'Yes' if f.unique else 'No'} "
            f"| {f.validation_rule} |"
            for f in self.fields
        ]
        return "\n".join([header, *rows])


def _effective_date_fields() -> tuple[FieldSpec, FieldSpec]:
    return (
        FieldSpec(
            name="effective_from",
            dtype="date",
            sql_type="DATE",
            required=True,
            allowed_values="ISO date YYYY-MM-DD",
            units="date",
            unique=False,
            validation_rule="Valid ISO date",
            description="Date from which this record is effective.",
        ),
        FieldSpec(
            name="effective_to",
            dtype="date",
            sql_type="DATE",
            required=False,
            allowed_values="ISO date YYYY-MM-DD or NULL",
            units="date",
            unique=False,
            validation_rule="NULL or >= effective_from",
            description="Optional end date for record validity.",
        ),
    )


def _lifecycle_field(enum_cls: type[Enum], name: str = "lifecycle_state") -> FieldSpec:
    return FieldSpec(
        name=name,
        dtype="str",
        sql_type="VARCHAR",
        required=True,
        allowed_values=_enum_values(enum_cls),
        units="none",
        unique=False,
        validation_rule=f"Must belong to {enum_cls.__name__}",
        description="Current lifecycle state of the record.",
        enum_cls=enum_cls,
    )


_ENTITIES: tuple[EntitySpec, ...] = (
    EntitySpec(
        name="SKU",
        table_name="skus",
        layer="master",
        primary_key="sku_id",
        lifecycle_column="lifecycle_state",
        description="Stock Keeping Unit master catalog with costing, sourcing, and Pareto velocity tier.",
        fields=(
            FieldSpec("sku_id", "str", "VARCHAR", True, "SKU-000001", "id", True, "Regex ^SKU-\d{6}$", "Immutable SKU identifier.", primary_key=True),
            FieldSpec("sku_name", "str", "VARCHAR", True, "Non-empty text", "text", False, "len >= 3", "Human-readable SKU title."),
            FieldSpec("category", "str", "VARCHAR", True, _enum_values(SKUCategory), "none", False, "Allowed SKUCategory enum", "Product category.", enum_cls=SKUCategory),
            FieldSpec("sourcing_type", "str", "VARCHAR", True, _enum_values(SourcingType), "none", False, "Allowed SourcingType enum", "Buy, Make, or Both.", enum_cls=SourcingType),
            FieldSpec("base_uom", "str", "VARCHAR", True, _enum_values(UOM), "uom", False, "Allowed UOM enum", "Canonical planning unit of measure.", enum_cls=UOM),
            FieldSpec("unit_cost", "float", "DOUBLE", True, "> 0", "INR", False, "unit_cost > 0", "Standard unit procurement or build cost."),
            FieldSpec("unit_price", "float", "DOUBLE", True, ">= unit_cost", "INR", False, "unit_price >= unit_cost", "Standard selling price per base unit."),
            FieldSpec("weight_kg", "float", "DOUBLE", True, "> 0", "kg", False, "weight_kg > 0", "Unit gross weight in kilograms."),
            FieldSpec("popularity_rank", "int", "INTEGER", True, ">= 1", "rank", True, "Unique positive rank", "Pareto popularity rank (1 = fastest mover)."),
            FieldSpec("popularity_tier", "str", "VARCHAR", True, _enum_values(PopularityTier), "none", False, "Allowed PopularityTier enum", "ABC velocity classification.", enum_cls=PopularityTier),
            FieldSpec("is_critical", "bool", "BOOLEAN", True, "true, false", "flag", False, "Boolean", "High-service priority flag."),
            *_effective_date_fields(),
            _lifecycle_field(EntityStatus),
        ),
        foreign_keys=(),
        relationships=(
            RelationshipSpec("ForecastDemand", "1:N", "sku_id", False, "Weekly demand per location."),
            RelationshipSpec("Inventory", "1:N", "sku_id", False, "On-hand stock per location."),
            RelationshipSpec("Supplier", "N:M", "sku_suppliers", False, "Bridged via sku_suppliers."),
            RelationshipSpec("SKU", "N:M", "sku_substitutes", True, "Approved/unapproved substitutes."),
            RelationshipSpec("SKU", "N:M", "bom_items", True, "Bill of materials parent-component links."),
        ),
    ),
    EntitySpec(
        name="Location",
        table_name="locations",
        layer="master",
        primary_key="location_id",
        lifecycle_column="lifecycle_state",
        description="Warehouses, distribution centres, plants, and regional hubs.",
        fields=(
            FieldSpec("location_id", "str", "VARCHAR", True, "LOC-0001", "id", True, "Regex ^LOC-\d{4}$", "Immutable location identifier.", primary_key=True),
            FieldSpec("location_name", "str", "VARCHAR", True, "Non-empty text", "text", False, "len >= 3", "Facility name."),
            FieldSpec("location_type", "str", "VARCHAR", True, _enum_values(LocationType), "none", False, "Allowed LocationType enum", "Facility role.", enum_cls=LocationType),
            FieldSpec("region", "str", "VARCHAR", True, _enum_values(Region), "none", False, "Allowed Region enum", "Geographic operating region.", enum_cls=Region),
            FieldSpec("storage_capacity_units", "int", "INTEGER", True, "> 0", "units", False, "storage_capacity_units > 0", "Maximum unit holding capacity."),
            FieldSpec("daily_production_capacity", "int", "INTEGER", True, ">= 0", "units/day", False, "0 unless PLANT; >= 0", "Daily manufacturing throughput."),
            FieldSpec("holding_cost_per_unit_week", "float", "DOUBLE", True, "> 0", "INR/unit/week", False, "holding_cost_per_unit_week > 0", "Weekly inventory carrying cost."),
            *_effective_date_fields(),
            _lifecycle_field(EntityStatus),
        ),
        foreign_keys=(),
        relationships=(
            RelationshipSpec("ForecastDemand", "1:N", "location_id", False, "Location weekly demand."),
            RelationshipSpec("Inventory", "1:N", "location_id", False, "Stock stored at location."),
            RelationshipSpec("ProductionPlan", "1:N", "location_id", True, "Production scheduled at plant."),
        ),
    ),
    EntitySpec(
        name="Supplier",
        table_name="suppliers",
        layer="master",
        primary_key="supplier_id",
        lifecycle_column="lifecycle_state",
        description="External vendor master with tiering, reliability, capacity constraint flag, and expedite surcharges.",
        fields=(
            FieldSpec("supplier_id", "str", "VARCHAR", True, "SUP-0001", "id", True, "Regex ^SUP-\d{4}$", "Immutable supplier identifier.", primary_key=True),
            FieldSpec("supplier_name", "str", "VARCHAR", True, "Non-empty text", "text", False, "len >= 3", "Supplier legal/trade name."),
            FieldSpec("region", "str", "VARCHAR", True, _enum_values(Region), "none", False, "Allowed Region enum", "Primary dispatch region.", enum_cls=Region),
            FieldSpec("supplier_tier", "str", "VARCHAR", True, _enum_values(SupplierTier), "none", False, "Allowed SupplierTier enum", "Commercial tier.", enum_cls=SupplierTier),
            FieldSpec("reliability_tier", "str", "VARCHAR", True, _enum_values(ReliabilityTier), "none", False, "Allowed ReliabilityTier enum", "Historical delivery reliability class.", enum_cls=ReliabilityTier),
            FieldSpec("on_time_rate", "float", "DOUBLE", True, "0.0 to 1.0", "ratio", False, "0 <= on_time_rate <= 1", "Expected on-time delivery ratio."),
            FieldSpec("is_constrained", "bool", "BOOLEAN", True, "true, false", "flag", False, "Boolean", "Indicates tight weekly capacity."),
            FieldSpec("expedite_surcharge_pct", "float", "DOUBLE", True, "0.0 to 1.0", "ratio", False, "0 <= expedite_surcharge_pct <= 1", "Percentage surcharge for expedited POs."),
            *_effective_date_fields(),
            _lifecycle_field(EntityStatus),
        ),
        foreign_keys=(),
        relationships=(
            RelationshipSpec("SupplierCapacity", "1:N", "supplier_id", False, "Weekly capacity ceiling."),
            RelationshipSpec("PurchaseOrder", "1:N", "supplier_id", False, "Inbound purchase orders."),
            RelationshipSpec("SKU", "N:M", "sku_suppliers", False, "Bridged via sku_suppliers."),
        ),
    ),
    EntitySpec(
        name="SKUSupplier",
        table_name="sku_suppliers",
        layer="bridge",
        primary_key="sku_supplier_id",
        lifecycle_column="lifecycle_state",
        description="Many-to-many approved sourcing agreements between SKUs and Suppliers.",
        fields=(
            FieldSpec("sku_supplier_id", "str", "VARCHAR", True, "SS-SKU-000001-SUP-0001", "id", True, "Regex ^SS-SKU-\d{6}-SUP-\d{4}$", "Bridge primary key.", primary_key=True),
            FieldSpec("sku_id", "str", "VARCHAR", True, "Valid skus.sku_id", "id", False, "FK -> skus.sku_id", "Referenced SKU."),
            FieldSpec("supplier_id", "str", "VARCHAR", True, "Valid suppliers.supplier_id", "id", False, "FK -> suppliers.supplier_id", "Referenced Supplier."),
            FieldSpec("unit_purchase_cost", "float", "DOUBLE", True, "> 0", "INR", False, "unit_purchase_cost > 0", "Contracted purchase price."),
            FieldSpec("min_order_qty", "int", "INTEGER", True, ">= 1", "units", False, "min_order_qty >= 1", "Minimum order quantity (MOQ)."),
            FieldSpec("order_multiple", "int", "INTEGER", True, ">= 1", "units", False, "order_multiple >= 1", "Lot-size rounding increment."),
            FieldSpec("is_primary", "bool", "BOOLEAN", True, "true, false", "flag", False, "Boolean", "Primary vendor indicator for this SKU."),
            FieldSpec("contract_uom", "str", "VARCHAR", True, _enum_values(UOM), "uom", False, "Allowed UOM enum; matches SKU base_uom in baseline", "Ordering UOM.", enum_cls=UOM),
            *_effective_date_fields(),
            _lifecycle_field(EntityStatus),
        ),
        foreign_keys=(
            ForeignKeySpec("sku_id", "skus", "sku_id"),
            ForeignKeySpec("supplier_id", "suppliers", "supplier_id"),
        ),
        relationships=(
            RelationshipSpec("SKU", "N:1", "sku_id", False, "SKU side of sourcing bridge."),
            RelationshipSpec("Supplier", "N:1", "supplier_id", False, "Supplier side of sourcing bridge."),
        ),
    ),
    EntitySpec(
        name="SKUSubstitute",
        table_name="sku_substitutes",
        layer="bridge",
        primary_key="sku_substitute_id",
        lifecycle_column="lifecycle_state",
        description="Approved and unapproved substitute SKU mappings for shortage mitigation.",
        fields=(
            FieldSpec("sku_substitute_id", "str", "VARCHAR", True, "SUB-SKU-000001-SKU-000002", "id", True, "Regex ^SUB-SKU-\d{6}-SKU-\d{6}$", "Bridge primary key.", primary_key=True),
            FieldSpec("sku_id", "str", "VARCHAR", True, "Valid skus.sku_id", "id", False, "FK -> skus.sku_id", "Primary SKU experiencing shortage."),
            FieldSpec("substitute_sku_id", "str", "VARCHAR", True, "Valid skus.sku_id != sku_id", "id", False, "FK -> skus.sku_id; != sku_id", "Candidate replacement SKU."),
            FieldSpec("approved", "bool", "BOOLEAN", True, "true, false", "flag", False, "Boolean; policy requires true for mitigation", "Engineering/policy approval flag."),
            FieldSpec("conversion_factor", "float", "DOUBLE", True, "> 0", "ratio", False, "conversion_factor > 0", "Units of substitute per unit of primary SKU."),
            FieldSpec("cost_delta_pct", "float", "DOUBLE", True, "-0.5 to 1.0", "ratio", False, "-0.5 <= cost_delta_pct <= 1.0", "Relative cost difference vs primary SKU."),
            FieldSpec("priority_rank", "int", "INTEGER", True, ">= 1", "rank", False, "priority_rank >= 1", "Substitution preference order."),
            *_effective_date_fields(),
            _lifecycle_field(EntityStatus),
        ),
        foreign_keys=(
            ForeignKeySpec("sku_id", "skus", "sku_id"),
            ForeignKeySpec("substitute_sku_id", "skus", "sku_id"),
        ),
        relationships=(
            RelationshipSpec("SKU", "N:1", "sku_id", False, "Primary SKU."),
            RelationshipSpec("SKU", "N:1", "substitute_sku_id", False, "Substitute SKU."),
        ),
    ),
    EntitySpec(
        name="BOMItem",
        table_name="bom_items",
        layer="bridge",
        primary_key="bom_id",
        lifecycle_column="lifecycle_state",
        description="Bill of Materials linking manufactured parent SKUs to component SKUs.",
        fields=(
            FieldSpec("bom_id", "str", "VARCHAR", True, "BOM-SKU-000001-SKU-000002", "id", True, "Regex ^BOM-SKU-\d{6}-SKU-\d{6}$", "BOM link primary key.", primary_key=True),
            FieldSpec("parent_sku_id", "str", "VARCHAR", True, "Valid skus.sku_id", "id", False, "FK -> skus.sku_id (MAKE or BOTH)", "Manufactured parent SKU."),
            FieldSpec("component_sku_id", "str", "VARCHAR", True, "Valid skus.sku_id != parent_sku_id", "id", False, "FK -> skus.sku_id; != parent_sku_id", "Required component SKU."),
            FieldSpec("qty_per_parent", "float", "DOUBLE", True, "> 0", "units/parent", False, "qty_per_parent > 0", "Component quantity needed per unit of parent."),
            FieldSpec("uom", "str", "VARCHAR", True, _enum_values(UOM), "uom", False, "Allowed UOM enum", "Unit of measure for BOM quantity.", enum_cls=UOM),
            FieldSpec("scrap_rate", "float", "DOUBLE", True, "0.0 to 0.3", "ratio", False, "0 <= scrap_rate <= 0.3", "Expected manufacturing scrap fraction."),
            *_effective_date_fields(),
            _lifecycle_field(EntityStatus),
        ),
        foreign_keys=(
            ForeignKeySpec("parent_sku_id", "skus", "sku_id"),
            ForeignKeySpec("component_sku_id", "skus", "sku_id"),
        ),
        relationships=(
            RelationshipSpec("SKU", "N:1", "parent_sku_id", False, "Manufactured parent SKU."),
            RelationshipSpec("SKU", "N:1", "component_sku_id", False, "Component SKU."),
        ),
    ),
    EntitySpec(
        name="ForecastDemand",
        table_name="forecast_demand",
        layer="dependent",
        primary_key="demand_id",
        lifecycle_column="lifecycle_state",
        description="Weekly SKU-location forecast demand generated with Pareto popularity, seasonality, and spikes.",
        fields=(
            FieldSpec("demand_id", "str", "VARCHAR", True, "DEM-SKU-000001-LOC-0001-2026W01", "id", True, "Regex ^DEM-SKU-\d{6}-LOC-\d{4}-\d{4}W\d{2}$", "Immutable demand record ID.", primary_key=True),
            FieldSpec("sku_id", "str", "VARCHAR", True, "Valid skus.sku_id", "id", False, "FK -> skus.sku_id", "Demanded SKU."),
            FieldSpec("location_id", "str", "VARCHAR", True, "Valid locations.location_id", "id", False, "FK -> locations.location_id", "Demand location."),
            FieldSpec("week_id", "str", "VARCHAR", True, "2026W01..2026W52", "iso_week", False, "Regex ^\d{4}W\d{2}$", "ISO planning week."),
            FieldSpec("week_start_date", "date", "DATE", True, "Monday of week_id", "date", False, "Matches ISO week Monday", "Start date of planning week."),
            FieldSpec("forecast_qty", "int", "INTEGER", True, ">= 0", "units", False, "forecast_qty >= 0", "Weekly forecast demand quantity."),
            FieldSpec("uom", "str", "VARCHAR", True, _enum_values(UOM), "uom", False, "Allowed UOM enum; matches SKU base_uom in baseline", "Demand unit of measure.", enum_cls=UOM),
            FieldSpec("is_spike_week", "bool", "BOOLEAN", True, "true, false", "flag", False, "Boolean", "Indicates synthetic demand spike week."),
            FieldSpec("seasonality_factor", "float", "DOUBLE", True, "> 0", "multiplier", False, "seasonality_factor > 0", "Applied seasonal multiplier."),
            FieldSpec("priority_weight", "float", "DOUBLE", True, "> 0", "score", False, "priority_weight > 0", "Service priority weight for shortage ranking."),
            *_effective_date_fields(),
            _lifecycle_field(EntityStatus),
        ),
        foreign_keys=(
            ForeignKeySpec("sku_id", "skus", "sku_id"),
            ForeignKeySpec("location_id", "locations", "location_id"),
        ),
        relationships=(
            RelationshipSpec("SKU", "N:1", "sku_id", False, "Parent SKU."),
            RelationshipSpec("Location", "N:1", "location_id", False, "Parent Location."),
        ),
    ),
    EntitySpec(
        name="Inventory",
        table_name="inventory",
        layer="dependent",
        primary_key="inventory_id",
        lifecycle_column="lifecycle_state",
        description="Opening SKU-location inventory snapshot with derived available stock.",
        fields=(
            FieldSpec("inventory_id", "str", "VARCHAR", True, "INV-SKU-000001-LOC-0001", "id", True, "Regex ^INV-SKU-\d{6}-LOC-\d{4}$", "Immutable inventory snapshot ID.", primary_key=True),
            FieldSpec("sku_id", "str", "VARCHAR", True, "Valid skus.sku_id", "id", False, "FK -> skus.sku_id", "Stocked SKU."),
            FieldSpec("location_id", "str", "VARCHAR", True, "Valid locations.location_id", "id", False, "FK -> locations.location_id", "Storage location."),
            FieldSpec("snapshot_date", "date", "DATE", True, "ISO date", "date", False, "Matches planning start date", "Opening balance cut-off date."),
            FieldSpec("on_hand_qty", "int", "INTEGER", True, ">= 0", "units", False, "on_hand_qty >= 0", "Physical stock on hand."),
            FieldSpec("reserved_qty", "int", "INTEGER", True, "0..on_hand_qty", "units", False, "0 <= reserved_qty <= on_hand_qty", "Stock allocated to existing commitments."),
            FieldSpec("available_qty", "int", "INTEGER", True, "on_hand_qty - reserved_qty", "units", False, "Derived == on_hand_qty - reserved_qty", "Net opening stock available for planning."),
            FieldSpec("safety_stock_qty", "int", "INTEGER", True, ">= 0", "units", False, "safety_stock_qty >= 0", "Target buffer inventory."),
            FieldSpec("reorder_point_qty", "int", "INTEGER", True, ">= safety_stock_qty", "units", False, "reorder_point_qty >= safety_stock_qty", "Replenishment trigger threshold."),
            FieldSpec("uom", "str", "VARCHAR", True, _enum_values(UOM), "uom", False, "Allowed UOM enum; matches SKU base_uom in baseline", "Inventory unit of measure.", enum_cls=UOM),
            *_effective_date_fields(),
            _lifecycle_field(EntityStatus),
        ),
        foreign_keys=(
            ForeignKeySpec("sku_id", "skus", "sku_id"),
            ForeignKeySpec("location_id", "locations", "location_id"),
        ),
        relationships=(
            RelationshipSpec("SKU", "N:1", "sku_id", False, "Parent SKU."),
            RelationshipSpec("Location", "N:1", "location_id", False, "Parent Location."),
        ),
    ),
    EntitySpec(
        name="SupplierCapacity",
        table_name="supplier_capacity",
        layer="dependent",
        primary_key="capacity_id",
        lifecycle_column="lifecycle_state",
        description="Weekly supplier output ceilings and derived committed/available capacity.",
        fields=(
            FieldSpec("capacity_id", "str", "VARCHAR", True, "CAP-SUP-0001-2026W01", "id", True, "Regex ^CAP-SUP-\d{4}-\d{4}W\d{2}$", "Immutable weekly capacity ID.", primary_key=True),
            FieldSpec("supplier_id", "str", "VARCHAR", True, "Valid suppliers.supplier_id", "id", False, "FK -> suppliers.supplier_id", "Supplier identifier."),
            FieldSpec("week_id", "str", "VARCHAR", True, "2026W01..2026W52", "iso_week", False, "Regex ^\d{4}W\d{2}$", "ISO planning week."),
            FieldSpec("week_start_date", "date", "DATE", True, "Monday of week_id", "date", False, "Matches ISO week Monday", "Week start date."),
            FieldSpec("max_weekly_capacity", "int", "INTEGER", True, "> 0", "units", False, "max_weekly_capacity > 0", "Maximum units supplier can supply in week."),
            FieldSpec("committed_qty", "int", "INTEGER", True, ">= 0", "units", False, "Derived sum of active POs for supplier-week", "Capacity already booked by POs."),
            FieldSpec("available_capacity", "int", "INTEGER", True, "max - committed", "units", False, "Derived == max_weekly_capacity - committed_qty; >= 0 in baseline", "Remaining capacity available for mitigations."),
            *_effective_date_fields(),
            _lifecycle_field(EntityStatus),
        ),
        foreign_keys=(ForeignKeySpec("supplier_id", "suppliers", "supplier_id"),),
        relationships=(RelationshipSpec("Supplier", "N:1", "supplier_id", False, "Owning supplier."),),
    ),
    EntitySpec(
        name="LeadTime",
        table_name="lead_times",
        layer="dependent",
        primary_key="lead_time_id",
        lifecycle_column="lifecycle_state",
        description="SKU-supplier-location replenishment lead times and MOQ constraints.",
        fields=(
            FieldSpec("lead_time_id", "str", "VARCHAR", True, "LT-SKU-000001-SUP-0001-LOC-0001", "id", True, "Regex ^LT-SKU-\d{6}-SUP-\d{4}-LOC-\d{4}$", "Immutable lead time ID.", primary_key=True),
            FieldSpec("sku_id", "str", "VARCHAR", True, "Valid skus.sku_id", "id", False, "FK -> skus.sku_id", "Replenished SKU."),
            FieldSpec("supplier_id", "str", "VARCHAR", True, "Valid suppliers.supplier_id", "id", False, "FK -> suppliers.supplier_id", "Supplying vendor."),
            FieldSpec("location_id", "str", "VARCHAR", True, "Valid locations.location_id", "id", False, "FK -> locations.location_id", "Receiving location."),
            FieldSpec("manufacturing_days", "int", "INTEGER", True, ">= 1", "days", False, "manufacturing_days >= 1", "Vendor production/prep days."),
            FieldSpec("transit_days", "int", "INTEGER", True, ">= 1", "days", False, "transit_days >= 1", "Standard carrier transit days."),
            FieldSpec("customs_buffer_days", "int", "INTEGER", True, ">= 0", "days", False, "customs_buffer_days >= 0", "Receiving/customs handling buffer."),
            FieldSpec("total_lead_time_days", "int", "INTEGER", True, "sum of components", "days", False, "Derived == manufacturing + transit + customs", "Total nominal lead time."),
            FieldSpec("min_order_qty", "int", "INTEGER", True, ">= 1", "units", False, "min_order_qty >= 1", "Minimum replenishment order quantity."),
            *_effective_date_fields(),
            _lifecycle_field(EntityStatus),
        ),
        foreign_keys=(
            ForeignKeySpec("sku_id", "skus", "sku_id"),
            ForeignKeySpec("supplier_id", "suppliers", "supplier_id"),
            ForeignKeySpec("location_id", "locations", "location_id"),
        ),
        relationships=(
            RelationshipSpec("SKU", "N:1", "sku_id", False, "SKU."),
            RelationshipSpec("Supplier", "N:1", "supplier_id", False, "Supplier."),
            RelationshipSpec("Location", "N:1", "location_id", False, "Destination location."),
        ),
    ),
    EntitySpec(
        name="PurchaseOrder",
        table_name="purchase_orders",
        layer="dependent",
        primary_key="po_id",
        lifecycle_column="current_status",
        description="Inbound supplier purchase orders with derived costs and event-sourced status.",
        fields=(
            FieldSpec("po_id", "str", "VARCHAR", True, "PO-2026-000001", "id", True, "Regex ^PO-\d{4}-\d{6}$", "Immutable PO identifier.", primary_key=True),
            FieldSpec("sku_id", "str", "VARCHAR", True, "Valid skus.sku_id", "id", False, "FK -> skus.sku_id", "Ordered SKU."),
            FieldSpec("supplier_id", "str", "VARCHAR", True, "Valid suppliers.supplier_id", "id", False, "FK -> suppliers.supplier_id", "Fulfilling supplier."),
            FieldSpec("location_id", "str", "VARCHAR", True, "Valid locations.location_id", "id", False, "FK -> locations.location_id", "Ship-to location."),
            FieldSpec("order_date", "date", "DATE", True, "ISO date", "date", False, "order_date <= promised_delivery_date", "PO placement date."),
            FieldSpec("promised_delivery_date", "date", "DATE", True, "ISO date", "date", False, ">= order_date", "Baseline expected delivery date."),
            FieldSpec("actual_delivery_date", "date", "DATE", False, "ISO date or NULL", "date", False, "NULL if cancelled; >= order_date", "Expected/actual arrival including transport delay."),
            FieldSpec("arrival_week_id", "str", "VARCHAR", True, "2026W01..2026W52", "iso_week", False, "Derived ISO week of effective delivery date", "Planning week inbound lands."),
            FieldSpec("order_qty", "int", "INTEGER", True, "> 0", "units", False, "order_qty > 0", "Ordered quantity."),
            FieldSpec("uom", "str", "VARCHAR", True, _enum_values(UOM), "uom", False, "Allowed UOM enum; matches SKU base_uom in baseline", "PO unit of measure.", enum_cls=UOM),
            FieldSpec("unit_cost", "float", "DOUBLE", True, "> 0", "INR", False, "unit_cost > 0", "Contracted unit price."),
            FieldSpec("total_cost", "float", "DOUBLE", True, "order_qty * unit_cost", "INR", False, "Derived == round(order_qty * unit_cost, 4)", "Extended PO value."),
            FieldSpec("transport_delay_days", "int", "INTEGER", True, ">= 0", "days", False, "transport_delay_days >= 0", "Carrier/transit delay in days."),
            _lifecycle_field(POStatus, name="current_status"),
            *_effective_date_fields(),
        ),
        foreign_keys=(
            ForeignKeySpec("sku_id", "skus", "sku_id"),
            ForeignKeySpec("supplier_id", "suppliers", "supplier_id"),
            ForeignKeySpec("location_id", "locations", "location_id"),
        ),
        relationships=(
            RelationshipSpec("SKU", "N:1", "sku_id", False, "Ordered SKU."),
            RelationshipSpec("Supplier", "N:1", "supplier_id", False, "Vendor."),
            RelationshipSpec("Location", "N:1", "location_id", False, "Destination."),
            RelationshipSpec("PurchaseOrderEvent", "1:N", "po_id", False, "Immutable status transition log."),
        ),
    ),
    EntitySpec(
        name="PurchaseOrderEvent",
        table_name="purchase_order_events",
        layer="event",
        primary_key="event_id",
        lifecycle_column="lifecycle_state",
        description="Append-only state transition history for PurchaseOrder lifecycle.",
        fields=(
            FieldSpec("event_id", "str", "VARCHAR", True, "POE-2026-0000001", "id", True, "Regex ^POE-\d{4}-\d{7}$", "Immutable event ID.", primary_key=True),
            FieldSpec("po_id", "str", "VARCHAR", True, "Valid purchase_orders.po_id", "id", False, "FK -> purchase_orders.po_id", "Associated PO."),
            FieldSpec("sequence_num", "int", "INTEGER", True, ">= 1", "seq", False, "Monotonic 1..k per po_id", "Event order within PO."),
            FieldSpec("from_status", "str", "VARCHAR", False, f"NULL or {_enum_values(POStatus)}", "none", False, "Valid transition predecessor", "Prior PO status."),
            FieldSpec("to_status", "str", "VARCHAR", True, _enum_values(POStatus), "none", False, "Valid transition target", "New PO status.", enum_cls=POStatus),
            FieldSpec("event_ts", "datetime", "TIMESTAMP", True, "ISO-8601 UTC timestamp", "timestamp", False, "Non-decreasing per po_id", "Deterministic event timestamp."),
            FieldSpec("actor", "str", "VARCHAR", True, "PLANNER, SUPPLIER, CARRIER, WAREHOUSE, OPS_MANAGER", "role", False, "Non-empty system actor", "Actor triggering transition."),
            FieldSpec("reason", "str", "VARCHAR", True, "Non-empty text", "text", False, "len >= 3", "Business reason for state change."),
            *_effective_date_fields(),
            _lifecycle_field(EntityStatus),
        ),
        foreign_keys=(ForeignKeySpec("po_id", "purchase_orders", "po_id"),),
        relationships=(RelationshipSpec("PurchaseOrder", "N:1", "po_id", False, "Parent purchase order."),),
    ),
    EntitySpec(
        name="ProductionPlan",
        table_name="production_plans",
        layer="dependent",
        primary_key="production_id",
        lifecycle_column="lifecycle_state",
        description="Weekly internal production schedule constrained by plant capacity and BOM availability.",
        fields=(
            FieldSpec("production_id", "str", "VARCHAR", True, "PROD-2026-000001", "id", True, "Regex ^PROD-\d{4}-\d{6}$", "Immutable production order ID.", primary_key=True),
            FieldSpec("sku_id", "str", "VARCHAR", True, "Valid skus.sku_id", "id", False, "FK -> skus.sku_id", "Manufactured SKU."),
            FieldSpec("location_id", "str", "VARCHAR", True, "Valid locations.location_id", "id", False, "FK -> locations.location_id (PLANT)", "Manufacturing plant."),
            FieldSpec("week_id", "str", "VARCHAR", True, "2026W01..2026W52", "iso_week", False, "Regex ^\d{4}W\d{2}$", "Production ISO week."),
            FieldSpec("week_start_date", "date", "DATE", True, "Monday of week_id", "date", False, "Matches ISO week Monday", "Week start date."),
            FieldSpec("planned_qty", "int", "INTEGER", True, "> 0", "units", False, "planned_qty > 0", "Requested build quantity."),
            FieldSpec("capacity_limit_qty", "int", "INTEGER", True, ">= 0", "units", False, "capacity_limit_qty >= 0", "Plant capacity cap allocated to SKU."),
            FieldSpec("bom_feasible_qty", "int", "INTEGER", True, ">= 0", "units", False, "bom_feasible_qty >= 0", "Maximum units buildable from component stock."),
            FieldSpec("achievable_qty", "int", "INTEGER", True, "min(planned, capacity, bom)", "units", False, "Derived == min(planned_qty, capacity_limit_qty, bom_feasible_qty)", "Net production output."),
            FieldSpec("uom", "str", "VARCHAR", True, _enum_values(UOM), "uom", False, "Allowed UOM enum", "Production unit of measure.", enum_cls=UOM),
            FieldSpec("unit_production_cost", "float", "DOUBLE", True, "> 0", "INR", False, "unit_production_cost > 0", "Unit internal manufacturing cost."),
            _lifecycle_field(ProductionStatus),
            *_effective_date_fields(),
        ),
        foreign_keys=(
            ForeignKeySpec("sku_id", "skus", "sku_id"),
            ForeignKeySpec("location_id", "locations", "location_id"),
        ),
        relationships=(
            RelationshipSpec("SKU", "N:1", "sku_id", False, "Manufactured SKU."),
            RelationshipSpec("Location", "N:1", "location_id", False, "Manufacturing plant."),
        ),
    ),
    EntitySpec(
        name="ProjectedBalance",
        table_name="projected_balances",
        layer="derived",
        primary_key="balance_id",
        lifecycle_column="lifecycle_state",
        description="Week-by-week inventory ledger reconciling opening stock, inbound POs, production, and forecast demand.",
        fields=(
            FieldSpec("balance_id", "str", "VARCHAR", True, "BAL-SKU-000001-LOC-0001-2026W01", "id", True, "Regex ^BAL-SKU-\d{6}-LOC-\d{4}-\d{4}W\d{2}$", "Immutable weekly balance key.", primary_key=True),
            FieldSpec("sku_id", "str", "VARCHAR", True, "Valid skus.sku_id", "id", False, "FK -> skus.sku_id", "SKU."),
            FieldSpec("location_id", "str", "VARCHAR", True, "Valid locations.location_id", "id", False, "FK -> locations.location_id", "Location."),
            FieldSpec("week_id", "str", "VARCHAR", True, "2026W01..2026W52", "iso_week", False, "Regex ^\d{4}W\d{2}$", "ISO planning week."),
            FieldSpec("week_start_date", "date", "DATE", True, "Monday of week_id", "date", False, "Matches ISO week Monday", "Week start date."),
            FieldSpec("opening_stock", "int", "INTEGER", True, "Derived carry-over", "units", False, "W01 == inventory.available_qty; Wt == closing_{t-1}", "Opening available inventory."),
            FieldSpec("inbound_qty", "int", "INTEGER", True, ">= 0", "units", False, "Derived sum of non-cancelled POs arriving in week", "Inbound PO receipts."),
            FieldSpec("production_qty", "int", "INTEGER", True, ">= 0", "units", False, "Derived sum of production achievable_qty in week", "Internal production receipts."),
            FieldSpec("demand_qty", "int", "INTEGER", True, ">= 0", "units", False, "Derived == forecast_demand.forecast_qty", "Weekly forecast demand."),
            FieldSpec("closing_stock", "int", "INTEGER", True, "opening + inbound + prod - demand", "units", False, "Derived == opening_stock + inbound_qty + production_qty - demand_qty", "Projected ending available balance."),
            FieldSpec("safety_stock_qty", "int", "INTEGER", True, ">= 0", "units", False, "Matches inventory.safety_stock_qty", "Target safety stock threshold."),
            FieldSpec("below_safety_stock", "bool", "BOOLEAN", True, "true, false", "flag", False, "Derived == (closing_stock < safety_stock_qty)", "True when closing balance dips under safety stock."),
            *_effective_date_fields(),
            _lifecycle_field(EntityStatus),
        ),
        foreign_keys=(
            ForeignKeySpec("sku_id", "skus", "sku_id"),
            ForeignKeySpec("location_id", "locations", "location_id"),
        ),
        relationships=(
            RelationshipSpec("SKU", "N:1", "sku_id", False, "SKU."),
            RelationshipSpec("Location", "N:1", "location_id", False, "Location."),
            RelationshipSpec("Shortage", "1:1", "balance_id", True, "Shortage raised when closing_stock < 0."),
        ),
    ),
    EntitySpec(
        name="Shortage",
        table_name="shortages",
        layer="derived",
        primary_key="shortage_id",
        lifecycle_column="lifecycle_state",
        description="Derived inventory deficit with explainable root cause, lead-time order-by date, and priority score.",
        fields=(
            FieldSpec("shortage_id", "str", "VARCHAR", True, "SHORT-2026-000001", "id", True, "Regex ^SHORT-\d{4}-\d{6}$", "Immutable shortage identifier.", primary_key=True),
            FieldSpec("balance_id", "str", "VARCHAR", True, "Valid projected_balances.balance_id", "id", False, "FK -> projected_balances.balance_id", "Originating negative balance row."),
            FieldSpec("sku_id", "str", "VARCHAR", True, "Valid skus.sku_id", "id", False, "FK -> skus.sku_id", "Short SKU."),
            FieldSpec("location_id", "str", "VARCHAR", True, "Valid locations.location_id", "id", False, "FK -> locations.location_id", "Affected location."),
            FieldSpec("week_id", "str", "VARCHAR", True, "2026W01..2026W52", "iso_week", False, "Regex ^\d{4}W\d{2}$", "Week shortage occurs."),
            FieldSpec("week_start_date", "date", "DATE", True, "Monday of week_id", "date", False, "Matches ISO week Monday", "Week start date."),
            FieldSpec("shortage_qty", "int", "INTEGER", True, "> 0", "units", False, "Derived == abs(closing_stock)", "Magnitude of deficit in base units."),
            FieldSpec("revenue_at_risk", "float", "DOUBLE", True, "> 0", "INR", False, "Derived == round(shortage_qty * sku.unit_price, 4)", "Potential lost revenue."),
            FieldSpec("lead_time_days_used", "int", "INTEGER", True, ">= 0", "days", False, "Derived min supplier lead time (0 only if MAKE-only)", "Replenishment lead time applied."),
            FieldSpec("required_order_by_date", "date", "DATE", True, "week_start_date - lead_time_days_used", "date", False, "Derived == week_start_date - lead_time_days_used", "Latest date replenishment had to be triggered."),
            FieldSpec("root_cause", "str", "VARCHAR", True, _enum_values(ShortageRootCause), "none", False, "Allowed ShortageRootCause enum", "Explainable primary cause.", enum_cls=ShortageRootCause),
            FieldSpec("severity", "str", "VARCHAR", True, _enum_values(ShortageSeverity), "none", False, "Allowed ShortageSeverity enum", "Derived urgency tier.", enum_cls=ShortageSeverity),
            FieldSpec("priority_score", "float", "DOUBLE", True, "0.0 to 100.0", "score", False, "0 <= priority_score <= 100", "Derived composite prioritization score."),
            FieldSpec("priority_rank", "int", "INTEGER", True, ">= 1", "rank", True, "Unique dense rank 1..N", "Global shortage action priority."),
            _lifecycle_field(ShortageStatus),
            *_effective_date_fields(),
        ),
        foreign_keys=(
            ForeignKeySpec("balance_id", "projected_balances", "balance_id"),
            ForeignKeySpec("sku_id", "skus", "sku_id"),
            ForeignKeySpec("location_id", "locations", "location_id"),
        ),
        relationships=(
            RelationshipSpec("ProjectedBalance", "1:1", "balance_id", False, "Source negative balance ledger row."),
            RelationshipSpec("ShortageEvidence", "1:N", "shortage_id", False, "Traceable evidence rows."),
            RelationshipSpec("MitigationOption", "1:N", "shortage_id", True, "Ranked candidate mitigations."),
        ),
    ),
    EntitySpec(
        name="ShortageEvidence",
        table_name="shortage_evidence",
        layer="derived",
        primary_key="evidence_id",
        lifecycle_column="lifecycle_state",
        description="Traceability bridge linking each Shortage to the exact source rows explaining its root cause.",
        fields=(
            FieldSpec("evidence_id", "str", "VARCHAR", True, "EVID-2026-000001", "id", True, "Regex ^EVID-\d{4}-\d{6}$", "Immutable evidence row ID.", primary_key=True),
            FieldSpec("shortage_id", "str", "VARCHAR", True, "Valid shortages.shortage_id", "id", False, "FK -> shortages.shortage_id", "Explained shortage."),
            FieldSpec("source_table", "str", "VARCHAR", True, "forecast_demand, inventory, purchase_orders, supplier_capacity, lead_times, production_plans", "table", False, "Valid source table name", "Originating source table."),
            FieldSpec("source_record_id", "str", "VARCHAR", True, "Valid PK in source_table", "id", False, "Must exist in source_table", "Referenced source row primary key."),
            FieldSpec("contribution_type", "str", "VARCHAR", True, _enum_values(EvidenceContribution), "none", False, "Allowed EvidenceContribution enum", "Role in causing the shortage.", enum_cls=EvidenceContribution),
            FieldSpec("metric_value", "float", "DOUBLE", True, "Numeric", "mixed", False, "Finite number", "Key quantitative metric from source row."),
            FieldSpec("explanation", "str", "VARCHAR", True, "Non-empty text", "text", False, "len >= 5", "Human-readable audit note."),
            *_effective_date_fields(),
            _lifecycle_field(EntityStatus),
        ),
        foreign_keys=(ForeignKeySpec("shortage_id", "shortages", "shortage_id"),),
        relationships=(RelationshipSpec("Shortage", "N:1", "shortage_id", False, "Parent shortage."),),
    ),
    EntitySpec(
        name="MitigationOption",
        table_name="mitigation_options",
        layer="derived",
        primary_key="mitigation_id",
        lifecycle_column="lifecycle_state",
        description="Policy-checked, capacity-checked shortage mitigation alternatives with cost/service trade-offs.",
        fields=(
            FieldSpec("mitigation_id", "str", "VARCHAR", True, "MIT-SHORT-2026-000001-01", "id", True, "Regex ^MIT-SHORT-\d{4}-\d{6}-\d{2}$", "Immutable mitigation option ID.", primary_key=True),
            FieldSpec("shortage_id", "str", "VARCHAR", True, "Valid shortages.shortage_id", "id", False, "FK -> shortages.shortage_id", "Target shortage."),
            FieldSpec("mitigation_type", "str", "VARCHAR", True, _enum_values(MitigationType), "none", False, "Allowed MitigationType enum", "Action strategy.", enum_cls=MitigationType),
            FieldSpec("target_supplier_id", "str", "VARCHAR", False, "Valid suppliers.supplier_id or NULL", "id", False, "Optional FK -> suppliers.supplier_id", "Supplier used if purchase/expedite."),
            FieldSpec("target_sku_id", "str", "VARCHAR", False, "Valid skus.sku_id or NULL", "id", False, "Optional FK -> skus.sku_id", "Substitute SKU if substitution."),
            FieldSpec("source_location_id", "str", "VARCHAR", False, "Valid locations.location_id or NULL", "id", False, "Optional FK -> locations.location_id", "Donor location if transfer."),
            FieldSpec("mitigation_qty", "int", "INTEGER", True, "> 0", "units", False, "mitigation_qty > 0", "Units covered by this mitigation."),
            FieldSpec("cost", "float", "DOUBLE", True, ">= 0", "INR", False, "cost >= 0", "Incremental execution cost."),
            FieldSpec("service_level_impact", "float", "DOUBLE", True, "0.0 to 1.0", "ratio", False, "0 <= service_level_impact <= 1", "Fraction of shortage demand recovered."),
            FieldSpec("lead_time_days", "int", "INTEGER", True, ">= 0", "days", False, "lead_time_days >= 0", "Days to execute mitigation."),
            FieldSpec("capacity_check_passed", "bool", "BOOLEAN", True, "true, false", "flag", False, "True in clean baseline", "Confirms supplier/plant/stock capacity availability."),
            FieldSpec("policy_check_passed", "bool", "BOOLEAN", True, "true, false", "flag", False, "True in clean baseline", "Confirms policy & approval compliance."),
            FieldSpec("score", "float", "DOUBLE", True, "0.0 to 100.0", "score", False, "Derived weighted cost/service/lead-time score", "Composite trade-off score (higher is better)."),
            FieldSpec("rank", "int", "INTEGER", True, ">= 1", "rank", False, "Unique rank 1..k per shortage_id", "Recommended option ranking."),
            _lifecycle_field(MitigationStatus),
            *_effective_date_fields(),
        ),
        foreign_keys=(
            ForeignKeySpec("shortage_id", "shortages", "shortage_id"),
            ForeignKeySpec("target_supplier_id", "suppliers", "supplier_id", optional=True),
            ForeignKeySpec("target_sku_id", "skus", "sku_id", optional=True),
            ForeignKeySpec("source_location_id", "locations", "location_id", optional=True),
        ),
        relationships=(
            RelationshipSpec("Shortage", "N:1", "shortage_id", False, "Shortage addressed."),
            RelationshipSpec("Supplier", "N:1", "target_supplier_id", True, "Alternate/expedite vendor."),
            RelationshipSpec("SKU", "N:1", "target_sku_id", True, "Substitute SKU."),
            RelationshipSpec("Location", "N:1", "source_location_id", True, "Transfer donor location."),
        ),
    ),
)

ENTITY_REGISTRY: dict[str, EntitySpec] = {spec.table_name: spec for spec in _ENTITIES}
ENTITY_ORDER: tuple[str, ...] = tuple(spec.table_name for spec in _ENTITIES)


def get_entity_spec(table_name: str) -> EntitySpec:
    return ENTITY_REGISTRY[table_name]


def generate_full_sql_ddl() -> str:
    blocks = [
        "-- Auto-generated from oryva_planning.schema.registry (single source of truth)",
        "",
    ]
    for table_name in ENTITY_ORDER:
        blocks.append(ENTITY_REGISTRY[table_name].to_sql_ddl())
        blocks.append("")
    return "\n".join(blocks)
