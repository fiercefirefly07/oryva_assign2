-- Auto-generated from oryva_planning.schema.registry (single source of truth)

CREATE TABLE skus (
    sku_id VARCHAR NOT NULL,
    sku_name VARCHAR NOT NULL,
    category VARCHAR NOT NULL,
    sourcing_type VARCHAR NOT NULL,
    base_uom VARCHAR NOT NULL,
    unit_cost DOUBLE NOT NULL,
    unit_price DOUBLE NOT NULL,
    weight_kg DOUBLE NOT NULL,
    popularity_rank INTEGER NOT NULL UNIQUE,
    popularity_tier VARCHAR NOT NULL,
    is_critical BOOLEAN NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE,
    lifecycle_state VARCHAR NOT NULL,
    PRIMARY KEY (sku_id)
);

CREATE TABLE locations (
    location_id VARCHAR NOT NULL,
    location_name VARCHAR NOT NULL,
    location_type VARCHAR NOT NULL,
    region VARCHAR NOT NULL,
    storage_capacity_units INTEGER NOT NULL,
    daily_production_capacity INTEGER NOT NULL,
    holding_cost_per_unit_week DOUBLE NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE,
    lifecycle_state VARCHAR NOT NULL,
    PRIMARY KEY (location_id)
);

CREATE TABLE suppliers (
    supplier_id VARCHAR NOT NULL,
    supplier_name VARCHAR NOT NULL,
    region VARCHAR NOT NULL,
    supplier_tier VARCHAR NOT NULL,
    reliability_tier VARCHAR NOT NULL,
    on_time_rate DOUBLE NOT NULL,
    is_constrained BOOLEAN NOT NULL,
    expedite_surcharge_pct DOUBLE NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE,
    lifecycle_state VARCHAR NOT NULL,
    PRIMARY KEY (supplier_id)
);

