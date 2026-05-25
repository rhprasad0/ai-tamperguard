"""Decision validation and v1 safety-policy normalization."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from openclaw_ai_soc.redaction import redact_payload
from openclaw_ai_soc.state import AnalysisRecord, SummaryRecord

AllowedClassification = Literal[
    "benign",
    "suspicious",
    "malicious",
    "inconclusive",
    "telemetry_failure",
    "policy_violation",
]
AllowedConfidence = Literal["low", "medium", "high"]
AllowedRecommendedAction = Literal[
    "no_action",
    "monitor",
    "investigate",
    "escalate",
    "contain",
    "remediate",
]

ALLOWED_CLASSIFICATIONS = {
    "benign",
    "suspicious",
    "malicious",
    "inconclusive",
    "telemetry_failure",
    "policy_violation",
}
ALLOWED_CONFIDENCE_VALUES = {"low", "medium", "high"}
ALLOWED_RECOMMENDED_ACTIONS = {
    "no_action",
    "monitor",
    "investigate",
    "escalate",
    "contain",
    "remediate",
}

_FORCE_REVIEW_CLASSIFICATIONS = {"malicious", "telemetry_failure", "policy_violation"}
_OPERATOR_ONLY_ACTIONS = {"contain", "remediate"}
_SAFE_SUMMARY_SHORT = "Potentially unsafe model summary withheld."
_SAFE_SUMMARY_DETAILS = (
    "The model summary echoed untrusted evidence that matched prompt-injection, "
    "telemetry-evasion, secret-disclosure, or remediation-execution language. "
    "Review the validated classification, confidence, evidence anchors, and "
    "advisory-only recommendations instead."
)


class FlexibleRecommendedAction(BaseModel):
    """Model action shape before v1 execution flags are forced off."""

    model_config = ConfigDict(extra="forbid")

    action: AllowedRecommendedAction
    priority: str
    reason: str
    execution_allowed: bool = False


class FlexibleRemediationPlan(BaseModel):
    """Model remediation plan shape before v1 execution fields are disabled."""

    model_config = ConfigDict(extra="forbid")

    generated: bool = False
    execution_enabled: bool = False
    requires_human_approval: bool = True
    steps: list[str] = Field(default_factory=list)
    executed: bool = False


class FlexibleDecision(BaseModel):
    """Strict decision schema before policy normalization."""

    model_config = ConfigDict(extra="forbid")

    analysis: AnalysisRecord
    classification: AllowedClassification
    confidence: AllowedConfidence
    recommended_actions: list[FlexibleRecommendedAction] = Field(default_factory=list)
    remediation_plan: FlexibleRemediationPlan = Field(
        default_factory=FlexibleRemediationPlan
    )
    human_review_required: bool = True
    prompt_injection_detected: bool = False
    telemetry_evasion_detected: bool = False
    summary: SummaryRecord

    @model_validator(mode="after")
    def reject_impossible_combinations(self) -> FlexibleDecision:
        action_values = {action.action for action in self.recommended_actions}
        if self.classification == "inconclusive" and action_values.intersection(
            _OPERATOR_ONLY_ACTIONS
        ):
            raise ValueError(
                "inconclusive decisions cannot recommend contain/remediate"
            )
        return self


class ValidatedRecommendedAction(BaseModel):
    """Advisory-only action after v1 policy normalization."""

    model_config = ConfigDict(extra="forbid")

    action: AllowedRecommendedAction
    priority: str
    reason: str
    execution_allowed: Literal[False] = False


class ValidatedRemediationPlan(BaseModel):
    """Disabled remediation plan after v1 policy normalization."""

    model_config = ConfigDict(extra="forbid")

    generated: bool = False
    execution_enabled: Literal[False] = False
    requires_human_approval: Literal[True] = True
    steps: list[str] = Field(default_factory=list)
    executed: Literal[False] = False


class ValidatedDecision(BaseModel):
    """Decision result safe to merge into LangGraph state."""

    model_config = ConfigDict(extra="forbid")

    analysis: AnalysisRecord
    classification: AllowedClassification
    confidence: AllowedConfidence
    recommended_actions: list[ValidatedRecommendedAction] = Field(default_factory=list)
    remediation_plan: ValidatedRemediationPlan = Field(
        default_factory=ValidatedRemediationPlan
    )
    human_review_required: bool = True
    prompt_injection_detected: bool = False
    telemetry_evasion_detected: bool = False
    summary: SummaryRecord
    policy_corrections: list[dict[str, str]] = Field(default_factory=list)


def validate_decision(
    decision: dict[str, Any] | BaseModel,
    *,
    evidence: list[dict[str, Any]] | None = None,
) -> ValidatedDecision:
    """Validate model output, then force v1 fail-closed safety policy.

    Evidence is inspected only through the pure redaction detector. Model-reported
    injection/evasion booleans are advisory and are never trusted without
    corroborating evidence or unsafe summary echo.
    """

    raw_decision = (
        decision.model_dump() if isinstance(decision, BaseModel) else dict(decision)
    )
    parsed = FlexibleDecision.model_validate(raw_decision)
    evidence_items = evidence or []
    evidence_redaction = redact_payload(evidence_items).summary
    summary_redaction = redact_payload(parsed.summary.model_dump()).summary
    corrections: list[dict[str, str]] = []

    normalized_actions: list[ValidatedRecommendedAction] = []
    contains_operator_only_action = False
    for action in parsed.recommended_actions:
        if action.action in _OPERATOR_ONLY_ACTIONS:
            contains_operator_only_action = True
        if action.execution_allowed:
            _append_correction(
                corrections, "action_execution_disabled", "recommended_actions"
            )
        normalized_actions.append(
            ValidatedRecommendedAction(
                action=action.action,
                priority=action.priority,
                reason=action.reason,
                execution_allowed=False,
            )
        )

    telemetry_evasion_detected = evidence_redaction.telemetry_evasion_detected
    if telemetry_evasion_detected and not parsed.telemetry_evasion_detected:
        _append_correction(
            corrections, "telemetry_evasion_corroborated_from_evidence", "evidence"
        )

    normalized_classification = parsed.classification
    under_escalated_telemetry_evasion = normalized_classification in {
        "benign",
        "inconclusive",
    }
    if telemetry_evasion_detected and under_escalated_telemetry_evasion:
        normalized_classification = "suspicious"
        _append_correction(
            corrections,
            "classification_forced_by_telemetry_evasion",
            "classification",
        )

    force_review = parsed.human_review_required
    if normalized_classification in _FORCE_REVIEW_CLASSIFICATIONS:
        if not force_review:
            _append_correction(
                corrections,
                "human_review_forced_by_classification",
                "human_review_required",
            )
        force_review = True
    if telemetry_evasion_detected:
        if not force_review:
            _append_correction(
                corrections,
                "human_review_forced_by_telemetry_evasion",
                "human_review_required",
            )
        force_review = True
    if normalized_classification == "suspicious" and parsed.confidence == "low":
        if not force_review:
            _append_correction(
                corrections,
                "human_review_forced_by_low_confidence_suspicious",
                "human_review_required",
            )
        force_review = True
    if contains_operator_only_action:
        if not force_review:
            _append_correction(
                corrections,
                "human_review_forced_by_operator_only_action",
                "human_review_required",
            )
        force_review = True

    remediation_plan = parsed.remediation_plan
    if remediation_plan.execution_enabled:
        _append_correction(
            corrections, "remediation_execution_disabled", "remediation_plan"
        )
    if remediation_plan.executed:
        _append_correction(
            corrections, "remediation_executed_reset", "remediation_plan"
        )
    if not remediation_plan.requires_human_approval:
        _append_correction(
            corrections, "remediation_human_approval_forced", "remediation_plan"
        )
    disabled_plan = ValidatedRemediationPlan(
        generated=remediation_plan.generated,
        execution_enabled=False,
        requires_human_approval=True,
        steps=remediation_plan.steps,
        executed=False,
    )

    prompt_injection_detected = evidence_redaction.prompt_injection_detected
    unsafe_summary_echo = (
        summary_redaction.prompt_injection_detected
        or summary_redaction.telemetry_evasion_detected
    )
    if parsed.prompt_injection_detected and not prompt_injection_detected:
        _append_correction(
            corrections, "model_prompt_injection_self_report_ignored", "evidence"
        )
    if unsafe_summary_echo:
        prompt_injection_detected = True
        _append_correction(corrections, "unsafe_summary_replaced", "summary")
        summary = SummaryRecord(
            short=_SAFE_SUMMARY_SHORT, details=_SAFE_SUMMARY_DETAILS
        )
    else:
        summary = parsed.summary

    return ValidatedDecision(
        analysis=parsed.analysis,
        classification=normalized_classification,
        confidence=parsed.confidence,
        recommended_actions=normalized_actions,
        remediation_plan=disabled_plan,
        human_review_required=force_review,
        prompt_injection_detected=prompt_injection_detected,
        telemetry_evasion_detected=telemetry_evasion_detected,
        summary=summary,
        policy_corrections=corrections,
    )


def _append_correction(
    corrections: list[dict[str, str]], code: str, field: str
) -> None:
    correction = {"code": code, "field": field}
    if correction not in corrections:
        corrections.append(correction)
