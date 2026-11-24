"""Read-only Streamlit dashboard for Oryva Demand, Inventory & Supply Planning.

Run with:
    python -m streamlit run src/oryva_planning/dashboard/app.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Oryva AI — Supply Planning Dashboard",
    layout="wide",
)


def _format_inr(amount: float) -> str:
    val = float(amount)
    abs_val = abs(val)
    sign = "-" if val < 0 else ""
    if abs_val >= 1e7:
        return f"{sign}₹{abs_val / 1e7:.2f} Cr"
    if abs_val >= 1e5:
        return f"{sign}₹{abs_val / 1e5:.2f} L"
    return f"{sign}₹{abs_val:,.0f}"


@st.cache_data(show_spinner=False)
def load_planning_csvs(data_dir: str) -> dict[str, pd.DataFrame]:
    csv_dir = Path(data_dir) / "inputs" / "csv"
    if not csv_dir.exists():
        raise FileNotFoundError(f"CSV directory not found: {csv_dir}")
    names = [
        "skus",
        "locations",
        "suppliers",
        "projected_balances",
        "shortages",
        "shortage_evidence",
        "mitigation_options",
        "purchase_orders",
        "purchase_order_events",
        "supplier_capacity",
        "production_plans",
    ]
    return {n: pd.read_csv(csv_dir / f"{n}.csv") for n in names}


def main() -> None:
    st.title("Oryva AI — Demand, Inventory & Supply Planning")
    st.caption(
        "Read-only planning explorer over deterministic CSV exports. "
        "Planning views never read data/ground_truth/."
    )

    with st.sidebar:
        st.header("Data Source")
        data_dir = st.text_input("Export data directory", value="data")
        try:
            tables = load_planning_csvs(data_dir)
        except FileNotFoundError as exc:
            st.error(str(exc))
            st.info(
                "Generate starter data first with: "
                "`python -m oryva_planning generate --scale starter --seed 20261022`"
            )
            st.stop()

        skus = tables["skus"]
        locations = tables["locations"]
        shortages = tables["shortages"]

        st.header("Filters")
        selected_regions = st.multiselect(
            "Region",
            options=sorted(locations["region"].unique().tolist()),
            default=sorted(locations["region"].unique().tolist()),
        )
        loc_ids_in_region = locations[locations["region"].isin(selected_regions)][
            "location_id"
        ].tolist()
        selected_locs = st.multiselect(
            "Location",
            options=sorted(loc_ids_in_region),
            default=sorted(loc_ids_in_region),
        )
        selected_severities = st.multiselect(
            "Shortage Severity",
            options=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
            default=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
        )
        all_causes = sorted(shortages["root_cause"].dropna().unique().tolist())
        selected_causes = st.multiselect(
            "Root Cause",
            options=all_causes,
            default=all_causes,
        )

    filtered_shortages = shortages[
        shortages["location_id"].isin(selected_locs)
        & shortages["severity"].isin(selected_severities)
        & shortages["root_cause"].isin(selected_causes)
    ].sort_values(["priority_rank", "shortage_id"], kind="mergesort")

    balances = tables["projected_balances"]
    filtered_balances = balances[balances["location_id"].isin(selected_locs)]
    mitigations = tables["mitigation_options"]
    evidence = tables["shortage_evidence"]
    pos = tables["purchase_orders"]
    po_events = tables["purchase_order_events"]

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "1. Executive Overview",
            "2. Shortage Triage & Mitigations",
            "3. Weekly Balance Ledger",
            "4. PO Lifecycle & Audit",
        ]
    )

    with tab1:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("SKUs", f"{len(skus):,}")
        c2.metric("Filtered Shortages", f"{len(filtered_shortages):,}")
        c3.metric(
            "Units Short",
            f"{int(filtered_shortages['shortage_qty'].sum()):,}"
            if not filtered_shortages.empty
            else "0",
        )
        c4.metric(
            "Revenue at Risk",
            _format_inr(float(filtered_shortages["revenue_at_risk"].sum()))
            if not filtered_shortages.empty
            else "₹0",
        )
        c5.metric("Purchase Orders", f"{len(pos):,}")

        st.subheader("Weekly Network Demand vs. Supply (Inbound + Production)")
        wk_df = (
            filtered_balances.groupby("week_id", sort=True)[
                ["demand_qty", "inbound_qty", "production_qty"]
            ]
            .sum()
            .assign(total_supply=lambda d: d["inbound_qty"] + d["production_qty"])
        )
        st.line_chart(wk_df[["demand_qty", "total_supply"]])

        left, right = st.columns(2)
        with left:
            st.subheader("Shortages by Root Cause")
            if not filtered_shortages.empty:
                st.bar_chart(filtered_shortages["root_cause"].value_counts())
            else:
                st.info("No shortages match the active filters.")
        with right:
            st.subheader("Shortages by Severity")
            if not filtered_shortages.empty:
                sev_counts = (
                    filtered_shortages["severity"]
                    .value_counts()
                    .reindex(["CRITICAL", "HIGH", "MEDIUM", "LOW"], fill_value=0)
                )
                st.bar_chart(sev_counts)
            else:
                st.info("No shortages match the active filters.")

    with tab2:
        st.subheader(f"Prioritized Shortages ({len(filtered_shortages):,})")
        display_cols = [
            "priority_rank",
            "shortage_id",
            "sku_id",
            "location_id",
            "week_id",
            "shortage_qty",
            "revenue_at_risk",
            "root_cause",
            "severity",
            "priority_score",
            "lead_time_days_used",
            "required_order_by_date",
            "lifecycle_state",
        ]
        st.dataframe(filtered_shortages[display_cols], use_container_width=True, hide_index=True)

        if not filtered_shortages.empty:
            chosen_sid = st.selectbox(
                "Inspect Shortage Evidence & Ranked Mitigation Trade-Offs",
                options=filtered_shortages["shortage_id"].tolist(),
            )
            st.markdown(f"#### Linked Traceability Evidence (`shortage_evidence`) for `{chosen_sid}`")
            ev_rows = evidence[evidence["shortage_id"] == chosen_sid].sort_values(
                "evidence_id", kind="mergesort"
            )
            st.dataframe(
                ev_rows[
                    [
                        "evidence_id",
                        "source_table",
                        "source_record_id",
                        "contribution_type",
                        "metric_value",
                        "explanation",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

            st.markdown(f"#### Ranked Mitigation Options (`mitigation_options`) for `{chosen_sid}`")
            mit_rows = mitigations[mitigations["shortage_id"] == chosen_sid].sort_values(
                "rank", kind="mergesort"
            )
            st.dataframe(
                mit_rows[
                    [
                        "rank",
                        "mitigation_id",
                        "mitigation_type",
                        "mitigation_qty",
                        "cost",
                        "service_level_impact",
                        "lead_time_days",
                        "capacity_check_passed",
                        "policy_check_passed",
                        "score",
                        "lifecycle_state",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

    with tab3:
        st.subheader("SKU-Location 52-Week Projected Available Balance Reconciliation")
        col_sku, col_loc = st.columns(2)
        pick_sku = col_sku.selectbox("SKU", options=sorted(skus["sku_id"].unique().tolist()))
        pick_loc = col_loc.selectbox(
            "Location",
            options=sorted(selected_locs) if selected_locs else sorted(locations["location_id"].tolist()),
        )
        ledger = balances[
            (balances["sku_id"] == pick_sku) & (balances["location_id"] == pick_loc)
        ].sort_values("week_id", kind="mergesort")

        if not ledger.empty:
            st.line_chart(
                ledger.set_index("week_id")[["closing_stock", "safety_stock_qty"]]
            )
            st.dataframe(
                ledger[
                    [
                        "week_id",
                        "opening_stock",
                        "inbound_qty",
                        "production_qty",
                        "demand_qty",
                        "closing_stock",
                        "safety_stock_qty",
                        "below_safety_stock",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

    with tab4:
        st.subheader("Purchase Order Event-Sourced History")
        delayed_first = pos.sort_values(
            ["transport_delay_days", "po_id"], ascending=[False, True], kind="mergesort"
        )
        pick_po = st.selectbox("Select Purchase Order", options=delayed_first["po_id"].head(200).tolist())
        po_row = pos[pos["po_id"] == pick_po]
        st.dataframe(
            po_row[
                [
                    "po_id",
                    "sku_id",
                    "supplier_id",
                    "location_id",
                    "order_date",
                    "promised_delivery_date",
                    "actual_delivery_date",
                    "order_qty",
                    "uom",
                    "total_cost",
                    "transport_delay_days",
                    "current_status",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )
        ev_po = po_events[po_events["po_id"] == pick_po].sort_values("sequence_num", kind="mergesort")
        st.dataframe(
            ev_po[["sequence_num", "event_id", "from_status", "to_status", "event_ts", "actor", "reason"]],
            use_container_width=True,
            hide_index=True,
        )

        st.divider()
        show_audit = st.checkbox(
            "Show Isolated Anomaly Detector Evaluation (reads data/ground_truth/detector_metrics.json)",
            value=False,
        )
        if show_audit:
            metrics_path = Path(data_dir) / "ground_truth" / "detector_metrics.json"
            if metrics_path.exists():
                metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
                mdf = pd.DataFrame.from_dict(metrics, orient="index").reset_index().rename(
                    columns={"index": "issue_type"}
                )
                st.dataframe(mdf, use_container_width=True, hide_index=True)
            else:
                st.warning(f"No detector_metrics.json found at {metrics_path}")


if __name__ == "__main__":
    main()
