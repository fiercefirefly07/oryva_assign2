"""Typed YAML configuration loader and deterministic planning calendar helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

from oryva_planning.schema.ids import make_week_id

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_DIR = PROJECT_ROOT / "config"


def _parse_scalar(raw: str) -> Any:
    val = raw.strip()
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        return val[1:-1].replace("\\n", "\n")
    lower = val.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if lower in ("null", "none", "~"):
        return None
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        return val


def _simple_yaml_load(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        container = stack[-1][1]
        if stripped.startswith("- "):
            if isinstance(container, list):
                container.append(_parse_scalar(stripped[2:]))
            continue
        key, _, rest = stripped.partition(":")
        key, rest = key.strip(), rest.strip()
        if rest:
            container[key] = _parse_scalar(rest)
        else:
            child: Any = {}
            for nxt in lines[idx + 1 :]:
                ns = nxt.strip()
                if not ns or ns.startswith("#"):
                    continue
                if ns.startswith("- "):
                    child = []
                break
            container[key] = child
            stack.append((indent, child))
    return root


class ScaleConfig(BaseModel):
    num_skus: int = Field(..., ge=5)
    num_locations: int = Field(..., ge=2)
    num_suppliers: int = Field(..., ge=3)
    num_purchase_orders: int = Field(..., ge=10)
    avg_suppliers_per_sku: int = Field(2, ge=1)
    substitute_sku_share: float = Field(0.20, ge=0.0, le=1.0)
    make_sku_share: float = Field(0.15, ge=0.0, le=1.0)
    max_bom_components: int = Field(3, ge=1, le=10)


class DemandConfig(BaseModel):
    pareto_alpha: float = Field(1.5, gt=1.0)
    base_weekly_mean: float = Field(40.0, gt=0.0)
    seasonality_amplitude: float = Field(0.25, ge=0.0, le=0.9)
    dispersion_k: float = Field(5.0, gt=0.0)
    spike_probability: float = Field(0.03, ge=0.0, le=0.5)
    spike_min_multiplier: float = Field(2.2, ge=1.0)
    spike_max_multiplier: float = Field(3.8, ge=1.0)

    @model_validator(mode="after")
    def _check_spike_bounds(self) -> DemandConfig:
        if self.spike_max_multiplier < self.spike_min_multiplier:
            raise ValueError("spike_max_multiplier must be >= spike_min_multiplier")
        return self


class SupplierConfig(BaseModel):
    constrained_share: float = Field(0.20, ge=0.0, le=1.0)
    unreliable_share: float = Field(0.18, ge=0.0, le=1.0)
    lead_time_gamma_shape: float = Field(3.5, gt=0.0)
    lead_time_gamma_scale: float = Field(3.0, gt=0.0)
    transport_delay_probability: float = Field(0.12, ge=0.0, le=1.0)
    transport_delay_lognorm_mean: float = Field(1.5, ge=0.0)
    transport_delay_lognorm_sigma: float = Field(0.65, gt=0.0)


class InventoryConfig(BaseModel):
    safety_stock_weeks: float = Field(1.5, ge=0.0)
    initial_coverage_min_weeks: float = Field(1.5, ge=0.0)
    initial_coverage_max_weeks: float = Field(4.5, gt=0.0)
    reserved_share_max: float = Field(0.12, ge=0.0, le=0.9)

    @model_validator(mode="after")
    def _check_coverage_bounds(self) -> InventoryConfig:
        if self.initial_coverage_max_weeks < self.initial_coverage_min_weeks:
            raise ValueError("initial_coverage_max_weeks must be >= initial_coverage_min_weeks")
        return self


class ProductionConfig(BaseModel):
    capacity_buffer_ratio: float = Field(1.15, gt=0.0)
    constrained_week_share: float = Field(0.15, ge=0.0, le=1.0)
    overtime_cost_multiplier: float = Field(1.35, ge=1.0)


class MitigationConfig(BaseModel):
    cost_weight: float = Field(0.35, ge=0.0, le=1.0)
    service_weight: float = Field(0.45, ge=0.0, le=1.0)
    lead_time_weight: float = Field(0.20, ge=0.0, le=1.0)
    max_options_per_shortage: int = Field(4, ge=1, le=10)

    @model_validator(mode="after")
    def _check_weight_sum(self) -> MitigationConfig:
        total = round(self.cost_weight + self.service_weight + self.lead_time_weight, 6)
        if abs(total - 1.0) > 1e-5:
            raise ValueError(f"Mitigation weights must sum to 1.0, got {total}")
        return self


class AnomalyConfig(BaseModel):
    double_counted_inbound: int = Field(3, ge=1)
    unapproved_substitute: int = Field(3, ge=1)
    supplier_capacity_exceeded: int = Field(3, ge=1)
    shortage_without_lead_time: int = Field(3, ge=1)
    uom_mismatch: int = Field(3, ge=1)


class ExportConfig(BaseModel):
    output_dir: str = "data"
    float_format: str = "%.4f"
    line_terminator: str = "\n"
    formats: list[str] = Field(default_factory=lambda: ["csv", "json", "sql", "sqlite"])


class PlanningConfig(BaseModel):
    name: str
    seed: int = Field(20261022, ge=0)
    planning_year: int = Field(2026, ge=2020, le=2035)
    start_week: int = Field(1, ge=1, le=53)
    num_weeks: int = Field(52, ge=1, le=53)
    reference_date: date
    currency: str = "INR"
    scale: ScaleConfig
    demand: DemandConfig
    supplier: SupplierConfig
    inventory: InventoryConfig
    production: ProductionConfig
    mitigation: MitigationConfig
    anomalies: AnomalyConfig
    export: ExportConfig

    @property
    def inputs_dir(self) -> Path:
        return Path(self.export.output_dir) / "inputs"

    @property
    def ground_truth_dir(self) -> Path:
        return Path(self.export.output_dir) / "ground_truth"


@dataclass(frozen=True)
class PlanningWeek:
    week_index: int
    week_number: int
    week_id: str
    week_start_date: date
    week_end_date: date


def get_planning_weeks(
    planning_year: int,
    start_week: int = 1,
    num_weeks: int = 52,
) -> list[PlanningWeek]:
    first_monday = date.fromisocalendar(planning_year, start_week, 1)
    weeks: list[PlanningWeek] = []
    for idx in range(num_weeks):
        start_dt = first_monday + timedelta(days=7 * idx)
        end_dt = start_dt + timedelta(days=6)
        iso_year, iso_week, _ = start_dt.isocalendar()
        weeks.append(
            PlanningWeek(
                week_index=idx,
                week_number=idx + 1,
                week_id=make_week_id(iso_year, iso_week),
                week_start_date=start_dt,
                week_end_date=end_dt,
            )
        )
    return weeks


def resolve_config_path(scale_or_path: str | Path) -> Path:
    candidate = Path(scale_or_path)
    if candidate.exists() and candidate.is_file():
        return candidate
    named = DEFAULT_CONFIG_DIR / f"{scale_or_path}.yaml"
    if named.exists() and named.is_file():
        return named
    raise FileNotFoundError(f"Configuration not found for '{scale_or_path}' (checked {named})")


def load_config(
    scale_or_path: str | Path = "starter",
    seed_override: int | None = None,
    output_dir_override: str | None = None,
) -> PlanningConfig:
    path = resolve_config_path(scale_or_path)
    text = path.read_text(encoding="utf-8")
    raw = yaml.safe_load(text) if yaml is not None else _simple_yaml_load(text)
    if seed_override is not None:
        raw["seed"] = seed_override
    if output_dir_override is not None:
        raw.setdefault("export", {})["output_dir"] = output_dir_override
    return PlanningConfig.model_validate(raw)
