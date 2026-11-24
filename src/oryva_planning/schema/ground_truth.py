"""Strictly isolated ground-truth schema (never imported by planning modules)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from oryva_planning.schema.enums import IssueType

GROUND_TRUTH_COLUMNS: tuple[str, ...] = (
    "ground_truth_id",
    "issue_type",
    "target_table",
    "affected_id",
    "related_ids",
    "expected_detection_rule",
    "injected_detail",
)


class GroundTruthRecord(BaseModel):
    ground_truth_id: str = Field(..., pattern=r"^GT-\d{4}-\d{4}$")
    issue_type: IssueType
    target_table: str
    affected_id: str
    related_ids: str
    expected_detection_rule: str
    injected_detail: str
