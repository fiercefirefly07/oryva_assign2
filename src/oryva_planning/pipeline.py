"""End-to-end deterministic generation, planning, anomaly injection, validation, and export pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from oryva_planning.anomalies import evaluate_detectors, inject_all_anomalies, run_all_detectors
from oryva_planning.config import PlanningConfig, get_planning_weeks
from oryva_planning.export.manifest import (
    write_data_dictionary,
    write_er_diagram,
    write_source_manifest,
    write_validation_summary,
)
from oryva_planning.export.writers import export_all
from oryva_planning.generators import (
    generate_bom_items,
    generate_forecast_demand,
    generate_inventory,
    generate_lead_times,
    generate_locations,
    generate_production_plans,
    generate_purchase_orders_and_capacity,
    generate_sku_substitutes,
    generate_sku_suppliers,
    generate_skus,
    generate_suppliers,
)
from oryva_planning.planning import (
    compute_projected_balances,
    detect_shortages_and_evidence,
    generate_mitigation_options,
)
from oryva_planning.validation import ValidationReport, validate_tables


@dataclass
class PipelineResult:
    config: PlanningConfig
    baseline_tables: dict[str, pd.DataFrame]
    final_tables: dict[str, pd.DataFrame]
    ground_truth_df: pd.DataFrame
    baseline_report: ValidationReport
    final_report: ValidationReport
    detector_metrics: dict[str, dict[str, float | int]]
    export_meta: dict[str, Any] | None = None


def run_pipeline(
    config: PlanningConfig,
    export_outputs: bool = True,
    write_docs: bool = False,
    output_dir: Path | None = None,
    docs_dir: Path | None = None,
    validate_baseline: bool = True,
) -> PipelineResult:
    ss = np.random.SeedSequence(config.seed)
    streams = [np.random.default_rng(child) for child in ss.spawn(13)]
    (
        rng_sku,
        rng_loc,
        rng_sup,
        rng_ss,
        rng_sub,
        rng_bom,
        rng_dem,
        rng_inv,
        rng_lt,
        rng_cap,
        rng_po,
        rng_prod,
        rng_anom,
    ) = streams

    weeks = get_planning_weeks(config.planning_year, config.start_week, config.num_weeks)

    skus = generate_skus(config, rng_sku)
    locations = generate_locations(config, rng_loc)
    suppliers = generate_suppliers(config, rng_sup)
    sku_suppliers = generate_sku_suppliers(config, rng_ss, skus, suppliers)
    sku_substitutes = generate_sku_substitutes(config, rng_sub, skus)
    bom_items = generate_bom_items(config, rng_bom, skus)

    forecast_demand = generate_forecast_demand(config, rng_dem, skus, locations, weeks)
    inventory = generate_inventory(config, rng_inv, skus, locations, forecast_demand, weeks)
    lead_times = generate_lead_times(config, rng_lt, skus, locations, suppliers, sku_suppliers)
    purchase_orders, purchase_order_events, supplier_capacity = generate_purchase_orders_and_capacity(
        config, rng_cap, rng_po, skus, locations, suppliers, sku_suppliers, lead_times, forecast_demand, weeks
    )
    production_plans = generate_production_plans(
        config, rng_prod, skus, locations, bom_items, inventory, forecast_demand, weeks
    )

    projected_balances = compute_projected_balances(
        config, skus, locations, forecast_demand, inventory, purchase_orders, production_plans, weeks
    )
    shortages, shortage_evidence = detect_shortages_and_evidence(
        config, skus, suppliers, sku_suppliers, forecast_demand, inventory, supplier_capacity,
        lead_times, purchase_orders, production_plans, projected_balances, weeks
    )
    mitigation_options, shortages = generate_mitigation_options(
        config, skus, locations, suppliers, sku_suppliers, sku_substitutes, supplier_capacity,
        lead_times, purchase_orders, production_plans, projected_balances, shortages
    )

    baseline_tables: dict[str, pd.DataFrame] = {
        "skus": skus,
        "locations": locations,
        "suppliers": suppliers,
        "sku_suppliers": sku_suppliers,
        "sku_substitutes": sku_substitutes,
        "bom_items": bom_items,
        "forecast_demand": forecast_demand,
        "inventory": inventory,
        "supplier_capacity": supplier_capacity,
        "lead_times": lead_times,
        "purchase_orders": purchase_orders,
        "purchase_order_events": purchase_order_events,
        "production_plans": production_plans,
        "projected_balances": projected_balances,
        "shortages": shortages,
        "shortage_evidence": shortage_evidence,
        "mitigation_options": mitigation_options,
    }

    baseline_report = (
        validate_tables(baseline_tables, expect_clean_baseline=True)
        if validate_baseline
        else ValidationReport(sql_backend="skipped")
    )

    final_tables, ground_truth_df = inject_all_anomalies(config, rng_anom, baseline_tables)
    detected = run_all_detectors(final_tables)
    detector_metrics = evaluate_detectors(detected, ground_truth_df)
    final_report = validate_tables(final_tables, ground_truth_df=ground_truth_df, expect_clean_baseline=False)

    export_meta: dict[str, Any] | None = None
    if export_outputs:
        target_dir = Path(output_dir) if output_dir is not None else Path(config.export.output_dir)
        export_meta = export_all(
            config=config,
            tables=final_tables,
            ground_truth_df=ground_truth_df,
            detector_metrics=detector_metrics,
            output_dir=target_dir,
        )
        target_docs = Path(docs_dir) if docs_dir is not None else None
        write_source_manifest(config, export_meta, target_dir, docs_dir=target_docs)
        if write_docs and target_docs is not None:
            write_data_dictionary(target_docs)
            write_er_diagram(target_docs)
            write_validation_summary(final_report, target_docs, target_dir)

    return PipelineResult(
        config=config,
        baseline_tables=baseline_tables,
        final_tables=final_tables,
        ground_truth_df=ground_truth_df,
        baseline_report=baseline_report,
        final_report=final_report,
        detector_metrics=detector_metrics,
        export_meta=export_meta,
    )
