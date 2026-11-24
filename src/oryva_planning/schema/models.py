"""Pydantic v2 row-level validation models derived from the schema registry."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

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


class EffectiveDatedModel(BaseModel):
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def _validate_effective_dates(self) -> EffectiveDatedModel:
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must be >= effective_from")
        return self


class SKUModel(EffectiveDatedModel):
    sku_id: str = Field(..., pattern=r"^SKU-\d{6}$")
    sku_name: str = Field(..., min_length=3)
    category: SKUCategory
    sourcing_type: SourcingType
    base_uom: UOM
    unit_cost: float = Field(..., gt=0)
    unit_price: float = Field(..., gt=0)
    weight_kg: float = Field(..., gt=0)
    popularity_rank: int = Field(..., ge=1)
    popularity_tier: PopularityTier
    is_critical: bool
    lifecycle_state: EntityStatus

    @model_validator(mode="after")
    def _check_price(self) -> SKUModel:
        if self.unit_price < self.unit_cost:
            raise ValueError("unit_price must be >= unit_cost")
        return self


class LocationModel(EffectiveDatedModel):
    location_id: str = Field(..., pattern=r"^LOC-\d{4}$")
    location_name: str = Field(..., min_length=3)
    location_type: LocationType
    region: Region
    storage_capacity_units: int = Field(..., gt=0)
    daily_production_capacity: int = Field(..., ge=0)
    holding_cost_per_unit_week: float = Field(..., gt=0)
    lifecycle_state: EntityStatus


class SupplierModel(EffectiveDatedModel):
    supplier_id: str = Field(..., pattern=r"^SUP-\d{4}$")
    supplier_name: str = Field(..., min_length=3)
    region: Region
    supplier_tier: SupplierTier
    reliability_tier: ReliabilityTier
    on_time_rate: float = Field(..., ge=0.0, le=1.0)
    is_constrained: bool
    expedite_surcharge_pct: float = Field(..., ge=0.0, le=1.0)
    lifecycle_state: EntityStatus


class PurchaseOrderModel(EffectiveDatedModel):
    po_id: str = Field(..., pattern=r"^PO-\d{4}-\d{6}$")
    sku_id: str = Field(..., pattern=r"^SKU-\d{6}$")
    supplier_id: str = Field(..., pattern=r"^SUP-\d{4}$")
    location_id: str = Field(..., pattern=r"^LOC-\d{4}$")
    order_date: date
    promised_delivery_date: date
    actual_delivery_date: date | None = None
    arrival_week_id: str = Field(..., pattern=r"^\d{4}W(?:0[1-9]|[1-4]\d|5[0-3])$")
    order_qty: int = Field(..., gt=0)
    uom: UOM
    unit_cost: float = Field(..., gt=0)
    total_cost: float = Field(..., gt=0)
    transport_delay_days: int = Field(..., ge=0)
    current_status: POStatus

    @model_validator(mode="after")
    def _check_dates_and_cost(self) -> PurchaseOrderModel:
        if self.promised_delivery_date < self.order_date:
            raise ValueError("promised_delivery_date must be >= order_date")
        if self.actual_delivery_date is not None and self.actual_delivery_date < self.order_date:
            raise ValueError("actual_delivery_date must be >= order_date")
        expected_total = round(self.order_qty * self.unit_cost, 4)
        if abs(self.total_cost - expected_total) > 1e-2:
            raise ValueError(f"total_cost {self.total_cost} != {expected_total}")
        return self


class PurchaseOrderEventModel(EffectiveDatedModel):
    event_id: str = Field(..., pattern=r"^POE-\d{4}-\d{7}$")
    po_id: str = Field(..., pattern=r"^PO-\d{4}-\d{6}$")
    sequence_num: int = Field(..., ge=1)
    from_status: POStatus | None = None
    to_status: POStatus
    event_ts: datetime
    actor: str = Field(..., min_length=2)
    reason: str = Field(..., min_length=3)
    lifecycle_state: EntityStatus


class ProductionPlanModel(EffectiveDatedModel):
    production_id: str = Field(..., pattern=r"^PROD-\d{4}-\d{6}$")
    sku_id: str = Field(..., pattern=r"^SKU-\d{6}$")
    location_id: str = Field(..., pattern=r"^LOC-\d{4}$")
    week_id: str = Field(..., pattern=r"^\d{4}W(?:0[1-9]|[1-4]\d|5[0-3])$")
    week_start_date: date
    planned_qty: int = Field(..., gt=0)
    capacity_limit_qty: int = Field(..., ge=0)
    bom_feasible_qty: int = Field(..., ge=0)
    achievable_qty: int = Field(..., ge=0)
    uom: UOM
    unit_production_cost: float = Field(..., gt=0)
    lifecycle_state: ProductionStatus


class ShortageModel(EffectiveDatedModel):
    shortage_id: str = Field(..., pattern=r"^SHORT-\d{4}-\d{6}$")
    balance_id: str = Field(..., pattern=r"^BAL-SKU-\d{6}-LOC-\d{4}-\d{4}W\d{2}$")
    sku_id: str = Field(..., pattern=r"^SKU-\d{6}$")
    location_id: str = Field(..., pattern=r"^LOC-\d{4}$")
    week_id: str = Field(..., pattern=r"^\d{4}W(?:0[1-9]|[1-4]\d|5[0-3])$")
    week_start_date: date
    shortage_qty: int = Field(..., gt=0)
    revenue_at_risk: float = Field(..., gt=0)
    lead_time_days_used: int = Field(..., ge=0)
    required_order_by_date: date
    root_cause: ShortageRootCause
    severity: ShortageSeverity
    priority_score: float = Field(..., ge=0.0, le=100.0)
    priority_rank: int = Field(..., ge=1)
    lifecycle_state: ShortageStatus


class ShortageEvidenceModel(EffectiveDatedModel):
    evidence_id: str = Field(..., pattern=r"^EVID-\d{4}-\d{6}$")
    shortage_id: str = Field(..., pattern=r"^SHORT-\d{4}-\d{6}$")
    source_table: str
    source_record_id: str
    contribution_type: EvidenceContribution
    metric_value: float
    explanation: str = Field(..., min_length=5)
    lifecycle_state: EntityStatus


class MitigationOptionModel(EffectiveDatedModel):
    mitigation_id: str = Field(..., pattern=r"^MIT-SHORT-\d{4}-\d{6}-\d{2}$")
    shortage_id: str = Field(..., pattern=r"^SHORT-\d{4}-\d{6}$")
    mitigation_type: MitigationType
    target_supplier_id: str | None = None
    target_sku_id: str | None = None
    source_location_id: str | None = None
    mitigation_qty: int = Field(..., gt=0)
    cost: float = Field(..., ge=0.0)
    service_level_impact: float = Field(..., ge=0.0, le=1.0)
    lead_time_days: int = Field(..., ge=0)
    capacity_check_passed: bool
    policy_check_passed: bool
    score: float = Field(..., ge=0.0, le=100.0)
    rank: int = Field(..., ge=1)
    lifecycle_state: MitigationStatus


ROW_MODELS: dict[str, type[BaseModel]] = {
    "skus": SKUModel,
    "locations": LocationModel,
    "suppliers": SupplierModel,
    "purchase_orders": PurchaseOrderModel,
    "purchase_order_events": PurchaseOrderEventModel,
    "production_plans": ProductionPlanModel,
    "shortages": ShortageModel,
    "shortage_evidence": ShortageEvidenceModel,
    "mitigation_options": MitigationOptionModel,
}
