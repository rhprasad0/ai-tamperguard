"""Typed incident state and Pydantic boundary schemas."""

from typing import Any, Literal, NotRequired, TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from openclaw_ai_soc.config import V1_ALLOWED_OPENAI_BASE_URLS, V1_MODEL

TriggerType = Literal["manual_hermes"]
IncidentMode = Literal["synthetic", "real_home_telemetry", "private_test"]
EvidenceQuality = Literal["none", "partial", "sufficient", "conflicting"]
NotificationStatus = Literal["not_configured", "sent", "failed", "skipped"]
MemoryWriteStatus = Literal["not_attempted", "written", "failed", "skipped"]
InvestigationStatus = Literal["queued", "running", "completed", "failed", "skipped"]
Confidence = Literal["low", "medium", "high"]


class StrictBoundaryModel(BaseModel):
    """Base class for external payloads: typed, explicit, and no surprise keys."""

    model_config = ConfigDict(extra="forbid")


class TimeWindow(StrictBoundaryModel):
    """Bounded time window for all evidence collection."""

    earliest: str
    latest: str

    @field_validator("earliest", "latest")
    @classmethod
    def require_non_empty_text(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("time window bounds must be non-empty")
        return value

    @model_validator(mode="after")
    def require_bounded_window(self) -> "TimeWindow":
        if self.earliest == "0":
            raise ValueError("earliest=0 is open-ended and is not allowed")

        if self.earliest.startswith("-"):
            hours = _relative_window_hours(self.earliest)
            if hours is None:
                raise ValueError("earliest must be a bounded relative duration")
            if hours <= 0 or hours > 24:
                raise ValueError("time_window must be greater than 0 and at most 24h")

        return self


class SourceAlert(StrictBoundaryModel):
    """Alert-like input from the manual Hermes trigger boundary."""

    alert_type: str
    source: str
    description: str
    raw: dict[str, Any] = Field(default_factory=dict)


class ManualHermesTrigger(StrictBoundaryModel):
    """Manual v1 trigger payload accepted from Hermes."""

    trigger_type: TriggerType
    operator: str
    incident_mode: IncidentMode
    source_alert: SourceAlert
    time_window: TimeWindow


class SplunkQueryRecord(StrictBoundaryModel):
    """Metadata for one curated Splunk template execution."""

    template_id: str
    search_id: str | None = None
    earliest: str
    latest: str
    max_results: int | None = None
    result_count: int = 0
    status: str
    query_hash: str | None = None


class EvidenceRecord(StrictBoundaryModel):
    """Compact redacted evidence summary, never a raw event dump."""

    kind: str
    summary: str
    template_id: str | None = None
    selected_fields: list[dict[str, Any]] = Field(default_factory=list)
    redactions: list[str] = Field(default_factory=list)
    untrusted_evidence_locations: list[str] = Field(default_factory=list)


class MemoryMatch(StrictBoundaryModel):
    """Graphiti precedent summary, not raw memory content."""

    case_id: str
    classification: str | None = None
    summary: str
    relevance: str


class AnalysisRecord(StrictBoundaryModel):
    """Validated model analysis shape."""

    key_findings: list[str] = Field(default_factory=list)
    alternative_explanations: list[str] = Field(default_factory=list)


class RecommendedAction(StrictBoundaryModel):
    """Non-executed action recommendation."""

    action: str
    priority: str
    reason: str
    execution_allowed: Literal[False] = False


class RemediationPlan(StrictBoundaryModel):
    """Disabled remediation plan stub for v1."""

    generated: bool = False
    execution_enabled: Literal[False] = False
    requires_human_approval: Literal[True] = True
    steps: list[str] = Field(default_factory=list)
    executed: Literal[False] = False


class SummaryRecord(StrictBoundaryModel):
    """Hermes-ready summary payload."""

    short: str
    details: str


class ErrorRecord(StrictBoundaryModel):
    """Structured non-secret error details."""

    code: str
    message: str
    component: str | None = None


class IncidentState(StrictBoundaryModel):
    """Pydantic state model for boundary validation and default fail-closed values."""

    incident_id: str
    trigger_type: TriggerType
    incident_mode: IncidentMode
    source_alert: SourceAlert
    alert_time: str | None = None
    received_at: str
    time_window: TimeWindow
    entities: dict[str, Any] = Field(default_factory=dict)
    severity: str | None = None
    risk_score: float | None = None
    selected_playbooks: list[str] = Field(default_factory=list)
    splunk_queries_run: list[SplunkQueryRecord] = Field(default_factory=list)
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    evidence_quality: EvidenceQuality = "none"
    memory_matches: list[MemoryMatch] = Field(default_factory=list)
    analysis: AnalysisRecord | None = None
    classification: str | None = None
    confidence: Confidence | None = None
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    remediation_plan: RemediationPlan = Field(default_factory=RemediationPlan)
    human_review_required: bool = True
    prompt_injection_detected: bool = False
    telemetry_evasion_detected: bool = False
    summary: SummaryRecord | None = None
    notification_status: NotificationStatus = "not_configured"
    memory_write_status: MemoryWriteStatus = "not_attempted"
    investigation_status: InvestigationStatus = "queued"
    trace_ids: dict[str, Any] = Field(default_factory=dict)
    model_endpoint: str
    model_name: str
    errors: list[ErrorRecord] = Field(default_factory=list)

    @field_validator("model_endpoint")
    @classmethod
    def require_v1_bridge_url(cls, value: str) -> str:
        if value not in V1_ALLOWED_OPENAI_BASE_URLS:
            raise ValueError(
                "model_endpoint must equal an allowed LAN Codex bridge endpoint"
            )
        return value

    @field_validator("model_name")
    @classmethod
    def require_v1_model(cls, value: str) -> str:
        if value != V1_MODEL:
            raise ValueError(f"model_name must equal {V1_MODEL}")
        return value


class OpenclawState(TypedDict, total=False):
    """LangGraph-compatible typed state dictionary."""

    incident_id: str
    trigger_type: TriggerType
    incident_mode: IncidentMode
    source_alert: dict[str, Any]
    alert_time: NotRequired[str | None]
    received_at: str
    time_window: dict[str, str]
    entities: dict[str, Any]
    severity: NotRequired[str | None]
    risk_score: NotRequired[float | None]
    selected_playbooks: list[str]
    splunk_queries_run: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    evidence_quality: EvidenceQuality
    memory_matches: list[dict[str, Any]]
    analysis: NotRequired[dict[str, Any] | None]
    classification: NotRequired[str | None]
    confidence: NotRequired[Confidence | None]
    recommended_actions: list[dict[str, Any]]
    remediation_plan: dict[str, Any]
    human_review_required: bool
    prompt_injection_detected: bool
    telemetry_evasion_detected: bool
    summary: NotRequired[dict[str, Any] | None]
    notification_status: NotificationStatus
    memory_write_status: MemoryWriteStatus
    investigation_status: InvestigationStatus
    trace_ids: dict[str, Any]
    model_endpoint: str
    model_name: str
    errors: list[dict[str, Any]]


def _relative_window_hours(value: str) -> float | None:
    unit = value[-1:]
    amount = value[1:-1]
    if unit not in {"m", "h"} or not amount.isdigit():
        return None

    numeric_amount = int(amount)
    if unit == "m":
        return numeric_amount / 60
    return float(numeric_amount)
