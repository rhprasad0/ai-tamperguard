from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REQUIRED_INDEXES = ("_audit", "_configtracker", "openclaw_tamper_lab")
OPTIONAL_INDEXES = ("agentops",)
_REQUIRED_CONFIG_KEYS = ("authorized_lab_marker", "target_namespace", "capture_destination")
_ENV_VAR_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_SAFE_LITERAL_RE = re.compile(r"^[A-Za-z0-9:_-]+$")


class LabConfigError(ValueError):
    """Raised when private lab configuration is missing or unsafe."""


@dataclass(frozen=True)
class SplunkHecConfig:
    url: str
    token_env: str = "AI_TAMPERGUARD_SPLUNK_HEC_TOKEN"
    index: str = "openclaw_tamper_lab"
    sourcetype: str = "ai_tamperguard:v1:scenario_evidence"
    source: str = "ai_tamperguard:v1:seed"


@dataclass(frozen=True)
class SplunkSearchConfig:
    url: str
    token_env: str


@dataclass(frozen=True)
class LabConfig:
    path: Path
    authorized_lab_marker: str
    target_namespace: str
    capture_destination: Path
    allowed_indexes: tuple[str, ...]
    protected_indexes: tuple[str, ...]
    synthetic_evidence_index: str
    public_sample_policy: str
    sacrificial_allowed_app: str
    sacrificial_object_id_prefixes: tuple[str, ...]
    sacrificial_object_types: tuple[str, ...]
    splunk_hec: SplunkHecConfig | None = None
    splunk_search: SplunkSearchConfig | None = None

    @property
    def required_indexes(self) -> tuple[str, ...]:
        return REQUIRED_INDEXES

    @property
    def optional_indexes(self) -> tuple[str, ...]:
        return OPTIONAL_INDEXES


@dataclass(frozen=True)
class SacrificialArtifact:
    object_id: str
    private_name: str
    object_type: str
    scenario_ids: tuple[str, ...]


@dataclass(frozen=True)
class SacrificialInventory:
    path: Path
    namespace: str
    synthetic_index: str
    artifacts: tuple[SacrificialArtifact, ...]


def load_lab_config(path: Path | str) -> LabConfig:
    cfg_path = Path(path)
    _require_private_path(cfg_path)
    if not cfg_path.exists():
        raise LabConfigError(f"missing private lab config: {cfg_path}")

    data = _read_toml(cfg_path)
    errors: list[str] = []
    for key in _REQUIRED_CONFIG_KEYS:
        if key not in data:
            errors.append(f"missing required key: {key}")

    capture_destination = Path(str(data.get("capture_destination", "")))
    if capture_destination.as_posix() != "data/private/raw_exports":
        errors.append("capture_destination must be data/private/raw_exports")

    allowed_indexes = _as_str_tuple(data.get("allowed_indexes", ()))
    missing_indexes = [index for index in REQUIRED_INDEXES if index not in allowed_indexes]
    if missing_indexes:
        errors.append("allowed_indexes missing mandatory indexes: " + ", ".join(missing_indexes))

    protected_indexes = _as_str_tuple(data.get("protected_indexes", ("_audit", "_configtracker")))
    missing_protected = [index for index in ("_audit", "_configtracker") if index not in protected_indexes]
    if missing_protected:
        errors.append("protected_indexes missing: " + ", ".join(missing_protected))

    synthetic_evidence_index = str(data.get("synthetic_evidence_index", "openclaw_tamper_lab"))
    if synthetic_evidence_index != "openclaw_tamper_lab":
        errors.append("synthetic_evidence_index must be openclaw_tamper_lab for V1")

    target_namespace = str(data.get("target_namespace", ""))
    sacrificial = data.get("sacrificial", {})
    if not isinstance(sacrificial, dict):
        errors.append("[sacrificial] must be a TOML table")
        sacrificial = {}
    sacrificial_allowed_app = str(sacrificial.get("allowed_app", target_namespace))
    if target_namespace and sacrificial_allowed_app != target_namespace:
        errors.append("sacrificial.allowed_app must match target_namespace")

    object_types = _as_str_tuple(sacrificial.get("allowed_object_types", ()))
    if not object_types:
        errors.append("sacrificial.allowed_object_types must not be empty")

    splunk_hec = _parse_splunk_hec(data.get("splunk_hec"), errors)
    splunk_search = _parse_splunk_search(data.get("splunk_search"), errors)

    if errors:
        raise LabConfigError("; ".join(errors))

    return LabConfig(
        path=cfg_path,
        authorized_lab_marker=str(data["authorized_lab_marker"]),
        target_namespace=target_namespace,
        capture_destination=capture_destination,
        allowed_indexes=allowed_indexes,
        protected_indexes=protected_indexes,
        synthetic_evidence_index=synthetic_evidence_index,
        public_sample_policy=str(data.get("public_sample_policy", "live_run_required")),
        sacrificial_allowed_app=sacrificial_allowed_app,
        sacrificial_object_id_prefixes=_as_str_tuple(sacrificial.get("allowed_object_id_prefixes", ())),
        sacrificial_object_types=object_types,
        splunk_hec=splunk_hec,
        splunk_search=splunk_search,
    )


