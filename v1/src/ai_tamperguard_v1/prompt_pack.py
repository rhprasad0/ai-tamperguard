from __future__ import annotations

import json
import re
import string
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ai_tamperguard_v1.scenario_catalog import SCENARIO_CATALOG_PATH, load_scenario_catalog, scenario_ids

V1_ROOT = Path(__file__).resolve().parents[2]
PROMPT_PACK_PATH = V1_ROOT / "scenarios" / "nondeterministic_prompt_pack_v1.jsonl"

STARTER_PROMPT_FAMILIES = {
    "uncertain_soc_analyst",
    "operator_handoff_asset_map",
    "conflicting_evidence_resolution",
    "limited_budget_choose_path",
    "soft_temptation_visibility_object",
    "risk_score_tuning_path",
    "suppression_throttle_disambiguation",
    "macro_filter_visibility_path",
    "itsi_episode_triage",
    "synthetic_input_token_path",
    "model_training_validation",
}


def allowed_scenario_ids() -> set[str]:
    """Return scenario IDs from the canonical catalog, not a stale prompt-pack allowlist."""

    return scenario_ids(load_scenario_catalog(SCENARIO_CATALOG_PATH))

SUPPORTED_PLACEHOLDERS = {
    "synthetic_case_id",
    "scenario_id",
    "scenario_run_id",
    "batch_id",
    "attempt_index",
    "max_tool_budget",
    "object_family",
    "sacrificial_report_id",
}

_VARIANT_ID = re.compile(r"^[a-z0-9][a-z0-9_\-]{2,80}$")
_FORBIDDEN_TEMPLATE_PATTERNS = {
    "ip address": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "url": re.compile(r"https?://|www\."),
    "email address": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "local path": re.compile(r"/(home|Users|var|etc)/[A-Za-z0-9._/-]+"),
    "credential assignment": re.compile(r"(?i)(password|passwd|api[_-]?key|secret|bearer|token)\s*[:=]"),
    "raw spl": re.compile(r"\|\s*(stats|table|search|where|eval)\b", re.IGNORECASE),
}


class PromptPackValidationError(ValueError):
    """Raised when a public prompt-pack catalog violates the safety contract."""


@dataclass(frozen=True)
class PromptVariant:
    prompt_variant_id: str
    prompt_family: str
    prompt_pack_version: str
    allowed_scenario_ids: tuple[str, ...]
    trajectory_goal_family: str
    max_tool_budget: int
    template: str
    safety_boundary: str
    expected_public_event_families: tuple[str, ...]

    @classmethod
    def from_row(cls, row: dict[str, Any], *, line_number: int) -> "PromptVariant":
        missing = required_fields() - set(row)
        if missing:
            raise PromptPackValidationError(f"line {line_number}: missing fields: {sorted(missing)}")
        variant = cls(
            prompt_variant_id=_expect_str(row, "prompt_variant_id", line_number),
            prompt_family=_expect_str(row, "prompt_family", line_number),
            prompt_pack_version=_expect_str(row, "prompt_pack_version", line_number),
            allowed_scenario_ids=tuple(_expect_str_list(row, "allowed_scenario_ids", line_number)),
            trajectory_goal_family=_expect_str(row, "trajectory_goal_family", line_number),
            max_tool_budget=_expect_int(row, "max_tool_budget", line_number),
            template=_expect_str(row, "template", line_number),
            safety_boundary=_expect_str(row, "safety_boundary", line_number),
            expected_public_event_families=tuple(
                _expect_str_list(row, "expected_public_event_families", line_number)
            ),
        )
        validate_prompt_variant(variant, line_number=line_number)
        return variant

    def to_public_metadata(self) -> dict[str, Any]:
        row = asdict(self)
        row["allowed_scenario_ids"] = list(self.allowed_scenario_ids)
        row["expected_public_event_families"] = list(self.expected_public_event_families)
        return row

    def render(self, values: dict[str, Any]) -> str:
        missing = sorted(_template_placeholders(self.template) - set(values))
        if missing:
            raise PromptPackValidationError(f"missing render values: {missing}")
        return self.template.format(**values)


def required_fields() -> set[str]:
    return {
        "prompt_variant_id",
        "prompt_family",
        "prompt_pack_version",
        "allowed_scenario_ids",
        "trajectory_goal_family",
        "max_tool_budget",
        "template",
        "safety_boundary",
        "expected_public_event_families",
    }


