"""Domain enumerations and explicit lifecycle state transition graphs."""

from __future__ import annotations

from enum import Enum


class UOM(str, Enum):
    EA = "EA"
    KG = "KG"
    L = "L"
    CASE = "CASE"
    PALLET = "PALLET"


class SKUCategory(str, Enum):
    ELECTRONICS = "ELECTRONICS"
    INDUSTRIAL = "INDUSTRIAL"
    PACKAGING = "PACKAGING"
    CONSUMABLES = "CONSUMABLES"
    SPARE_PARTS = "SPARE_PARTS"


class SourcingType(str, Enum):
    BUY = "BUY"
    MAKE = "MAKE"
    BOTH = "BOTH"


class PopularityTier(str, Enum):
    A = "A"
    B = "B"
    C = "C"


class LocationType(str, Enum):
    WAREHOUSE = "WAREHOUSE"
    DISTRIBUTION_CENTER = "DISTRIBUTION_CENTER"
    PLANT = "PLANT"
    REGIONAL_HUB = "REGIONAL_HUB"


class Region(str, Enum):
    NORTH = "NORTH"
    SOUTH = "SOUTH"
    EAST = "EAST"
    WEST = "WEST"
    CENTRAL = "CENTRAL"


class SupplierTier(str, Enum):
    STRATEGIC = "STRATEGIC"
    PREFERRED = "PREFERRED"
    APPROVED = "APPROVED"
    CONSTRAINED = "CONSTRAINED"


class ReliabilityTier(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class EntityStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    RETIRED = "RETIRED"


class POStatus(str, Enum):
    CREATED = "CREATED"
    CONFIRMED = "CONFIRMED"
    IN_TRANSIT = "IN_TRANSIT"
    DELAYED = "DELAYED"
    RECEIVED = "RECEIVED"
    CANCELLED = "CANCELLED"


class ProductionStatus(str, Enum):
    PLANNED = "PLANNED"
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CONSTRAINED = "CONSTRAINED"
    CANCELLED = "CANCELLED"


class ShortageSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ShortageStatus(str, Enum):
    OPEN = "OPEN"
    MITIGATION_PROPOSED = "MITIGATION_PROPOSED"
    MITIGATED = "MITIGATED"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"


class ShortageRootCause(str, Enum):
    DEMAND_SPIKE = "DEMAND_SPIKE"
    LATE_INBOUND = "LATE_INBOUND"
    SUPPLIER_CAPACITY_CAP = "SUPPLIER_CAPACITY_CAP"
    LEAD_TIME_GAP = "LEAD_TIME_GAP"
    PRODUCTION_CONSTRAINT = "PRODUCTION_CONSTRAINT"
    LOW_OPENING_INVENTORY = "LOW_OPENING_INVENTORY"
    COMPOUND_DEFICIT = "COMPOUND_DEFICIT"


class MitigationType(str, Enum):
    EXPEDITE_PO = "EXPEDITE_PO"
    ALTERNATE_SUPPLIER = "ALTERNATE_SUPPLIER"
    SUBSTITUTE_SKU = "SUBSTITUTE_SKU"
    INTER_LOCATION_TRANSFER = "INTER_LOCATION_TRANSFER"
    OVERTIME_PRODUCTION = "OVERTIME_PRODUCTION"
    DEMAND_REALLOCATION = "DEMAND_REALLOCATION"


class MitigationStatus(str, Enum):
    PROPOSED = "PROPOSED"
    POLICY_VALIDATED = "POLICY_VALIDATED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"


class EvidenceContribution(str, Enum):
    DEMAND_DRIVER = "DEMAND_DRIVER"
    INVENTORY_BASELINE = "INVENTORY_BASELINE"
    INBOUND_DELAY = "INBOUND_DELAY"
    CAPACITY_BOTTLENECK = "CAPACITY_BOTTLENECK"
    LEAD_TIME_CONSTRAINT = "LEAD_TIME_CONSTRAINT"
    PRODUCTION_SHORTFALL = "PRODUCTION_SHORTFALL"


class IssueType(str, Enum):
    DOUBLE_COUNTED_INBOUND = "double_counted_inbound"
    UNAPPROVED_SUBSTITUTE = "unapproved_substitute"
    SUPPLIER_CAPACITY_EXCEEDED = "supplier_capacity_exceeded"
    SHORTAGE_WITHOUT_LEAD_TIME = "shortage_without_lead_time"
    UOM_MISMATCH = "uom_mismatch"


PO_TRANSITIONS: dict[POStatus | None, frozenset[POStatus]] = {
    None: frozenset({POStatus.CREATED}),
    POStatus.CREATED: frozenset({POStatus.CONFIRMED, POStatus.CANCELLED}),
    POStatus.CONFIRMED: frozenset({POStatus.IN_TRANSIT, POStatus.DELAYED, POStatus.CANCELLED}),
    POStatus.IN_TRANSIT: frozenset({POStatus.DELAYED, POStatus.RECEIVED}),
    POStatus.DELAYED: frozenset({POStatus.IN_TRANSIT, POStatus.RECEIVED, POStatus.CANCELLED}),
    POStatus.RECEIVED: frozenset(),
    POStatus.CANCELLED: frozenset(),
}

MASTER_TRANSITIONS: dict[EntityStatus | None, frozenset[EntityStatus]] = {
    None: frozenset({EntityStatus.DRAFT, EntityStatus.ACTIVE}),
    EntityStatus.DRAFT: frozenset({EntityStatus.ACTIVE, EntityStatus.RETIRED}),
    EntityStatus.ACTIVE: frozenset({EntityStatus.SUSPENDED, EntityStatus.RETIRED}),
    EntityStatus.SUSPENDED: frozenset({EntityStatus.ACTIVE, EntityStatus.RETIRED}),
    EntityStatus.RETIRED: frozenset(),
}

PRODUCTION_TRANSITIONS: dict[ProductionStatus | None, frozenset[ProductionStatus]] = {
    None: frozenset({ProductionStatus.PLANNED}),
    ProductionStatus.PLANNED: frozenset(
        {ProductionStatus.SCHEDULED, ProductionStatus.CONSTRAINED, ProductionStatus.CANCELLED}
    ),
    ProductionStatus.CONSTRAINED: frozenset(
        {ProductionStatus.SCHEDULED, ProductionStatus.CANCELLED}
    ),
    ProductionStatus.SCHEDULED: frozenset(
        {ProductionStatus.IN_PROGRESS, ProductionStatus.CANCELLED}
    ),
    ProductionStatus.IN_PROGRESS: frozenset({ProductionStatus.COMPLETED}),
    ProductionStatus.COMPLETED: frozenset(),
    ProductionStatus.CANCELLED: frozenset(),
}