def load_sacrificial_inventory(path: Path | str, *, expected_namespace: str) -> SacrificialInventory:
    inventory_path = Path(path)
    _require_private_path(inventory_path)
    if not inventory_path.exists():
        raise LabConfigError(f"missing private sacrificial inventory: {inventory_path}")

    data = _read_toml(inventory_path)
    namespace = str(data.get("namespace", ""))
    synthetic_index = str(data.get("synthetic_index", ""))
    errors: list[str] = []
    if namespace != expected_namespace:
        errors.append(f"inventory namespace must match {expected_namespace}")
    if synthetic_index != "openclaw_tamper_lab":
        errors.append("inventory synthetic_index must be openclaw_tamper_lab")

    raw_artifacts = data.get("artifacts", [])
    if not isinstance(raw_artifacts, list) or not raw_artifacts:
        errors.append("inventory must include at least one [[artifacts]] entry")
        raw_artifacts = []

    artifacts: list[SacrificialArtifact] = []
    for idx, raw in enumerate(raw_artifacts, 1):
        if not isinstance(raw, dict):
            errors.append(f"artifact {idx} must be a TOML table")
            continue
        object_id = str(raw.get("object_id", ""))
        private_name = str(raw.get("private_name", ""))
        object_type = str(raw.get("object_type", ""))
        scenario_ids = _as_str_tuple(raw.get("scenario_ids", ()))
        if not object_id.startswith("object_"):
            errors.append(f"artifact {idx} object_id must use public-safe object_ prefix")
        if not private_name:
            errors.append(f"artifact {idx} private_name is required for private reset lookup")
        if not object_type:
            errors.append(f"artifact {idx} object_type is required")
        if not scenario_ids:
            errors.append(f"artifact {idx} scenario_ids must not be empty")
        artifacts.append(
            SacrificialArtifact(
                object_id=object_id,
                private_name=private_name,
                object_type=object_type,
                scenario_ids=scenario_ids,
            )
        )

    if errors:
        raise LabConfigError("; ".join(errors))

    return SacrificialInventory(
        path=inventory_path,
        namespace=namespace,
        synthetic_index=synthetic_index,
        artifacts=tuple(artifacts),
    )


def _require_private_path(path: Path) -> None:
    parts = tuple(part for part in path.as_posix().split("/") if part)
    for idx in range(len(parts) - 1):
        if parts[idx : idx + 2] == ("splunk", "private"):
            return
    raise LabConfigError(f"private lab files must live under splunk/private: {path}")


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            value = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise LabConfigError(f"invalid TOML in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise LabConfigError(f"{path} must parse as a TOML table")
    return value


def _as_str_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list | tuple):
        return ()
    return tuple(str(item) for item in value)


def _parse_splunk_hec(value: Any, errors: list[str]) -> SplunkHecConfig | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        errors.append("[splunk_hec] must be a TOML table")
        return None
    url = str(value.get("url", ""))
    token_env = str(value.get("token_env", "AI_TAMPERGUARD_SPLUNK_HEC_TOKEN"))
    index = str(value.get("index", "openclaw_tamper_lab"))
    sourcetype = str(value.get("sourcetype", "ai_tamperguard:v1:scenario_evidence"))
    source = str(value.get("source", "ai_tamperguard:v1:seed"))
    if not url:
        errors.append("splunk_hec.url is required")
    if not _is_env_var_name(token_env):
        errors.append("splunk_hec.token_env must be an environment variable name")
    if index != "openclaw_tamper_lab":
        errors.append("splunk_hec.index must be openclaw_tamper_lab")
    if not _SAFE_LITERAL_RE.match(sourcetype):
        errors.append("splunk_hec.sourcetype must be a safe literal")
    if not _SAFE_LITERAL_RE.match(source):
        errors.append("splunk_hec.source must be a safe literal")
    return SplunkHecConfig(url=url, token_env=token_env, index=index, sourcetype=sourcetype, source=source)


def _parse_splunk_search(value: Any, errors: list[str]) -> SplunkSearchConfig | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        errors.append("[splunk_search] must be a TOML table")
        return None
    url = str(value.get("url", ""))
    token_env = str(value.get("token_env", ""))
    if not url:
        errors.append("splunk_search.url is required")
    if not _is_env_var_name(token_env):
        errors.append("splunk_search.token_env must be an environment variable name")
    return SplunkSearchConfig(url=url, token_env=token_env)


def _is_env_var_name(value: str) -> bool:
    return bool(_ENV_VAR_RE.match(value))
