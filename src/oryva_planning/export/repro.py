"""Two-run reproducibility proof comparing row counts and SHA-256 checksums."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from oryva_planning.config import load_config


def run_reproducibility_check(
    scale: str = "starter",
    seed: int = 20261022,
    work_dir: Path | None = None,
    report_path: Path | None = None,
    keep_runs: bool = False,
) -> dict[str, Any]:
    from oryva_planning.pipeline import run_pipeline

    base = Path(work_dir) if work_dir is not None else Path("data")
    run1_dir = base / "repro_run_1"
    run2_dir = base / "repro_run_2"
    for d in (run1_dir, run2_dir):
        if d.exists():
            shutil.rmtree(d)

    cfg1 = load_config(scale, seed_override=seed, output_dir_override=str(run1_dir))
    cfg2 = load_config(scale, seed_override=seed, output_dir_override=str(run2_dir))
    cfg1.export.formats = ["csv"]
    cfg2.export.formats = ["csv"]

    res1 = run_pipeline(cfg1, export_outputs=True, write_docs=False, output_dir=run1_dir, validate_baseline=False)
    res2 = run_pipeline(cfg2, export_outputs=True, write_docs=False, output_dir=run2_dir, validate_baseline=False)

    assert res1.export_meta is not None and res2.export_meta is not None
    c1, c2 = res1.export_meta["checksums"], res2.export_meta["checksums"]
    r1, r2 = res1.export_meta["row_counts"], res2.export_meta["row_counts"]

    all_keys = sorted(set(c1.keys()) | set(c2.keys()))
    rows: list[dict[str, Any]] = []
    all_match = True
    for key in all_keys:
        tbl = Path(key).stem
        cnt1, cnt2 = r1.get(tbl, -1), r2.get(tbl, -1)
        sha1, sha2 = c1.get(key, "MISSING"), c2.get(key, "MISSING")
        matched = (cnt1 == cnt2) and (sha1 == sha2)
        if not matched:
            all_match = False
        rows.append(
            {
                "artifact": key,
                "run1_rows": cnt1,
                "run2_rows": cnt2,
                "run1_sha256": sha1,
                "run2_sha256": sha2,
                "match": matched,
            }
        )

    lines = [
        "# Reproducibility Report",
        "",
        f"- **Scale Profile**: `{scale}`",
        f"- **Fixed Seed**: `{seed}`",
        f"- **Command Verified**: `python -m oryva_planning generate --scale {scale} --seed {seed}`",
        f"- **Verdict**: **{'PASS — 100% BIT-FOR-BIT IDENTICAL' if all_match else 'FAIL — MISMATCH DETECTED'}**",
        "",
        "## Run 1 vs Run 2 Comparison",
        "",
        "| Artifact | Run 1 Rows | Run 2 Rows | SHA-256 (first 16 hex) | Match |",
        "|---|---:|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| `{row['artifact']}` | {row['run1_rows']:,} | {row['run2_rows']:,} "
            f"| `{row['run1_sha256'][:16]}...` | {'PASS' if row['match'] else 'FAIL'} |"
        )
    lines.append("")
    md = "\n".join(lines)

    out_report = Path(report_path) if report_path is not None else Path("reproducibility_report.md")
    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_report.write_text(md, encoding="utf-8", newline="\n")

    if not keep_runs:
        shutil.rmtree(run1_dir, ignore_errors=True)
        shutil.rmtree(run2_dir, ignore_errors=True)

    return {
        "passed": all_match,
        "scale": scale,
        "seed": seed,
        "comparisons": rows,
        "report_path": str(out_report),
    }
