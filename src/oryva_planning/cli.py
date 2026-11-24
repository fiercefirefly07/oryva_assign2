"""Typer CLI entrypoint for Oryva Demand, Inventory & Supply Planning."""

from __future__ import annotations

from pathlib import Path

import typer

from oryva_planning.config import load_config
from oryva_planning.export.html_report import generate_html_report
from oryva_planning.export.manifest import (
    write_data_dictionary,
    write_er_diagram,
    write_validation_summary,
)
from oryva_planning.export.repro import run_reproducibility_check
from oryva_planning.pipeline import run_pipeline
from oryva_planning.schema.registry import ENTITY_ORDER, ENTITY_REGISTRY
from oryva_planning.validation import validate_data_directory

app = typer.Typer(
    name="oryva-planning",
    help="Oryva AI Demand, Inventory & Supply Planning — synthetic generator, planner, and validator.",
    add_completion=False,
)


@app.command("schema-info")
def schema_info() -> None:
    typer.echo(f"Registered tables: {len(ENTITY_ORDER)}")
    for idx, tbl in enumerate(ENTITY_ORDER, start=1):
        spec = ENTITY_REGISTRY[tbl]
        typer.echo(
            f"  {idx:02d}. {spec.name:<20} table={spec.table_name:<22} "
            f"layer={spec.layer:<10} pk={spec.primary_key:<18} fields={len(spec.fields)}"
        )


@app.command("check-config")
def check_config(
    scale: str = typer.Option("starter", help="Config profile ('starter', 'full') or YAML path."),
    seed: int | None = typer.Option(None, help="Optional seed override."),
) -> None:
    cfg = load_config(scale, seed_override=seed)
    typer.echo(
        f"Config OK: name={cfg.name} seed={cfg.seed} "
        f"skus={cfg.scale.num_skus} locations={cfg.scale.num_locations} "
        f"suppliers={cfg.scale.num_suppliers} pos={cfg.scale.num_purchase_orders} "
        f"weeks={cfg.num_weeks}"
    )


@app.command("generate")
def generate(
    scale: str = typer.Option("starter", help="Scale profile: 'starter' or 'full' (or YAML path)."),
    seed: int = typer.Option(20261022, help="Fixed deterministic random seed."),
    output_dir: str = typer.Option("data", help="Output directory for inputs/ and ground_truth/."),
    docs_dir: str = typer.Option("docs", help="Directory to write generated docs."),
    write_docs: bool = typer.Option(True, help="Also refresh data dictionary, ER, manifest, and validation summary."),
) -> None:
    cfg = load_config(scale, seed_override=seed, output_dir_override=output_dir)
    res = run_pipeline(
        cfg,
        export_outputs=True,
        write_docs=write_docs,
        output_dir=Path(output_dir),
        docs_dir=Path(docs_dir),
        validate_baseline=True,
    )
    typer.echo(f"Generated scale={cfg.name} seed={cfg.seed} into {output_dir}/")
    assert res.export_meta is not None
    for tbl in ENTITY_ORDER:
        typer.echo(f"  {tbl:<24} {res.export_meta['row_counts'][tbl]:>10,} rows")
    typer.echo(f"  {'ground_truth':<24} {res.export_meta['row_counts']['ground_truth']:>10,} rows")
    typer.echo(
        f"Baseline validation ({res.baseline_report.sql_backend}): "
        f"{'PASS' if res.baseline_report.passed else 'FAIL'}"
    )
    typer.echo(
        f"Final validation    ({res.final_report.sql_backend}): "
        f"{'PASS' if res.final_report.passed else 'FAIL'}"
    )
    overall = res.detector_metrics["overall"]
    typer.echo(
        f"Anomaly detectors overall: P={overall['precision']:.4f} "
        f"R={overall['recall']:.4f} F1={overall['f1']:.4f} "
        f"(TP={overall['tp']}, FP={overall['fp']}, FN={overall['fn']})"
    )
    if not res.baseline_report.passed or not res.final_report.passed:
        for fail in res.baseline_report.failed_checks:
            typer.echo(f"  BASELINE FAIL [{fail.category}] {fail.check}: {fail.violations}")
        for fail in res.final_report.failed_checks:
            typer.echo(f"  FINAL FAIL [{fail.category}] {fail.check}: {fail.violations}")
        raise typer.Exit(code=1)


@app.command("validate")
def validate(
    data_dir: str = typer.Option("data", help="Data directory containing inputs/ and ground_truth/."),
    docs_dir: str = typer.Option("docs", help="Optional docs directory to refresh VALIDATION_SUMMARY.md."),
) -> None:
    report = validate_data_directory(data_dir)
    write_validation_summary(report, Path(docs_dir), Path(data_dir))
    passed_cnt = sum(1 for c in report.checks if c.passed)
    typer.echo(
        f"Validation ({report.sql_backend}): {'PASS' if report.passed else 'FAIL'} "
        f"({passed_cnt}/{len(report.checks)} checks passed)"
    )
    for fail in report.failed_checks:
        typer.echo(f"  FAIL [{fail.category}] {fail.check}: {fail.violations} violations ({fail.details})")
    if report.detector_metrics:
        for k, m in report.detector_metrics.items():
            typer.echo(
                f"  Detector {k:<28} expected={m['expected']} detected={m['detected']} "
                f"P={m['precision']:.4f} R={m['recall']:.4f}"
            )
    if not report.passed:
        raise typer.Exit(code=1)


@app.command("repro")
def repro(
    scale: str = typer.Option("starter", help="Scale profile to verify ('starter' or 'full')."),
    seed: int = typer.Option(20261022, help="Fixed seed."),
    report_path: str = typer.Option("reproducibility_report.md", help="Path to write Markdown report."),
) -> None:
    result = run_reproducibility_check(
        scale=scale,
        seed=seed,
        work_dir=Path("data"),
        report_path=Path(report_path),
    )
    docs_copy = Path("docs/REPRODUCIBILITY_REPORT.md")
    docs_copy.parent.mkdir(parents=True, exist_ok=True)
    docs_copy.write_text(Path(report_path).read_text(encoding="utf-8"), encoding="utf-8", newline="\n")

    typer.echo(
        f"Reproducibility ({scale}, seed={seed}): "
        f"{'PASS (100% identical)' if result['passed'] else 'FAIL'}"
    )
    typer.echo(f"Report written to {report_path} and {docs_copy}")
    if not result["passed"]:
        raise typer.Exit(code=1)


@app.command("export-docs")
def export_docs(
    data_dir: str = typer.Option("data", help="Data directory for validation summary."),
    docs_dir: str = typer.Option("docs", help="Target docs directory."),
) -> None:
    d_path = Path(docs_dir)
    write_data_dictionary(d_path)
    write_er_diagram(d_path)
    if (Path(data_dir) / "inputs" / "csv").exists():
        report = validate_data_directory(data_dir)
        write_validation_summary(report, d_path, Path(data_dir))
    if (Path(data_dir) / "inputs" / "csv").exists():
        generate_html_report(data_dir=data_dir, output_path=d_path / "planning_dashboard.html")
    typer.echo(f"Documentation written to {d_path}/")


@app.command("report")
def report(
    data_dir: str = typer.Option("data", help="Data directory containing inputs/csv/."),
    output: str = typer.Option(
        "docs/planning_dashboard.html", help="Destination path for self-contained static HTML dashboard."
    ),
) -> None:
    """Generate a self-contained interactive static HTML planning dashboard."""
    out_path = generate_html_report(data_dir=data_dir, output_path=output)
    typer.echo(f"Static HTML dashboard written to {out_path}")
