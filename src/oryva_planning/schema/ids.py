"""Deterministic, zero-padded, immutable ID builders and regex validators."""

from __future__ import annotations

import re

SKU_PATTERN = re.compile(r"^SKU-\d{6}$")
LOCATION_PATTERN = re.compile(r"^LOC-\d{4}$")
SUPPLIER_PATTERN = re.compile(r"^SUP-\d{4}$")
WEEK_PATTERN = re.compile(r"^\d{4}W(?:0[1-9]|[1-4]\d|5[0-3])$")
DEMAND_PATTERN = re.compile(
    r"^DEM-SKU-\d{6}-LOC-\d{4}-\d{4}W(?:0[1-9]|[1-4]\d|5[0-3])$"
)
INVENTORY_PATTERN = re.compile(r"^INV-SKU-\d{6}-LOC-\d{4}$")
CAPACITY_PATTERN = re.compile(r"^CAP-SUP-\d{4}-\d{4}W(?:0[1-9]|[1-4]\d|5[0-3])$")
LEAD_TIME_PATTERN = re.compile(r"^LT-SKU-\d{6}-SUP-\d{4}-LOC-\d{4}$")
PO_PATTERN = re.compile(r"^PO-\d{4}-\d{6}$")
PO_EVENT_PATTERN = re.compile(r"^POE-\d{4}-\d{7}$")
PRODUCTION_PATTERN = re.compile(r"^PROD-\d{4}-\d{6}$")
BALANCE_PATTERN = re.compile(
    r"^BAL-SKU-\d{6}-LOC-\d{4}-\d{4}W(?:0[1-9]|[1-4]\d|5[0-3])$"
)
SHORTAGE_PATTERN = re.compile(r"^SHORT-\d{4}-\d{6}$")
MITIGATION_PATTERN = re.compile(r"^MIT-SHORT-\d{4}-\d{6}-\d{2}$")
EVIDENCE_PATTERN = re.compile(r"^EVID-\d{4}-\d{6}$")
SKU_SUPPLIER_PATTERN = re.compile(r"^SS-SKU-\d{6}-SUP-\d{4}$")
SKU_SUBSTITUTE_PATTERN = re.compile(r"^SUB-SKU-\d{6}-SKU-\d{6}$")
BOM_PATTERN = re.compile(r"^BOM-SKU-\d{6}-SKU-\d{6}$")
GROUND_TRUTH_PATTERN = re.compile(r"^GT-\d{4}-\d{4}$")

ID_PATTERNS: dict[str, re.Pattern[str]] = {
    "sku_id": SKU_PATTERN,
    "location_id": LOCATION_PATTERN,
    "supplier_id": SUPPLIER_PATTERN,
    "week_id": WEEK_PATTERN,
    "demand_id": DEMAND_PATTERN,
    "inventory_id": INVENTORY_PATTERN,
    "capacity_id": CAPACITY_PATTERN,
    "lead_time_id": LEAD_TIME_PATTERN,
    "po_id": PO_PATTERN,
    "event_id": PO_EVENT_PATTERN,
    "production_id": PRODUCTION_PATTERN,
    "balance_id": BALANCE_PATTERN,
    "shortage_id": SHORTAGE_PATTERN,
    "mitigation_id": MITIGATION_PATTERN,
    "evidence_id": EVIDENCE_PATTERN,
    "sku_supplier_id": SKU_SUPPLIER_PATTERN,
    "sku_substitute_id": SKU_SUBSTITUTE_PATTERN,
    "bom_id": BOM_PATTERN,
    "ground_truth_id": GROUND_TRUTH_PATTERN,
}


def _require_positive(value: int, label: str) -> None:
    if value < 1:
        raise ValueError(f"{label} must be >= 1, got {value}")


def make_sku_id(seq: int) -> str:
    _require_positive(seq, "sku sequence")
    return f"SKU-{seq:06d}"


def make_location_id(seq: int) -> str:
    _require_positive(seq, "location sequence")
    return f"LOC-{seq:04d}"


def make_supplier_id(seq: int) -> str:
    _require_positive(seq, "supplier sequence")
    return f"SUP-{seq:04d}"


def make_week_id(year: int, week: int) -> str:
    if not (1 <= week <= 53):
        raise ValueError(f"ISO week must be between 1 and 53, got {week}")
    return f"{year:04d}W{week:02d}"


def make_demand_id(sku_id: str, location_id: str, week_id: str) -> str:
    return f"DEM-{sku_id}-{location_id}-{week_id}"


def make_inventory_id(sku_id: str, location_id: str) -> str:
    return f"INV-{sku_id}-{location_id}"


def make_capacity_id(supplier_id: str, week_id: str) -> str:
    return f"CAP-{supplier_id}-{week_id}"


def make_lead_time_id(sku_id: str, supplier_id: str, location_id: str) -> str:
    return f"LT-{sku_id}-{supplier_id}-{location_id}"


def make_po_id(year: int, seq: int) -> str:
    _require_positive(seq, "purchase order sequence")
    return f"PO-{year:04d}-{seq:06d}"


def make_po_event_id(year: int, seq: int) -> str:
    _require_positive(seq, "purchase order event sequence")
    return f"POE-{year:04d}-{seq:07d}"


def make_production_id(year: int, seq: int) -> str:
    _require_positive(seq, "production plan sequence")
    return f"PROD-{year:04d}-{seq:06d}"


def make_balance_id(sku_id: str, location_id: str, week_id: str) -> str:
    return f"BAL-{sku_id}-{location_id}-{week_id}"


def make_shortage_id(year: int, seq: int) -> str:
    _require_positive(seq, "shortage sequence")
    return f"SHORT-{year:04d}-{seq:06d}"


def make_mitigation_id(shortage_id: str, option_num: int) -> str:
    if not (1 <= option_num <= 99):
        raise ValueError(f"mitigation option_num must be 1..99, got {option_num}")
    return f"MIT-{shortage_id}-{option_num:02d}"


def make_evidence_id(year: int, seq: int) -> str:
    _require_positive(seq, "evidence sequence")
    return f"EVID-{year:04d}-{seq:06d}"


def make_sku_supplier_id(sku_id: str, supplier_id: str) -> str:
    return f"SS-{sku_id}-{supplier_id}"


def make_sku_substitute_id(sku_id: str, substitute_sku_id: str) -> str:
    return f"SUB-{sku_id}-{substitute_sku_id}"


def make_bom_id(parent_sku_id: str, component_sku_id: str) -> str:
    return f"BOM-{parent_sku_id}-{component_sku_id}"


def make_ground_truth_id(year: int, seq: int) -> str:
    _require_positive(seq, "ground truth sequence")
    return f"GT-{year:04d}-{seq:04d}"


def validate_id(kind: str, value: str) -> bool:
    pattern = ID_PATTERNS.get(kind)
    if pattern is None:
        raise KeyError(f"Unknown ID kind: {kind}")
    return bool(pattern.match(value))
