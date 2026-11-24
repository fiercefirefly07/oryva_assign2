"""Phase 7 & 8 tests: Pydantic row checks, disk validation, SQL seed with FK ON, JSON/SQLite, repro."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

from oryva_planning.config import load_config
from oryva_planning.export.repro import run_reproducibility_check
from oryva_planning.pipeline import run_pipeline
from oryva_planning.schema.models import ROW_MODELS
from oryva_planning.schema.registry import ENTITY_ORDER
from oryva_planning.validation import validate_data_directory


def test_exports_sql_seed_fk_integrity_and_disk_validation(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    docs_dir = tmp_path / "docs"
    cfg = load_config("starter", seed_override=20261022, output_dir_override=str(data_dir))
    res = run_pipeline(
        cfg,
        export_outputs=True,
        write_docs=True,
        output_dir=data_dir,
        docs_dir=docs_dir,
        validate_baseline=True,
    )

    # Validate sampled baseline rows with Pydantic v2 models
    for tbl, model_cls in ROW_MODELS.items():
        for rec in res.baseline_tables[tbl].head(20).to_dict(orient="records"):
            cleaned = {k: (None if pd.isna(v) else v) for k, v in rec.items()}
            model_cls.model_validate(cleaned)

    # Validate exported CSV directory end-to-end
    disk_report = validate_data_directory(data_dir)
    assert disk_report.passed, f"Disk validation failures: {disk_report.failed_checks}"

    # Verify SQLite and JSON match CSV row counts
    db_path = data_dir / "inputs" / "sqlite" / "oryva_planning.sqlite"
    conn = sqlite3.connect(str(db_path))
    try:
        for tbl in ENTITY_ORDER:
            assert conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0] == len(res.final_tables[tbl])
            json_rows = json.loads((data_dir / "inputs" / "json" / f"{tbl}.json").read_text(encoding="utf-8"))
            assert len(json_rows) == len(res.final_tables[tbl])
    finally:
        conn.close()

    # Verify schema.sql + seed.sql execute cleanly in SQLite with FOREIGN KEYS ENFORCED
    ddl_sql = (data_dir / "inputs" / "sql" / "schema.sql").read_text(encoding="utf-8")
    seed_sql = (data_dir / "inputs" / "sql" / "seed.sql").read_text(encoding="utf-8")
    mem_conn = sqlite3.connect(":memory:")
    try:
        mem_conn.execute("PRAGMA foreign_keys = ON;")
        mem_conn.executescript(ddl_sql)
        mem_conn.executescript(seed_sql)
        fk_errors = mem_conn.execute("PRAGMA foreign_key_check;").fetchall()
        assert fk_errors == [], f"SQL seed foreign key violations: {fk_errors[:5]}"
    finally:
        mem_conn.close()

    # Verify documentation & manifest deliverables exist
    for doc_name in [
        "DATA_DICTIONARY.md",
        "ER_DIAGRAM.md",
        "SOURCE_MANIFEST.md",
        "VALIDATION_SUMMARY.md",
    ]:
        assert (docs_dir / doc_name).exists()
    assert (data_dir / "source_manifest.json").exists()
    assert (data_dir / "checksums.sha256").exists()


def test_reproducibility_two_runs_bit_for_bit_identical(tmp_path: Path) -> None:
    result = run_reproducibility_check(
        scale="starter",
        seed=20261022,
        work_dir=tmp_path,
        report_path=tmp_path / "reproducibility_report.md",
    )
    assert result["passed"] is True
    assert (tmp_path / "reproducibility_report.md").exists()
    assert len(result["comparisons"]) == len(ENTITY_ORDER) + 1


def test_static_html_report_and_streamlit_app_syntax(tmp_path: Path) -> None:
    import ast
    from oryva_planning.config import PROJECT_ROOT
    from oryva_planning.export.html_report import generate_html_report

    data_dir = tmp_path / "data"
    cfg = load_config("starter", seed_override=20261022, output_dir_override=str(data_dir))
    cfg.export.formats = ["csv"]
    run_pipeline(cfg, export_outputs=True, output_dir=data_dir, validate_baseline=False)

    html_out = generate_html_report(data_dir=data_dir, output_path=tmp_path / "dashboard.html")
    assert html_out.exists()
    content = html_out.read_text(encoding="utf-8")
    assert "Oryva AI" in content
    assert "shortage_evidence" in content
    assert "mitigation_options" in content
    assert "<script src=" not in content and "<link rel=\"stylesheet\" href=\"http" not in content

    # Verify Streamlit dashboard module parses cleanly
    st_app = PROJECT_ROOT / "src" / "oryva_planning" / "dashboard" / "app.py"
    assert st_app.exists()
    ast.parse(st_app.read_text(encoding="utf-8"))
