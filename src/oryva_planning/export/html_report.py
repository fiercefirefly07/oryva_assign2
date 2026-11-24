"""Self-contained, deterministic, zero-CDN interactive static HTML planning dashboard."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import pandas as pd


def _format_inr(amount: float) -> str:
    """Format INR values concisely using Indian numbering (Lakhs / Crores)."""
    val = float(amount)
    abs_val = abs(val)
    sign = "-" if val < 0 else ""
    if abs_val >= 1e7:
        return f"{sign}₹{abs_val / 1e7:.2f} Cr"
    if abs_val >= 1e5:
        return f"{sign}₹{abs_val / 1e5:.2f} L"
    return f"{sign}₹{abs_val:,.0f}"


def _svg_hbar_chart(
    items: list[tuple[str, float, str]],
    width: int = 520,
    bar_height: int = 24,
    gap: int = 10,
    value_fmt: str = "int",
) -> str:
    """Build a crisp deterministic inline SVG horizontal bar chart."""
    if not items:
        return "<p class='muted'>No data available.</p>"
    label_w = 195
    val_w = 75
    plot_w = max(80, width - label_w - val_w - 16)
    max_val = max(max(v for _, v, _ in items), 1.0)
    total_h = len(items) * (bar_height + gap) + 12

    parts = [
        f'<svg viewBox="0 0 {width} {total_h}" width="100%" height="{total_h}" '
        f'role="img" aria-label="Horizontal bar chart" xmlns="http://www.w3.org/2000/svg">'
    ]
    for idx, (label, val, color) in enumerate(items):
        y = idx * (bar_height + gap) + 6
        bw = max(2.0, (val / max_val) * plot_w) if val > 0 else 0.0
        lbl_esc = html.escape(label.replace("_", " "))
        val_str = f"{int(round(val)):,}" if value_fmt == "int" else f"{val:,.1f}"
        parts.append(
            f'<text x="{label_w - 10}" y="{y + bar_height * 0.68:.1f}" '
            f'text-anchor="end" font-size="12" fill="#334155" font-family="system-ui, sans-serif">'
            f"{lbl_esc}</text>"
        )
        parts.append(
            f'<rect x="{label_w}" y="{y}" width="{plot_w}" height="{bar_height}" '
            f'rx="5" fill="#f1f5f9"/>'
        )
        parts.append(
            f'<rect x="{label_w}" y="{y}" width="{bw:.1f}" height="{bar_height}" '
            f'rx="5" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{label_w + plot_w + 10}" y="{y + bar_height * 0.68:.1f}" '
            f'text-anchor="start" font-size="12" font-weight="600" fill="#0f172a" '
            f'font-family="system-ui, sans-serif">{val_str}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _svg_weekly_line_chart(
    weeks: list[str],
    demand_vals: list[int],
    supply_vals: list[int],
    width: int = 860,
    height: int = 240,
) -> str:
    """Build an inline SVG multi-series line chart of weekly Demand vs Supply."""
    if not weeks:
        return "<p class='muted'>No weekly data available.</p>"
    pad_l, pad_r, pad_t, pad_b = 64, 20, 20, 38
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    n = len(weeks)
    max_y = max(max(demand_vals, default=1), max(supply_vals, default=1), 1)
    y_ceil = max_y * 1.12

    def _xy(idx: int, val: int) -> tuple[float, float]:
        x = pad_l + (idx / max(n - 1, 1)) * plot_w
        y = pad_t + plot_h - (val / y_ceil) * plot_h
        return x, y

    dem_pts = " ".join(f"{_xy(i, v)[0]:.1f},{_xy(i, v)[1]:.1f}" for i, v in enumerate(demand_vals))
    sup_pts = " ".join(f"{_xy(i, v)[0]:.1f},{_xy(i, v)[1]:.1f}" for i, v in enumerate(supply_vals))

    parts = [
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'role="img" aria-label="Weekly demand vs supply trend" xmlns="http://www.w3.org/2000/svg">'
    ]
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        gy = pad_t + plot_h * (1.0 - frac)
        gval = int(round(y_ceil * frac))
        parts.append(
            f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{width - pad_r}" y2="{gy:.1f}" '
            f'stroke="#e2e8f0" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{pad_l - 8}" y="{gy + 4:.1f}" text-anchor="end" font-size="11" '
            f'fill="#64748b" font-family="system-ui, sans-serif">{gval:,}</text>'
        )

    step = max(1, n // 8)
    for i in range(0, n, step):
        lx, _ = _xy(i, 0)
        parts.append(
            f'<text x="{lx:.1f}" y="{height - 12}" text-anchor="middle" font-size="11" '
            f'fill="#64748b" font-family="system-ui, sans-serif">{html.escape(weeks[i])}</text>'
        )

    parts.append(
        f'<polyline fill="none" stroke="#2563eb" stroke-width="2.4" points="{dem_pts}"/>'
    )
    parts.append(
        f'<polyline fill="none" stroke="#059669" stroke-width="2.2" stroke-dasharray="6,3" points="{sup_pts}"/>'
    )
    parts.append("</svg>")
    return "".join(parts)


def generate_html_report(
    data_dir: str | Path = "data",
    output_path: str | Path = "docs/planning_dashboard.html",
    max_shortage_rows: int = 200,
    max_po_rows: int = 120,
) -> Path:
    """Generate a self-contained static HTML planning dashboard from exported CSV artifacts."""
    base = Path(data_dir)
    csv_dir = base / "inputs" / "csv"
    if not csv_dir.exists():
        raise FileNotFoundError(f"CSV directory not found: {csv_dir}")

    skus = pd.read_csv(csv_dir / "skus.csv")
    locations = pd.read_csv(csv_dir / "locations.csv")
    suppliers = pd.read_csv(csv_dir / "suppliers.csv")
    balances = pd.read_csv(csv_dir / "projected_balances.csv")
    shortages = pd.read_csv(csv_dir / "shortages.csv")
    evidence = pd.read_csv(csv_dir / "shortage_evidence.csv")
    mitigations = pd.read_csv(csv_dir / "mitigation_options.csv")
    pos = pd.read_csv(csv_dir / "purchase_orders.csv")
    po_events = pd.read_csv(csv_dir / "purchase_order_events.csv")

    manifest_path = base / "source_manifest.json"
    manifest: dict[str, Any] = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    )
    metrics_path = base / "ground_truth" / "detector_metrics.json"
    detector_metrics: dict[str, Any] = (
        json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
    )

    scale_name = str(manifest.get("config_scale", "starter"))
    fixed_seed = str(manifest.get("fixed_seed", "20261022"))
    horizon = str(manifest.get("planning_horizon", "2026W01..2026W52"))

    # KPI aggregates
    total_skus = len(skus)
    total_locs = len(locations)
    total_sups = len(suppliers)
    total_pos = len(pos)
    total_shortages = len(shortages)
    total_units_short = int(shortages["shortage_qty"].sum()) if not shortages.empty else 0
    total_rev_risk = float(shortages["revenue_at_risk"].sum()) if not shortages.empty else 0.0
    total_mitigations = len(mitigations)
    avg_top_service = (
        float(mitigations[mitigations["rank"] == 1]["service_level_impact"].mean() * 100.0)
        if not mitigations.empty
        else 0.0
    )

    # Chart 1: Root Causes
    rc_colors = {
        "DEMAND_SPIKE": "#dc2626",
        "LATE_INBOUND": "#ea580c",
        "SUPPLIER_CAPACITY_CAP": "#d97706",
        "PRODUCTION_CONSTRAINT": "#7c3aed",
        "LEAD_TIME_GAP": "#2563eb",
        "LOW_OPENING_INVENTORY": "#0891b2",
        "COMPOUND_DEFICIT": "#475569",
    }
    rc_counts = shortages["root_cause"].value_counts()
    rc_items = [
        (str(k), float(v), rc_colors.get(str(k), "#475569"))
        for k, v in sorted(rc_counts.items(), key=lambda kv: (-int(kv[1]), str(kv[0])))
    ]
    svg_root_cause = _svg_hbar_chart(rc_items)

    # Chart 2: Severity
    sev_order = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    sev_colors = {
        "CRITICAL": "#b91c1c",
        "HIGH": "#ea580c",
        "MEDIUM": "#ca8a04",
        "LOW": "#0284c7",
    }
    sev_counts = shortages["severity"].value_counts().to_dict()
    sev_items = [(s, float(sev_counts.get(s, 0)), sev_colors[s]) for s in sev_order]
    svg_severity = _svg_hbar_chart(sev_items)

    # Chart 3: Mitigation strategies
    mit_counts = mitigations["mitigation_type"].value_counts()
    mit_items = [
        (str(k), float(v), "#0d9488")
        for k, v in sorted(mit_counts.items(), key=lambda kv: (-int(kv[1]), str(kv[0])))
    ]
    svg_mitigation = _svg_hbar_chart(mit_items)

    # Chart 4: Weekly Demand vs Supply (Inbound + Production)
    wk_agg = (
        balances.groupby("week_id", sort=True)[["demand_qty", "inbound_qty", "production_qty"]]
        .sum()
        .reset_index()
    )
    wk_agg["total_supply"] = wk_agg["inbound_qty"] + wk_agg["production_qty"]
    svg_weekly = _svg_weekly_line_chart(
        wk_agg["week_id"].astype(str).tolist(),
        wk_agg["demand_qty"].astype(int).tolist(),
        wk_agg["total_supply"].astype(int).tolist(),
    )

    # Prepare interactive JSON payload for Shortage + Evidence + Mitigation Explorer
    sku_name_map = dict(zip(skus["sku_id"], skus["sku_name"]))
    loc_name_map = dict(zip(locations["location_id"], locations["location_name"]))

    top_shorts = shortages.sort_values(
        ["priority_rank", "shortage_id"], kind="mergesort"
    ).head(max_shortage_rows)
    top_sids = set(top_shorts["shortage_id"].astype(str))

    ev_grouped: dict[str, list[dict[str, Any]]] = {}
    for r in evidence[evidence["shortage_id"].isin(top_sids)].sort_values(
        "evidence_id", kind="mergesort"
    ).itertuples(index=False):
        ev_grouped.setdefault(str(r.shortage_id), []).append(
            {
                "evidence_id": str(r.evidence_id),
                "source_table": str(r.source_table),
                "source_record_id": str(r.source_record_id),
                "contribution_type": str(r.contribution_type),
                "metric_value": round(float(r.metric_value), 2),
                "explanation": str(r.explanation),
            }
        )

    mit_grouped: dict[str, list[dict[str, Any]]] = {}
    for r in mitigations[mitigations["shortage_id"].isin(top_sids)].sort_values(
        ["shortage_id", "rank", "mitigation_id"], kind="mergesort"
    ).itertuples(index=False):
        mit_grouped.setdefault(str(r.shortage_id), []).append(
            {
                "mitigation_id": str(r.mitigation_id),
                "rank": int(r.rank),
                "type": str(r.mitigation_type),
                "qty": int(r.mitigation_qty),
                "cost": round(float(r.cost), 2),
                "service_pct": round(float(r.service_level_impact) * 100.0, 1),
                "lead_time_days": int(r.lead_time_days),
                "capacity_ok": bool(r.capacity_check_passed),
                "policy_ok": bool(r.policy_check_passed),
                "score": round(float(r.score), 2),
                "target": (
                    str(r.target_supplier_id)
                    if pd.notna(r.target_supplier_id)
                    else (
                        str(r.target_sku_id)
                        if pd.notna(r.target_sku_id)
                        else (str(r.source_location_id) if pd.notna(r.source_location_id) else "-")
                    )
                ),
            }
        )

    shortage_payload: list[dict[str, Any]] = []
    for r in top_shorts.itertuples(index=False):
        sid = str(r.shortage_id)
        shortage_payload.append(
            {
                "shortage_id": sid,
                "rank": int(r.priority_rank),
                "sku_id": str(r.sku_id),
                "sku_name": str(sku_name_map.get(r.sku_id, "")),
                "location_id": str(r.location_id),
                "location_name": str(loc_name_map.get(r.location_id, "")),
                "week_id": str(r.week_id),
                "shortage_qty": int(r.shortage_qty),
                "revenue_at_risk": round(float(r.revenue_at_risk), 2),
                "lead_time_days_used": int(r.lead_time_days_used),
                "required_order_by_date": str(r.required_order_by_date),
                "root_cause": str(r.root_cause),
                "severity": str(r.severity),
                "priority_score": round(float(r.priority_score), 2),
                "status": str(r.lifecycle_state),
                "evidence": ev_grouped.get(sid, []),
                "mitigations": mit_grouped.get(sid, []),
            }
        )

    # PO lifecycle sample (prioritize delayed & active POs so timeline viewer is rich)
    po_sorted = pos.sort_values(
        ["transport_delay_days", "po_id"], ascending=[False, True], kind="mergesort"
    ).head(max_po_rows)
    po_ids_keep = set(po_sorted["po_id"].astype(str))
    ev_by_po: dict[str, list[dict[str, Any]]] = {}
    for r in po_events[po_events["po_id"].isin(po_ids_keep)].sort_values(
        ["po_id", "sequence_num"], kind="mergesort"
    ).itertuples(index=False):
        ev_by_po.setdefault(str(r.po_id), []).append(
            {
                "seq": int(r.sequence_num),
                "from": str(r.from_status) if pd.notna(r.from_status) else "INIT",
                "to": str(r.to_status),
                "ts": str(r.event_ts),
                "actor": str(r.actor),
                "reason": str(r.reason),
            }
        )

    po_payload = [
        {
            "po_id": str(r.po_id),
            "sku_id": str(r.sku_id),
            "supplier_id": str(r.supplier_id),
            "location_id": str(r.location_id),
            "arrival_week_id": str(r.arrival_week_id),
            "order_qty": int(r.order_qty),
            "uom": str(r.uom),
            "total_cost": round(float(r.total_cost), 2),
            "delay_days": int(r.transport_delay_days),
            "status": str(r.current_status),
            "events": ev_by_po.get(str(r.po_id), []),
        }
        for r in po_sorted.itertuples(index=False)
    ]

    # PO status chart
    po_status_counts = pos["current_status"].value_counts()
    po_status_items = [
        (str(k), float(v), "#3b82f6")
        for k, v in sorted(po_status_counts.items(), key=lambda kv: (-int(kv[1]), str(kv[0])))
    ]
    svg_po_status = _svg_hbar_chart(po_status_items)

    # Audit section HTML (strictly isolated ground-truth evaluation metrics)
    if detector_metrics:
        audit_rows = []
        for k in sorted(detector_metrics.keys(), key=lambda x: (x == "overall", x)):
            m = detector_metrics[k]
            row_cls = " class='total-row'" if k == "overall" else ""
            audit_rows.append(
                f"<tr{row_cls}><td><code>{html.escape(k)}</code></td>"
                f"<td class='num'>{m['expected']}</td><td class='num'>{m['detected']}</td>"
                f"<td class='num'>{m['tp']}</td><td class='num'>{m['fp']}</td><td class='num'>{m['fn']}</td>"
                f"<td class='num'>{m['precision']:.4f}</td><td class='num'>{m['recall']:.4f}</td>"
                f"<td class='num'><strong>{m['f1']:.4f}</strong></td></tr>"
            )
        audit_table_html = (
            "<table class='data-table'><thead><tr>"
            "<th>Issue Type</th><th class='num'>Expected</th><th class='num'>Detected</th>"
            "<th class='num'>TP</th><th class='num'>FP</th><th class='num'>FN</th>"
            "<th class='num'>Precision</th><th class='num'>Recall</th><th class='num'>F1</th>"
            "</tr></thead><tbody>" + "".join(audit_rows) + "</tbody></table>"
        )
    else:
        audit_table_html = "<p class='muted'>No detector_metrics.json found in data/ground_truth/.</p>"

    row_counts_map: dict[str, int] = manifest.get("row_counts", {})
    manifest_rows = "".join(
        f"<tr><td><code>{html.escape(tbl)}</code></td><td class='num'>{cnt:,}</td></tr>"
        for tbl, cnt in sorted(row_counts_map.items())
    )

    loc_options = "".join(
        f'<option value="{html.escape(str(r.location_id))}">{html.escape(str(r.location_id))} — {html.escape(str(r.location_name))}</option>'
        for r in locations.sort_values("location_id", kind="mergesort").itertuples(index=False)
    )
    rc_options = "".join(
        f'<option value="{html.escape(rc)}">{html.escape(rc.replace("_", " "))}</option>'
        for rc in sorted(shortages["root_cause"].dropna().unique().tolist())
    )

    shortages_json = json.dumps(shortage_payload, ensure_ascii=False).replace("</", "<\/")
    pos_json = json.dumps(po_payload, ensure_ascii=False).replace("</", "<\/")

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Oryva AI — Demand, Inventory &amp; Supply Planning Dashboard</title>
<style>
  :root {{
    --bg: #f8fafc;
    --card: #ffffff;
    --border: #e2e8f0;
    --text: #0f172a;
    --muted: #64748b;
    --accent: #2563eb;
    --accent-soft: #eff6ff;
    --ok: #059669;
    --warn: #d97706;
    --bad: #dc2626;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
  }}
  header {{
    background: #0f172a;
    color: #f8fafc;
    padding: 20px 28px;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }}
  header h1 {{ margin: 0; font-size: 20px; letter-spacing: -0.01em; }}
  header .sub {{ font-size: 13px; color: #94a3b8; margin-top: 2px; }}
  .pill-row {{ display: flex; gap: 8px; flex-wrap: wrap; }}
  .pill {{
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 999px;
    padding: 4px 12px;
    font-size: 12px;
    color: #e2e8f0;
  }}
  nav.tabs {{
    background: var(--card);
    border-bottom: 1px solid var(--border);
    padding: 0 28px;
    display: flex;
    gap: 6px;
    overflow-x: auto;
  }}
  nav.tabs button {{
    background: none;
    border: none;
    border-bottom: 3px solid transparent;
    padding: 13px 16px;
    font-size: 14px;
    font-weight: 600;
    color: var(--muted);
    cursor: pointer;
    white-space: nowrap;
  }}
  nav.tabs button.active {{
    color: var(--accent);
    border-bottom-color: var(--accent);
  }}
  main {{ max-width: 1320px; margin: 22px auto; padding: 0 24px 48px; }}
  .tab-panel {{ display: none; }}
  .tab-panel.active {{ display: block; }}
  .kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: 14px;
    margin-bottom: 20px;
  }}
  .kpi {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px 18px;
  }}
  .kpi .label {{ font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }}
  .kpi .val {{ font-size: 24px; font-weight: 700; margin-top: 6px; }}
  .kpi .hint {{ font-size: 12px; color: var(--muted); margin-top: 2px; }}
  .grid-2 {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(460px, 1fr));
    gap: 16px;
    margin-bottom: 16px;
  }}
  .card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 18px 20px;
    margin-bottom: 16px;
  }}
  .card h2 {{ margin: 0 0 12px; font-size: 16px; }}
  .card h3 {{ margin: 14px 0 8px; font-size: 14px; color: #334155; }}
  .legend {{ display: flex; gap: 18px; font-size: 12px; color: var(--muted); margin-bottom: 8px; }}
  .dot {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }}
  .controls {{
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 14px;
    align-items: center;
  }}
  .controls input, .controls select {{
    padding: 8px 10px;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    font-size: 13px;
    background: #fff;
  }}
  .table-wrap {{ overflow-x: auto; max-height: 440px; border: 1px solid var(--border); border-radius: 8px; }}
  table.data-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  table.data-table th {{
    position: sticky;
    top: 0;
    background: #f1f5f9;
    text-align: left;
    padding: 9px 10px;
    border-bottom: 1px solid var(--border);
    font-weight: 600;
    color: #334155;
    white-space: nowrap;
  }}
  table.data-table td {{
    padding: 8px 10px;
    border-bottom: 1px solid #f1f5f9;
    vertical-align: top;
  }}
  table.data-table tbody tr:hover {{ background: #f8fafc; cursor: pointer; }}
  table.data-table tbody tr.selected {{ background: var(--accent-soft); }}
  table.data-table tr.total-row td {{ background: #f8fafc; border-top: 2px solid #cbd5e1; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
  }}
  .sev-CRITICAL {{ background: #fee2e2; color: #991b1b; }}
  .sev-HIGH {{ background: #ffedd5; color: #9a3412; }}
  .sev-MEDIUM {{ background: #fef9c3; color: #854d0e; }}
  .sev-LOW {{ background: #e0f2fe; color: #075985; }}
  .ok-badge {{ background: #d1fae5; color: #065f46; }}
  .bad-badge {{ background: #fee2e2; color: #991b1b; }}
  .muted {{ color: var(--muted); font-size: 13px; }}
  .detail-box {{
    background: #f8fafc;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 16px;
    margin-top: 14px;
  }}
  .banner {{
    background: #fffbeb;
    border: 1px solid #fde68a;
    color: #92400e;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 13px;
    margin-bottom: 14px;
  }}
  code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }}
</style>
</head>
<body>
<header>
  <div>
    <h1>Oryva AI — Demand, Inventory &amp; Supply Planning</h1>
    <div class="sub">Read-only static dashboard generated from deterministic pipeline exports</div>
  </div>
  <div class="pill-row">
    <span class="pill">Scale: {html.escape(scale_name)}</span>
    <span class="pill">Seed: {html.escape(fixed_seed)}</span>
    <span class="pill">Horizon: {html.escape(horizon)}</span>
    <span class="pill">Currency: INR (&#8377;)</span>
  </div>
</header>

<nav class="tabs">
  <button class="active" data-tab="overview">1. Executive Overview</button>
  <button data-tab="shortages">2. Shortages, Evidence &amp; Mitigations</button>
  <button data-tab="supply">3. Purchase Orders &amp; Event History</button>
  <button data-tab="audit">4. Validation &amp; Anomaly Audit</button>
</nav>

<main>
  <!-- TAB 1: OVERVIEW -->
  <section id="tab-overview" class="tab-panel active">
    <div class="kpi-grid">
      <div class="kpi">
        <div class="label">Network Master</div>
        <div class="val">{total_skus:,} SKUs</div>
        <div class="hint">{total_locs:,} locations &middot; {total_sups:,} suppliers</div>
      </div>
      <div class="kpi">
        <div class="label">Total Shortages</div>
        <div class="val">{total_shortages:,}</div>
        <div class="hint">{total_units_short:,} units short across 52 weeks</div>
      </div>
      <div class="kpi">
        <div class="label">Revenue at Risk</div>
        <div class="val">{html.escape(_format_inr(total_rev_risk))}</div>
        <div class="hint">Derived from shortage qty &times; unit price</div>
      </div>
      <div class="kpi">
        <div class="label">Mitigation Options</div>
        <div class="val">{total_mitigations:,}</div>
        <div class="hint">Avg Rank-1 recovery: {avg_top_service:.1f}%</div>
      </div>
      <div class="kpi">
        <div class="label">Inbound Orders</div>
        <div class="val">{total_pos:,} POs</div>
        <div class="hint">{len(po_events):,} append-only lifecycle events</div>
      </div>
    </div>

    <div class="card">
      <h2>Weekly Network Demand vs. Supply (Inbound POs + Internal Production)</h2>
      <div class="legend">
        <span><span class="dot" style="background:#2563eb"></span>Forecast Demand (units)</span>
        <span><span class="dot" style="background:#059669"></span>Total Supply: Inbound + Production (units)</span>
      </div>
      {svg_weekly}
    </div>

    <div class="grid-2">
      <div class="card">
        <h2>Shortages by Explainable Root Cause</h2>
        {svg_root_cause}
      </div>
      <div class="card">
        <h2>Shortages by Priority Severity</h2>
        {svg_severity}
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <h2>Mitigation Strategy Mix</h2>
        {svg_mitigation}
      </div>
      <div class="card">
        <h2>Purchase Order Current Lifecycle Status</h2>
        {svg_po_status}
      </div>
    </div>
  </section>

  <!-- TAB 2: SHORTAGES -->
  <section id="tab-shortages" class="tab-panel">
    <div class="card">
      <h2>Prioritized Shortage Triage (Top {len(shortage_payload)} by Priority Rank)</h2>
      <div class="controls">
        <input id="shortSearch" type="text" placeholder="Search SKU, shortage ID, week..." style="min-width:220px" />
        <select id="sevFilter">
          <option value="">All Severities</option>
          <option value="CRITICAL">CRITICAL</option>
          <option value="HIGH">HIGH</option>
          <option value="MEDIUM">MEDIUM</option>
          <option value="LOW">LOW</option>
        </select>
        <select id="rcFilter">
          <option value="">All Root Causes</option>
          {rc_options}
        </select>
        <select id="locFilter">
          <option value="">All Locations</option>
          {loc_options}
        </select>
        <span id="shortCount" class="muted"></span>
      </div>

      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th class="num">Rank</th>
              <th>Shortage ID</th>
              <th>SKU</th>
              <th>Location</th>
              <th>Week</th>
              <th class="num">Short Qty</th>
              <th class="num">Rev at Risk (&#8377;)</th>
              <th>Root Cause</th>
              <th>Severity</th>
              <th class="num">Score</th>
            </tr>
          </thead>
          <tbody id="shortBody"></tbody>
        </table>
      </div>

      <div id="shortDetail" class="detail-box">
        <p class="muted">Click any shortage row above to inspect its linked <code>shortage_evidence</code> rows and ranked <code>mitigation_options</code> trade-offs.</p>
      </div>
    </div>
  </section>

  <!-- TAB 3: PO LIFECYCLE -->
  <section id="tab-supply" class="tab-panel">
    <div class="card">
      <h2>Inbound Purchase Orders &amp; Append-Only Event History (Top {len(po_payload)} by Delay)</h2>
      <div class="controls">
        <input id="poSearch" type="text" placeholder="Search PO ID, SKU, Supplier..." style="min-width:220px" />
        <select id="poStatusFilter">
          <option value="">All Statuses</option>
          <option value="RECEIVED">RECEIVED</option>
          <option value="DELAYED">DELAYED</option>
          <option value="IN_TRANSIT">IN_TRANSIT</option>
          <option value="CONFIRMED">CONFIRMED</option>
          <option value="CANCELLED">CANCELLED</option>
        </select>
        <span id="poCount" class="muted"></span>
      </div>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>PO ID</th>
              <th>SKU</th>
              <th>Supplier</th>
              <th>Location</th>
              <th>Arrival Week</th>
              <th class="num">Qty</th>
              <th>UOM</th>
              <th class="num">Total Cost (&#8377;)</th>
              <th class="num">Delay (d)</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody id="poBody"></tbody>
        </table>
      </div>
      <div id="poDetail" class="detail-box">
        <p class="muted">Click any Purchase Order row above to view its immutable <code>purchase_order_events</code> state transition log.</p>
      </div>
    </div>
  </section>

  <!-- TAB 4: AUDIT -->
  <section id="tab-audit" class="tab-panel">
    <div class="banner">
      <strong>Ground Truth Wall Notice:</strong> This audit panel reads <code>data/ground_truth/detector_metrics.json</code> strictly for post-hoc evaluation. The planning engine in <code>src/oryva_planning/planning/</code> never imports or reads ground truth.
    </div>
    <div class="card">
      <h2>Anomaly Detector Precision, Recall &amp; F1 Scorecard</h2>
      {audit_table_html}
    </div>
    <div class="card">
      <h2>Generated Dataset Provenance &amp; Row Counts</h2>
      <p class="muted">Provenance: 100% synthetic data generated programmatically; zero external datasets used.</p>
      <table class="data-table" style="max-width:480px">
        <thead><tr><th>Table</th><th class="num">Rows</th></tr></thead>
        <tbody>{manifest_rows}</tbody>
      </table>
    </div>
  </section>
</main>

<script>
const SHORTAGES = {shortages_json};
const POS = {pos_json};

function esc(s) {{
  return String(s ?? "").replace(/[&<>"]/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}}[c]));
}}
function fmtNum(n) {{
  return Number(n).toLocaleString("en-IN");
}}

// Tab switching
document.querySelectorAll("nav.tabs button").forEach(btn => {{
  btn.addEventListener("click", () => {{
    document.querySelectorAll("nav.tabs button").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
  }});
}});

// Shortages table + drill-down
let selectedShortId = SHORTAGES.length ? SHORTAGES[0].shortage_id : null;

function renderShortDetail(item) {{
  const box = document.getElementById("shortDetail");
  if (!item) {{
    box.innerHTML = "<p class='muted'>No shortage selected.</p>";
    return;
  }}
  const evRows = item.evidence.map(e => `
    <tr>
      <td><code>${{esc(e.evidence_id)}}</code></td>
      <td><code>${{esc(e.source_table)}}</code></td>
      <td><code>${{esc(e.source_record_id)}}</code></td>
      <td>${{esc(e.contribution_type)}}</td>
      <td class="num">${{fmtNum(e.metric_value)}}</td>
      <td>${{esc(e.explanation)}}</td>
    </tr>
  `).join("");

  const mitRows = item.mitigations.map(m => `
    <tr>
      <td class="num"><strong>#${{m.rank}}</strong></td>
      <td><code>${{esc(m.mitigation_id)}}</code></td>
      <td>${{esc(m.type)}}</td>
      <td><code>${{esc(m.target)}}</code></td>
      <td class="num">${{fmtNum(m.qty)}}</td>
      <td class="num">&#8377;${{fmtNum(m.cost)}}</td>
      <td class="num">${{m.service_pct.toFixed(1)}}%</td>
      <td class="num">${{m.lead_time_days}}d</td>
      <td><span class="badge ${{m.capacity_ok ? 'ok-badge' : 'bad-badge'}}">${{m.capacity_ok ? 'PASS' : 'FAIL'}}</span></td>
      <td><span class="badge ${{m.policy_ok ? 'ok-badge' : 'bad-badge'}}">${{m.policy_ok ? 'PASS' : 'FAIL'}}</span></td>
      <td class="num"><strong>${{m.score.toFixed(2)}}</strong></td>
    </tr>
  `).join("");

  box.innerHTML = `
    <h3>Shortage <code>${{esc(item.shortage_id)}}</code> — ${{esc(item.sku_id)}} (${{esc(item.sku_name)}}) at ${{esc(item.location_id)}} (${{esc(item.week_id)}})</h3>
    <p class="muted">
      Root Cause: <strong>${{esc(item.root_cause)}}</strong> &middot;
      Lead Time Applied: <strong>${{item.lead_time_days_used}} days</strong> &middot;
      Required Order-By Date: <strong>${{esc(item.required_order_by_date)}}</strong> &middot;
      Status: <strong>${{esc(item.status)}}</strong>
    </p>
    <h3>Linked Traceability Evidence (<code>shortage_evidence</code>)</h3>
    <table class="data-table">
      <thead><tr><th>Evidence ID</th><th>Source Table</th><th>Source Record</th><th>Contribution</th><th class="num">Metric</th><th>Explanation</th></tr></thead>
      <tbody>${{evRows || '<tr><td colspan="6" class="muted">None</td></tr>'}}</tbody>
    </table>
    <h3>Ranked Mitigation Options &amp; Trade-Offs (<code>mitigation_options</code>)</h3>
    <table class="data-table">
      <thead><tr><th class="num">Rank</th><th>Mitigation ID</th><th>Strategy</th><th>Target</th><th class="num">Qty</th><th class="num">Cost</th><th class="num">Service</th><th class="num">Lead Time</th><th>Cap</th><th>Policy</th><th class="num">Score</th></tr></thead>
      <tbody>${{mitRows || '<tr><td colspan="11" class="muted">None</td></tr>'}}</tbody>
    </table>
  `;
}}

function renderShortages() {{
  const q = document.getElementById("shortSearch").value.trim().toLowerCase();
  const sev = document.getElementById("sevFilter").value;
  const rc = document.getElementById("rcFilter").value;
  const loc = document.getElementById("locFilter").value;

  const filtered = SHORTAGES.filter(s => {{
    if (sev && s.severity !== sev) return false;
    if (rc && s.root_cause !== rc) return false;
    if (loc && s.location_id !== loc) return false;
    if (q) {{
      const hay = (s.shortage_id + " " + s.sku_id + " " + s.sku_name + " " + s.week_id + " " + s.root_cause).toLowerCase();
      if (!hay.includes(q)) return false;
    }}
    return true;
  }});

  document.getElementById("shortCount").textContent = `Showing ${{filtered.length}} of ${{SHORTAGES.length}}`;
  const tbody = document.getElementById("shortBody");
  tbody.innerHTML = filtered.map(s => `
    <tr data-id="${{esc(s.shortage_id)}}" class="${{s.shortage_id === selectedShortId ? 'selected' : ''}}">
      <td class="num">${{s.rank}}</td>
      <td><code>${{esc(s.shortage_id)}}</code></td>
      <td><code>${{esc(s.sku_id)}}</code></td>
      <td><code>${{esc(s.location_id)}}</code></td>
      <td>${{esc(s.week_id)}}</td>
      <td class="num">${{fmtNum(s.shortage_qty)}}</td>
      <td class="num">${{fmtNum(s.revenue_at_risk)}}</td>
      <td>${{esc(s.root_cause)}}</td>
      <td><span class="badge sev-${{esc(s.severity)}}">${{esc(s.severity)}}</span></td>
      <td class="num">${{s.priority_score.toFixed(1)}}</td>
    </tr>
  `).join("");

  tbody.querySelectorAll("tr").forEach(tr => {{
    tr.addEventListener("click", () => {{
      selectedShortId = tr.dataset.id;
      const found = SHORTAGES.find(x => x.shortage_id === selectedShortId);
      renderShortages();
      renderShortDetail(found);
    }});
  }});

  const active = filtered.find(x => x.shortage_id === selectedShortId) || filtered[0] || null;
  if (active) {{
    selectedShortId = active.shortage_id;
    renderShortDetail(active);
  }}
}}

["shortSearch", "sevFilter", "rcFilter", "locFilter"].forEach(id => {{
  document.getElementById(id).addEventListener("input", renderShortages);
  document.getElementById(id).addEventListener("change", renderShortages);
}});

// PO table + event history viewer
let selectedPoId = POS.length ? POS[0].po_id : null;

function renderPoDetail(po) {{
  const box = document.getElementById("poDetail");
  if (!po) {{
    box.innerHTML = "<p class='muted'>No PO selected.</p>";
    return;
  }}
  const rows = po.events.map(e => `
    <tr>
      <td class="num">${{e.seq}}</td>
      <td><code>${{esc(e.from)}}</code> &rarr; <code>${{esc(e.to)}}</code></td>
      <td><code>${{esc(e.ts)}}</code></td>
      <td>${{esc(e.actor)}}</td>
      <td>${{esc(e.reason)}}</td>
    </tr>
  `).join("");
  box.innerHTML = `
    <h3>Append-Only State Transition History for <code>${{esc(po.po_id)}}</code></h3>
    <table class="data-table">
      <thead><tr><th class="num">Seq</th><th>Transition</th><th>Timestamp (UTC)</th><th>Actor</th><th>Reason</th></tr></thead>
      <tbody>${{rows}}</tbody>
    </table>
  `;
}}

function renderPOs() {{
  const q = document.getElementById("poSearch").value.trim().toLowerCase();
  const st = document.getElementById("poStatusFilter").value;
  const filtered = POS.filter(p => {{
    if (st && p.status !== st) return false;
    if (q) {{
      const hay = (p.po_id + " " + p.sku_id + " " + p.supplier_id + " " + p.location_id).toLowerCase();
      if (!hay.includes(q)) return false;
    }}
    return true;
  }});
  document.getElementById("poCount").textContent = `Showing ${{filtered.length}} of ${{POS.length}}`;
  const tbody = document.getElementById("poBody");
  tbody.innerHTML = filtered.map(p => `
    <tr data-id="${{esc(p.po_id)}}" class="${{p.po_id === selectedPoId ? 'selected' : ''}}">
      <td><code>${{esc(p.po_id)}}</code></td>
      <td><code>${{esc(p.sku_id)}}</code></td>
      <td><code>${{esc(p.supplier_id)}}</code></td>
      <td><code>${{esc(p.location_id)}}</code></td>
      <td>${{esc(p.arrival_week_id)}}</td>
      <td class="num">${{fmtNum(p.order_qty)}}</td>
      <td>${{esc(p.uom)}}</td>
      <td class="num">${{fmtNum(p.total_cost)}}</td>
      <td class="num">${{p.delay_days}}</td>
      <td>${{esc(p.status)}}</td>
    </tr>
  `).join("");

  tbody.querySelectorAll("tr").forEach(tr => {{
    tr.addEventListener("click", () => {{
      selectedPoId = tr.dataset.id;
      const found = POS.find(x => x.po_id === selectedPoId);
      renderPOs();
      renderPoDetail(found);
    }});
  }});

  const active = filtered.find(x => x.po_id === selectedPoId) || filtered[0] || null;
  if (active) {{
    selectedPoId = active.po_id;
    renderPoDetail(active);
  }}
}}

["poSearch", "poStatusFilter"].forEach(id => {{
  document.getElementById(id).addEventListener("input", renderPOs);
  document.getElementById(id).addEventListener("change", renderPOs);
}});

renderShortages();
renderPOs();
</script>
</body>
</html>
"""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_doc, encoding="utf-8", newline="\n")
    return out