CREATE TABLE sku_suppliers (
    sku_supplier_id VARCHAR NOT NULL,
    sku_id VARCHAR NOT NULL,
    supplier_id VARCHAR NOT NULL,
    unit_purchase_cost DOUBLE NOT NULL,
    min_order_qty INTEGER NOT NULL,
    order_multiple INTEGER NOT NULL,
    is_primary BOOLEAN NOT NULL,
    contract_uom VARCHAR NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE,
    lifecycle_state VARCHAR NOT NULL,
    PRIMARY KEY (sku_supplier_id),
    FOREIGN KEY (sku_id) REFERENCES skus(sku_id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
);

CREATE TABLE sku_substitutes (
    sku_substitute_id VARCHAR NOT NULL,
    sku_id VARCHAR NOT NULL,
    substitute_sku_id VARCHAR NOT NULL,
    approved BOOLEAN NOT NULL,
    conversion_factor DOUBLE NOT NULL,
    cost_delta_pct DOUBLE NOT NULL,
    priority_rank INTEGER NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE,
    lifecycle_state VARCHAR NOT NULL,
    PRIMARY KEY (sku_substitute_id),
    FOREIGN KEY (sku_id) REFERENCES skus(sku_id),
    FOREIGN KEY (substitute_sku_id) REFERENCES skus(sku_id)
);

CREATE TABLE bom_items (
    bom_id VARCHAR NOT NULL,
    parent_sku_id VARCHAR NOT NULL,
    component_sku_id VARCHAR NOT NULL,
    qty_per_parent DOUBLE NOT NULL,
    uom VARCHAR NOT NULL,
    scrap_rate DOUBLE NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE,
    lifecycle_state VARCHAR NOT NULL,
    PRIMARY KEY (bom_id),
    FOREIGN KEY (parent_sku_id) REFERENCES skus(sku_id),
    FOREIGN KEY (component_sku_id) REFERENCES skus(sku_id)
);

CREATE TABLE forecast_demand (
    demand_id VARCHAR NOT NULL,
    sku_id VARCHAR NOT NULL,
    location_id VARCHAR NOT NULL,
    week_id VARCHAR NOT NULL,
    week_start_date DATE NOT NULL,
    forecast_qty INTEGER NOT NULL,
    uom VARCHAR NOT NULL,
    is_spike_week BOOLEAN NOT NULL,
    seasonality_factor DOUBLE NOT NULL,
    priority_weight DOUBLE NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE,
    lifecycle_state VARCHAR NOT NULL,
    PRIMARY KEY (demand_id),
    FOREIGN KEY (sku_id) REFERENCES skus(sku_id),
    FOREIGN KEY (location_id) REFERENCES locations(location_id)
);

CREATE TABLE inventory (
    inventory_id VARCHAR NOT NULL,
    sku_id VARCHAR NOT NULL,
    location_id VARCHAR NOT NULL,
    snapshot_date DATE NOT NULL,
    on_hand_qty INTEGER NOT NULL,
    reserved_qty INTEGER NOT NULL,
    available_qty INTEGER NOT NULL,
    safety_stock_qty INTEGER NOT NULL,
    reorder_point_qty INTEGER NOT NULL,
    uom VARCHAR NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE,
    lifecycle_state VARCHAR NOT NULL,
    PRIMARY KEY (inventory_id),
    FOREIGN KEY (sku_id) REFERENCES skus(sku_id),
    FOREIGN KEY (location_id) REFERENCES locations(location_id)
);

CREATE TABLE supplier_capacity (
    capacity_id VARCHAR NOT NULL,
    supplier_id VARCHAR NOT NULL,
    week_id VARCHAR NOT NULL,
    week_start_date DATE NOT NULL,
    max_weekly_capacity INTEGER NOT NULL,
    committed_qty INTEGER NOT NULL,
    available_capacity INTEGER NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE,
    lifecycle_state VARCHAR NOT NULL,
    PRIMARY KEY (capacity_id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
);

CREATE TABLE lead_times (
    lead_time_id VARCHAR NOT NULL,
    sku_id VARCHAR NOT NULL,
    supplier_id VARCHAR NOT NULL,
    location_id VARCHAR NOT NULL,
    manufacturing_days INTEGER NOT NULL,
    transit_days INTEGER NOT NULL,
    customs_buffer_days INTEGER NOT NULL,
    total_lead_time_days INTEGER NOT NULL,
    min_order_qty INTEGER NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE,
    lifecycle_state VARCHAR NOT NULL,
    PRIMARY KEY (lead_time_id),
    FOREIGN KEY (sku_id) REFERENCES skus(sku_id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
    FOREIGN KEY (location_id) REFERENCES locations(location_id)
);

CREATE TABLE purchase_orders (
    po_id VARCHAR NOT NULL,
    sku_id VARCHAR NOT NULL,
    supplier_id VARCHAR NOT NULL,
    location_id VARCHAR NOT NULL,
    order_date DATE NOT NULL,
    promised_delivery_date DATE NOT NULL,
    actual_delivery_date DATE,
    arrival_week_id VARCHAR NOT NULL,
    order_qty INTEGER NOT NULL,
    uom VARCHAR NOT NULL,
    unit_cost DOUBLE NOT NULL,
    total_cost DOUBLE NOT NULL,
    transport_delay_days INTEGER NOT NULL,
    current_status VARCHAR NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE,
    PRIMARY KEY (po_id),
    FOREIGN KEY (sku_id) REFERENCES skus(sku_id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
    FOREIGN KEY (location_id) REFERENCES locations(location_id)
);

CREATE TABLE purchase_order_events (
    event_id VARCHAR NOT NULL,
    po_id VARCHAR NOT NULL,
    sequence_num INTEGER NOT NULL,
    from_status VARCHAR,
    to_status VARCHAR NOT NULL,
    event_ts TIMESTAMP NOT NULL,
    actor VARCHAR NOT NULL,
    reason VARCHAR NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE,
    lifecycle_state VARCHAR NOT NULL,
    PRIMARY KEY (event_id),
    FOREIGN KEY (po_id) REFERENCES purchase_orders(po_id)
);

CREATE TABLE production_plans (
    production_id VARCHAR NOT NULL,
    sku_id VARCHAR NOT NULL,
    location_id VARCHAR NOT NULL,
    week_id VARCHAR NOT NULL,
    week_start_date DATE NOT NULL,
    planned_qty INTEGER NOT NULL,
    capacity_limit_qty INTEGER NOT NULL,
    bom_feasible_qty INTEGER NOT NULL,
    achievable_qty INTEGER NOT NULL,
    uom VARCHAR NOT NULL,
    unit_production_cost DOUBLE NOT NULL,
    lifecycle_state VARCHAR NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE,
    PRIMARY KEY (production_id),
    FOREIGN KEY (sku_id) REFERENCES skus(sku_id),
    FOREIGN KEY (location_id) REFERENCES locations(location_id)
);

CREATE TABLE projected_balances (
    balance_id VARCHAR NOT NULL,
    sku_id VARCHAR NOT NULL,
    location_id VARCHAR NOT NULL,
    week_id VARCHAR NOT NULL,
    week_start_date DATE NOT NULL,
    opening_stock INTEGER NOT NULL,
    inbound_qty INTEGER NOT NULL,
    production_qty INTEGER NOT NULL,
    demand_qty INTEGER NOT NULL,
    closing_stock INTEGER NOT NULL,
    safety_stock_qty INTEGER NOT NULL,
    below_safety_stock BOOLEAN NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE,
    lifecycle_state VARCHAR NOT NULL,
    PRIMARY KEY (balance_id),
    FOREIGN KEY (sku_id) REFERENCES skus(sku_id),
    FOREIGN KEY (location_id) REFERENCES locations(location_id)
);

CREATE TABLE shortages (
    shortage_id VARCHAR NOT NULL,
    balance_id VARCHAR NOT NULL,
    sku_id VARCHAR NOT NULL,
    location_id VARCHAR NOT NULL,
    week_id VARCHAR NOT NULL,
    week_start_date DATE NOT NULL,
    shortage_qty INTEGER NOT NULL,
    revenue_at_risk DOUBLE NOT NULL,
    lead_time_days_used INTEGER NOT NULL,
    required_order_by_date DATE NOT NULL,
    root_cause VARCHAR NOT NULL,
    severity VARCHAR NOT NULL,
    priority_score DOUBLE NOT NULL,
    priority_rank INTEGER NOT NULL UNIQUE,
    lifecycle_state VARCHAR NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE,
    PRIMARY KEY (shortage_id),
    FOREIGN KEY (balance_id) REFERENCES projected_balances(balance_id),
    FOREIGN KEY (sku_id) REFERENCES skus(sku_id),
    FOREIGN KEY (location_id) REFERENCES locations(location_id)
);

CREATE TABLE shortage_evidence (
    evidence_id VARCHAR NOT NULL,
    shortage_id VARCHAR NOT NULL,
    source_table VARCHAR NOT NULL,
    source_record_id VARCHAR NOT NULL,
    contribution_type VARCHAR NOT NULL,
    metric_value DOUBLE NOT NULL,
    explanation VARCHAR NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE,
    lifecycle_state VARCHAR NOT NULL,
    PRIMARY KEY (evidence_id),
    FOREIGN KEY (shortage_id) REFERENCES shortages(shortage_id)
);

CREATE TABLE mitigation_options (
    mitigation_id VARCHAR NOT NULL,
    shortage_id VARCHAR NOT NULL,
    mitigation_type VARCHAR NOT NULL,
    target_supplier_id VARCHAR,
    target_sku_id VARCHAR,
    source_location_id VARCHAR,
    mitigation_qty INTEGER NOT NULL,
    cost DOUBLE NOT NULL,
    service_level_impact DOUBLE NOT NULL,
    lead_time_days INTEGER NOT NULL,
    capacity_check_passed BOOLEAN NOT NULL,
    policy_check_passed BOOLEAN NOT NULL,
    score DOUBLE NOT NULL,
    rank INTEGER NOT NULL,
    lifecycle_state VARCHAR NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE,
    PRIMARY KEY (mitigation_id),
    FOREIGN KEY (shortage_id) REFERENCES shortages(shortage_id),
    FOREIGN KEY (target_supplier_id) REFERENCES suppliers(supplier_id),
    FOREIGN KEY (target_sku_id) REFERENCES skus(sku_id),
    FOREIGN KEY (source_location_id) REFERENCES locations(location_id)
);