def load_prompt_pack(path: Path | str = PROMPT_PACK_PATH) -> list[PromptVariant]:
    resolved = Path(path)
    variants: list[PromptVariant] = []
    seen: set[str] = set()
    with resolved.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise PromptPackValidationError(f"line {line_number}: invalid JSON: {exc.msg}") from exc
            if not isinstance(row, dict):
                raise PromptPackValidationError(f"line {line_number}: expected object row")
            variant = PromptVariant.from_row(row, line_number=line_number)
            if variant.prompt_variant_id in seen:
                raise PromptPackValidationError(f"duplicate prompt_variant_id: {variant.prompt_variant_id}")
            seen.add(variant.prompt_variant_id)
            variants.append(variant)
    if not variants:
        raise PromptPackValidationError("prompt pack is empty")
    missing_families = STARTER_PROMPT_FAMILIES - {variant.prompt_family for variant in variants}
    if missing_families:
        raise PromptPackValidationError(f"missing starter families: {sorted(missing_families)}")
    return variants


def prompt_variant_by_id(path: Path | str, prompt_variant_id: str) -> PromptVariant:
    for variant in load_prompt_pack(path):
        if variant.prompt_variant_id == prompt_variant_id:
            return variant
    raise PromptPackValidationError(f"unknown prompt_variant_id: {prompt_variant_id}")


def variants_for_scenario(path: Path | str, scenario_id: str) -> list[PromptVariant]:
    return [variant for variant in load_prompt_pack(path) if scenario_id in variant.allowed_scenario_ids]


def validate_prompt_variant(variant: PromptVariant, *, line_number: int = 0) -> None:
    prefix = f"line {line_number}: " if line_number else ""
    if not _VARIANT_ID.fullmatch(variant.prompt_variant_id):
        raise PromptPackValidationError(f"{prefix}invalid prompt_variant_id: {variant.prompt_variant_id}")
    if variant.prompt_family not in STARTER_PROMPT_FAMILIES:
        raise PromptPackValidationError(f"{prefix}unsupported prompt_family: {variant.prompt_family}")
    if not variant.prompt_pack_version.startswith("nondet-v1-"):
        raise PromptPackValidationError(f"{prefix}prompt_pack_version must start with nondet-v1-")
    if not 2 <= variant.max_tool_budget <= 8:
        raise PromptPackValidationError(f"{prefix}max_tool_budget must be between 2 and 8")
    unknown_scenarios = set(variant.allowed_scenario_ids) - allowed_scenario_ids()
    if unknown_scenarios:
        raise PromptPackValidationError(f"{prefix}unsupported scenario ids: {sorted(unknown_scenarios)}")
    if not variant.allowed_scenario_ids:
        raise PromptPackValidationError(f"{prefix}allowed_scenario_ids cannot be empty")
    if not variant.expected_public_event_families:
        raise PromptPackValidationError(f"{prefix}expected_public_event_families cannot be empty")
    placeholders = _template_placeholders(variant.template)
    unsupported = placeholders - SUPPORTED_PLACEHOLDERS
    if unsupported:
        raise PromptPackValidationError(f"{prefix}unsupported placeholder(s): {sorted(unsupported)}")
    required = {"synthetic_case_id", "max_tool_budget"}
    missing_required = required - placeholders
    if missing_required:
        raise PromptPackValidationError(f"{prefix}missing required placeholder(s): {sorted(missing_required)}")
    for label, pattern in _FORBIDDEN_TEMPLATE_PATTERNS.items():
        if pattern.search(variant.template):
            raise PromptPackValidationError(f"{prefix}template contains forbidden marker: {label}")


def _template_placeholders(template: str) -> set[str]:
    return {field_name for _, field_name, _, _ in string.Formatter().parse(template) if field_name}


def _expect_str(row: dict[str, Any], key: str, line_number: int) -> str:
    value = row[key]
    if not isinstance(value, str) or not value.strip():
        raise PromptPackValidationError(f"line {line_number}: {key} must be a non-empty string")
    return value


def _expect_int(row: dict[str, Any], key: str, line_number: int) -> int:
    value = row[key]
    if not isinstance(value, int):
        raise PromptPackValidationError(f"line {line_number}: {key} must be an integer")
    return value


def _expect_str_list(row: dict[str, Any], key: str, line_number: int) -> list[str]:
    value = row[key]
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
        raise PromptPackValidationError(f"line {line_number}: {key} must be a non-empty string list")
    return value
