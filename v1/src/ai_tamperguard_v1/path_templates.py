from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai_tamperguard_v1.scenario_catalog import SCENARIO_CATALOG_PATH, ScenarioDefinition, load_scenario_catalog

V1_ROOT = Path(__file__).resolve().parents[2]
PATH_TEMPLATES_PATH = V1_ROOT / "scenarios" / "path_templates_v1.jsonl"

_TEMPLATE_ID = re.compile(r"^[a-z0-9][a-z0-9_\-]{2,100}$")
_VALID_PATH_TYPES = {
    "benign_control",
    "hard_negative",
    "gray_zone",
    "attempted_positive",
    "successful_synthetic",
    "blocked",
}
_VALID_LABEL_POLICIES = {"benign", "positive_proxy", "needs_review", "hard_negative"}
_VALID_OUTCOMES = {"benign", "attempted", "blocked", "failed", "successful_synthetic", "needs_review"}


class PathTemplateValidationError(ValueError):
    """Raised when path-template catalog rows violate the safety contract."""


@dataclass(frozen=True)
class PathTemplate:
    path_template_id: str
    scenario_id: str
    path_type: str
    expected_action_sequence: tuple[str, ...]
    allowed_object_types: tuple[str, ...]
    forbidden_object_types: tuple[str, ...]
    label_family: str
    label_binary_policy: str
    outcome: str
    post_run_verification: tuple[str, ...]
    paired_control_path_template_id: str | None

    @classmethod
    def from_row(cls, row: dict[str, Any], *, line_number: int) -> "PathTemplate":
        missing = _required_fields() - set(row)
        if missing:
            raise PathTemplateValidationError(f"line {line_number}: missing fields: {sorted(missing)}")
        paired = row["paired_control_path_template_id"]
        if paired is not None and (not isinstance(paired, str) or not paired.strip()):
            raise PathTemplateValidationError(f"line {line_number}: paired_control_path_template_id must be null or string")
        template = cls(
            path_template_id=_expect_str(row, "path_template_id", line_number),
            scenario_id=_expect_str(row, "scenario_id", line_number),
            path_type=_expect_str(row, "path_type", line_number),
            expected_action_sequence=tuple(_expect_str_list(row, "expected_action_sequence", line_number)),
            allowed_object_types=tuple(_expect_str_list(row, "allowed_object_types", line_number)),
            forbidden_object_types=tuple(_expect_str_list(row, "forbidden_object_types", line_number)),
            label_family=_expect_str(row, "label_family", line_number),
            label_binary_policy=_expect_str(row, "label_binary_policy", line_number),
            outcome=_expect_str(row, "outcome", line_number),
            post_run_verification=tuple(_expect_str_list(row, "post_run_verification", line_number)),
            paired_control_path_template_id=paired,
        )
        _validate_template_shape(template, line_number=line_number)
        return template


def load_path_templates(
    path: Path | str = PATH_TEMPLATES_PATH,
    *,
    scenarios: list[ScenarioDefinition] | None = None,
) -> list[PathTemplate]:
    resolved = Path(path)
    catalog = scenarios if scenarios is not None else load_scenario_catalog(SCENARIO_CATALOG_PATH)
    scenarios_by_id = {scenario.scenario_id: scenario for scenario in catalog}
    templates: list[PathTemplate] = []
    seen: set[str] = set()
    with resolved.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise PathTemplateValidationError(f"line {line_number}: invalid JSON: {exc.msg}") from exc
            if not isinstance(row, dict):
                raise PathTemplateValidationError(f"line {line_number}: expected object row")
            template = PathTemplate.from_row(row, line_number=line_number)
            if template.path_template_id in seen:
                raise PathTemplateValidationError(f"duplicate path_template_id: {template.path_template_id}")
            seen.add(template.path_template_id)
            scenario = scenarios_by_id.get(template.scenario_id)
            if scenario is None:
                raise PathTemplateValidationError(f"line {line_number}: unknown scenario_id: {template.scenario_id}")
            if template.path_type not in scenario.path_types_supported:
                raise PathTemplateValidationError(
                    f"line {line_number}: path_type {template.path_type} is not supported by {template.scenario_id}"
                )
            forbidden_overlap = set(template.allowed_object_types) & set(template.forbidden_object_types)
            if forbidden_overlap:
                raise PathTemplateValidationError(
                    f"line {line_number}: object type cannot be both allowed and forbidden: {sorted(forbidden_overlap)}"
                )
            templates.append(template)
    if not templates:
        raise PathTemplateValidationError("path-template catalog is empty")
    known_template_ids = {template.path_template_id for template in templates}
    for template in templates:
        paired = template.paired_control_path_template_id
        if paired and paired not in known_template_ids:
            raise PathTemplateValidationError(
                f"{template.path_template_id}: unknown paired_control_path_template_id: {paired}"
            )
    return templates


def _required_fields() -> set[str]:
    return {
        "path_template_id",
        "scenario_id",
        "path_type",
        "expected_action_sequence",
        "allowed_object_types",
        "forbidden_object_types",
        "label_family",
        "label_binary_policy",
        "outcome",
        "post_run_verification",
        "paired_control_path_template_id",
    }


def _validate_template_shape(template: PathTemplate, *, line_number: int) -> None:
    prefix = f"line {line_number}: "
    if not _TEMPLATE_ID.fullmatch(template.path_template_id):
        raise PathTemplateValidationError(f"{prefix}invalid path_template_id: {template.path_template_id}")
    if template.path_type not in _VALID_PATH_TYPES:
        raise PathTemplateValidationError(f"{prefix}unsupported path_type: {template.path_type}")
    if template.label_binary_policy not in _VALID_LABEL_POLICIES:
        raise PathTemplateValidationError(f"{prefix}unsupported label_binary_policy: {template.label_binary_policy}")
    if template.outcome not in _VALID_OUTCOMES:
        raise PathTemplateValidationError(f"{prefix}unsupported outcome: {template.outcome}")


def _expect_str(row: dict[str, Any], key: str, line_number: int) -> str:
    value = row[key]
    if not isinstance(value, str) or not value.strip():
        raise PathTemplateValidationError(f"line {line_number}: {key} must be a non-empty string")
    return value


def _expect_str_list(row: dict[str, Any], key: str, line_number: int) -> list[str]:
    value = row[key]
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
        raise PathTemplateValidationError(f"line {line_number}: {key} must be a non-empty string list")
    return value
