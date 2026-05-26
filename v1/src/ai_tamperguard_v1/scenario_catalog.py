from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

V1_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_CATALOG_PATH = V1_ROOT / "scenarios" / "scenario_catalog_v1.jsonl"
SCENARIO_ALIASES_PATH = V1_ROOT / "scenarios" / "scenario_aliases_v1.jsonl"

_SCENARIO_ID = re.compile(r"^scenario_\d{3}$")
_SCENARIO_SLUG = re.compile(r"^[a-z0-9][a-z0-9_]{2,100}$")
_ALLOWED_STATUSES = {"required_v1", "optional_v1", "future", "doc_only", "implemented"}


class ScenarioCatalogValidationError(ValueError):
    """Raised when the canonical scenario catalog is malformed."""


@dataclass(frozen=True)
class ScenarioDefinition:
    scenario_id: str
    scenario_slug: str
    name: str
    family: str
    canonical_status: str
    path_types_supported: tuple[str, ...]
    variation_axes_supported: tuple[str, ...]
    minimum_prompt_families: int
    paired_control_scenario_ids: tuple[str, ...]
    verification_requirements: tuple[str, ...]
    allowed_object_types: tuple[str, ...]
    allowed_surfaces: tuple[str, ...]
    blocked_condition: str
    positive_condition: str
    post_run_verification: str
    public_claim_boundary: str
    reset_requirements: tuple[str, ...]
    known_limitations: str
    source_subset_status: str | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any], *, line_number: int) -> "ScenarioDefinition":
        missing = _required_fields() - set(row)
        if missing:
            raise ScenarioCatalogValidationError(f"line {line_number}: missing fields: {sorted(missing)}")
        scenario = cls(
            scenario_id=_expect_str(row, "scenario_id", line_number),
            scenario_slug=_expect_str(row, "scenario_slug", line_number),
            name=_expect_str(row, "name", line_number),
            family=_expect_str(row, "family", line_number),
            canonical_status=_expect_str(row, "canonical_status", line_number),
            path_types_supported=tuple(_expect_str_list(row, "path_types_supported", line_number)),
            variation_axes_supported=tuple(_expect_str_list(row, "variation_axes_supported", line_number)),
            minimum_prompt_families=_expect_int(row, "minimum_prompt_families", line_number),
            paired_control_scenario_ids=tuple(_expect_optional_str_list(row, "paired_control_scenario_ids", line_number)),
            verification_requirements=tuple(_expect_str_list(row, "verification_requirements", line_number)),
            allowed_object_types=tuple(_expect_str_list(row, "allowed_object_types", line_number)),
            allowed_surfaces=tuple(_expect_str_list(row, "allowed_surfaces", line_number)),
            blocked_condition=_expect_str(row, "blocked_condition", line_number),
            positive_condition=_expect_str(row, "positive_condition", line_number),
            post_run_verification=_expect_str(row, "post_run_verification", line_number),
            public_claim_boundary=_expect_str(row, "public_claim_boundary", line_number),
            reset_requirements=tuple(_expect_str_list(row, "reset_requirements", line_number)),
            known_limitations=_expect_str(row, "known_limitations", line_number),
            source_subset_status=row.get("source_subset_status") if isinstance(row.get("source_subset_status"), str) else None,
        )
        _validate_scenario(scenario, line_number=line_number)
        return scenario


def load_scenario_catalog(path: Path | str = SCENARIO_CATALOG_PATH) -> list[ScenarioDefinition]:
    resolved = Path(path)
    scenarios: list[ScenarioDefinition] = []
    seen: set[str] = set()
    seen_slugs: set[str] = set()
    with resolved.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ScenarioCatalogValidationError(f"line {line_number}: invalid JSON: {exc.msg}") from exc
            if not isinstance(row, dict):
                raise ScenarioCatalogValidationError(f"line {line_number}: expected object row")
            raw_scenario_id = row.get("scenario_id")
            if isinstance(raw_scenario_id, str) and raw_scenario_id in seen:
                raise ScenarioCatalogValidationError(f"duplicate scenario_id: {raw_scenario_id}")
            if "scenario_slug" not in row and isinstance(row.get("name"), str):
                row = {**row, "scenario_slug": re.sub(r"[^a-z0-9]+", "_", row["name"].lower()).strip("_")}
            scenario = ScenarioDefinition.from_row(row, line_number=line_number)
            if scenario.scenario_id in seen:
                raise ScenarioCatalogValidationError(f"duplicate scenario_id: {scenario.scenario_id}")
            if scenario.scenario_slug in seen_slugs:
                raise ScenarioCatalogValidationError(f"duplicate scenario_slug: {scenario.scenario_slug}")
            seen.add(scenario.scenario_id)
            seen_slugs.add(scenario.scenario_slug)
            scenarios.append(scenario)
    if not scenarios:
        raise ScenarioCatalogValidationError("scenario catalog is empty")
    known_ids = scenario_ids(scenarios)
    for scenario in scenarios:
        missing_pairs = set(scenario.paired_control_scenario_ids) - known_ids
        if missing_pairs:
            raise ScenarioCatalogValidationError(
                f"{scenario.scenario_id}: unknown paired_control_scenario_ids: {sorted(missing_pairs)}"
            )
    return scenarios


@dataclass(frozen=True)
class ScenarioAlias:
    design_legacy_heading: str
    canonical_scenario_id: str
    scenario_slug: str
    alias_reason: str

    @classmethod
    def from_row(cls, row: dict[str, Any], *, line_number: int) -> "ScenarioAlias":
        missing = {"design_legacy_heading", "canonical_scenario_id", "scenario_slug", "alias_reason"} - set(row)
        if missing:
            raise ScenarioCatalogValidationError(f"line {line_number}: missing alias fields: {sorted(missing)}")
        alias = cls(
            design_legacy_heading=_expect_str(row, "design_legacy_heading", line_number),
            canonical_scenario_id=_expect_str(row, "canonical_scenario_id", line_number),
            scenario_slug=_expect_str(row, "scenario_slug", line_number),
            alias_reason=_expect_str(row, "alias_reason", line_number),
        )
        if not _SCENARIO_ID.fullmatch(alias.canonical_scenario_id):
            raise ScenarioCatalogValidationError(
                f"line {line_number}: invalid canonical_scenario_id: {alias.canonical_scenario_id}"
            )
        if not _SCENARIO_SLUG.fullmatch(alias.scenario_slug):
            raise ScenarioCatalogValidationError(f"line {line_number}: invalid scenario_slug: {alias.scenario_slug}")
        return alias


def load_scenario_aliases(
    path: Path | str = SCENARIO_ALIASES_PATH,
    *,
    scenarios: list[ScenarioDefinition] | None = None,
) -> list[ScenarioAlias]:
    resolved = Path(path)
    aliases: list[ScenarioAlias] = []
    seen_headings: set[str] = set()
    with resolved.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ScenarioCatalogValidationError(f"line {line_number}: invalid JSON: {exc.msg}") from exc
            if not isinstance(row, dict):
                raise ScenarioCatalogValidationError(f"line {line_number}: expected alias object row")
            alias = ScenarioAlias.from_row(row, line_number=line_number)
            if alias.design_legacy_heading in seen_headings:
                raise ScenarioCatalogValidationError(f"duplicate design_legacy_heading: {alias.design_legacy_heading}")
            seen_headings.add(alias.design_legacy_heading)
            aliases.append(alias)
    if not aliases:
        raise ScenarioCatalogValidationError("scenario alias map is empty")
    catalog = scenarios if scenarios is not None else load_scenario_catalog(SCENARIO_CATALOG_PATH)
    slugs_by_id = {scenario.scenario_id: scenario.scenario_slug for scenario in catalog}
    for alias in aliases:
        if alias.canonical_scenario_id not in slugs_by_id:
            raise ScenarioCatalogValidationError(
                f"{alias.design_legacy_heading}: unknown canonical_scenario_id: {alias.canonical_scenario_id}"
            )
        if slugs_by_id[alias.canonical_scenario_id] != alias.scenario_slug:
            raise ScenarioCatalogValidationError(
                f"{alias.design_legacy_heading}: scenario_slug does not match catalog row"
            )
    return aliases


def scenario_ids(scenarios: list[ScenarioDefinition]) -> set[str]:
    return {scenario.scenario_id for scenario in scenarios}


def scenario_by_id(path: Path | str, scenario_id: str) -> ScenarioDefinition:
    for scenario in load_scenario_catalog(path):
        if scenario.scenario_id == scenario_id:
            return scenario
    raise ScenarioCatalogValidationError(f"unknown scenario_id: {scenario_id}")


def _required_fields() -> set[str]:
    return {
        "scenario_id",
        "scenario_slug",
        "name",
        "family",
        "canonical_status",
        "path_types_supported",
        "variation_axes_supported",
        "minimum_prompt_families",
        "paired_control_scenario_ids",
        "verification_requirements",
        "allowed_object_types",
        "allowed_surfaces",
        "blocked_condition",
        "positive_condition",
        "post_run_verification",
        "public_claim_boundary",
        "reset_requirements",
        "known_limitations",
    }


def _validate_scenario(scenario: ScenarioDefinition, *, line_number: int) -> None:
    prefix = f"line {line_number}: "
    if not _SCENARIO_ID.fullmatch(scenario.scenario_id):
        raise ScenarioCatalogValidationError(f"{prefix}invalid scenario_id: {scenario.scenario_id}")
    if not _SCENARIO_SLUG.fullmatch(scenario.scenario_slug):
        raise ScenarioCatalogValidationError(f"{prefix}invalid scenario_slug: {scenario.scenario_slug}")
    if scenario.canonical_status not in _ALLOWED_STATUSES:
        raise ScenarioCatalogValidationError(f"{prefix}unknown canonical_status: {scenario.canonical_status}")
    if scenario.minimum_prompt_families < 1:
        raise ScenarioCatalogValidationError(f"{prefix}minimum_prompt_families must be >= 1")


def _expect_str(row: dict[str, Any], key: str, line_number: int) -> str:
    value = row[key]
    if not isinstance(value, str) or not value.strip():
        raise ScenarioCatalogValidationError(f"line {line_number}: {key} must be a non-empty string")
    return value


def _expect_int(row: dict[str, Any], key: str, line_number: int) -> int:
    value = row[key]
    if not isinstance(value, int):
        raise ScenarioCatalogValidationError(f"line {line_number}: {key} must be an integer")
    return value


def _expect_str_list(row: dict[str, Any], key: str, line_number: int) -> list[str]:
    value = row[key]
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
        raise ScenarioCatalogValidationError(f"line {line_number}: {key} must be a non-empty string list")
    return value


def _expect_optional_str_list(row: dict[str, Any], key: str, line_number: int) -> list[str]:
    value = row[key]
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ScenarioCatalogValidationError(f"line {line_number}: {key} must be a string list")
    return value
