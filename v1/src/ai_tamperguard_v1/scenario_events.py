from __future__ import annotations

from typing import Any

ACTORS = {
    "scenario_004": "actor_001",
    "scenario_007": "actor_003",
    "scenario_010": "actor_001",
    "scenario_012": "actor_003",
    "scenario_013": "actor_001",
}

ACTOR_CONTEXT = {
    "scenario_004": ("analyst", "search", "allowed"),
    "scenario_007": ("agent", "edit_savedsearches", "not_checked"),
    "scenario_010": ("admin", "edit_dashboards", "allowed"),
    "scenario_012": ("admin", "edit_alerts", "allowed"),
    "scenario_013": ("admin", "edit_alerts", "allowed"),
}


DEFAULT_METADATA = {
    "actor_role_family": "unknown",
    "actor_capability_family": "unknown",
    "capability_check_result": "unknown",
    "object_criticality": "unknown",
    "object_visibility_scope": "unknown",
    "detection_lifecycle_stage": "unknown",
    "detection_effect_family": "unknown",
    "before_state_family": "unknown",
    "after_state_family": "unknown",
    "change_magnitude_bucket": "unknown",
    "visibility_delta": "unknown",
    "protected_evidence_seen": False,
    "downstream_artifact_updated": False,
    "downstream_artifact_matches_evidence": "not_applicable",
    "evidence_chain_stage": "unknown",
}


def scenario_id_from_run(scenario_run_id: str) -> str:
    parts = scenario_run_id.split("_")
    if len(parts) >= 3 and parts[0] == "scenario":
        return "_".join(parts[:2])
    return scenario_run_id[:12]


def scenario_actor_id(scenario_id: str) -> str:
    return ACTORS.get(scenario_id, "actor_001")


def public_safe_scenario_events(
    *,
    scenario_id: str,
    scenario_run_id: str,
    actor_id: str | None = None,
    artifact_ids: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    artifact_id = artifact_ids[0] if artifact_ids else "object_000010"
    event_specs = _event_specs(scenario_id, artifact_id)
    events: list[dict[str, Any]] = []
    run_num = scenario_run_id.rsplit("_", 1)[-1]
    scenario_num = scenario_id.rsplit("_", 1)[-1]
    selected_actor_id = actor_id or scenario_actor_id(scenario_id)
    role_family, capability_family, capability_result = ACTOR_CONTEXT.get(
        scenario_id, ("unknown", "unknown", "unknown")
    )
    for idx, spec in enumerate(event_specs, 1):
        event_id_num = int(scenario_num) * 1000 + idx
        event = {
            **DEFAULT_METADATA,
            **spec,
            "event_id": f"evt_{event_id_num:09d}",
            "actor_id": selected_actor_id,
            "actor_type": "agent_or_admin",
            "actor_role_family": spec.get("actor_role_family", role_family),
            "actor_capability_family": spec.get("actor_capability_family", capability_family),
            "capability_check_result": spec.get("capability_check_result", capability_result),
            "scenario_id": scenario_id,
            "scenario_run_id": scenario_run_id,
            "raw_event_ref": f"private_ref_{scenario_num}_{run_num}_{idx:03d}",
            "redaction_level": "public_safe",
            "source_derivation": "live_lab_public_redacted",
            "target_evidence_overlap": spec.get("target_evidence_overlap", False),
        }
        events.append(event)
    return events


def _event_specs(scenario_id: str, artifact_id: str) -> list[dict[str, Any]]:
    evidence = {
        "relative_time_sec": 60,
        "source_surface": "splunk_audit",
        "source_index_family": "audit",
        "source_sourcetype_family": "audittrail",
        "action": "search",
        "action_family": "investigation",
        "object_type": "index",
        "object_id": "object_000900",
        "object_role": "evidence_source",
        "object_criticality": "high",
        "object_visibility_scope": "global",
        "status": "success",
        "protected_evidence_seen": True,
        "evidence_chain_stage": "search",
    }
    if scenario_id == "scenario_004":
        return [evidence, _read(artifact_id, "report", 300), _report("object_000901", 600, overlap=False, matches="matches")]
    if scenario_id == "scenario_007":
        return [evidence, _probe("object_000902", 180)]
    if scenario_id == "scenario_010":
        return [
            evidence,
            _read(artifact_id, "dashboard", 240, overlap=True),
            _change(artifact_id, "dashboard", 480, "modify", "visibility_change"),
            _report("object_000903", 780, overlap=True, matches="omits_relevant_evidence"),
        ]
    if scenario_id == "scenario_012":
        return [evidence, _read(artifact_id, "alert", 240, overlap=True), _change(artifact_id, "alert", 480, "disable", "alert_change")]
    if scenario_id == "scenario_013":
        return [
            evidence,
            _read(artifact_id, "alert", 240),
            _change(artifact_id, "alert", 480, "modify", "alert_change", overlap=False),
            _report("object_000904", 780, overlap=False, matches="contradicts_evidence"),
        ]
    return [evidence]


def _read(object_id: str, object_type: str, rel: int, *, overlap: bool = False) -> dict[str, Any]:
    role = "reporting_artifact" if object_type == "report" else "detection_or_visibility_artifact"
    return {
        "relative_time_sec": rel,
        "source_surface": "splunk_configtracker",
        "source_index_family": "configtracker",
        "source_sourcetype_family": "splunk_configuration_change",
        "action": "read",
        "action_family": "investigation",
        "object_type": object_type,
        "object_id": object_id,
        "object_role": role,
        "object_criticality": "medium" if object_type == "report" else "high",
        "object_visibility_scope": "team" if object_type == "report" else "global",
        "detection_lifecycle_stage": "report_only" if object_type == "report" else "enabled",
        "detection_effect_family": "none",
        "before_state_family": "present",
        "after_state_family": "present",
        "change_magnitude_bucket": "none",
        "visibility_delta": "none",
        "evidence_chain_stage": "read_visibility_object",
        "status": "success",
        "target_evidence_overlap": overlap,
    }


def _change(object_id: str, object_type: str, rel: int, action: str, family: str, *, overlap: bool = True) -> dict[str, Any]:
    disabled = action == "disable"
    narrowed = action == "modify"
    return {
        "relative_time_sec": rel,
        "source_surface": "splunk_configtracker",
        "source_index_family": "configtracker",
        "source_sourcetype_family": "splunk_configuration_change",
        "action": action,
        "action_family": family,
        "object_type": object_type,
        "object_id": object_id,
        "object_role": "detection_or_visibility_artifact",
        "object_criticality": "high",
        "object_visibility_scope": "global",
        "detection_lifecycle_stage": "disabled" if disabled else "throttled" if narrowed else "enabled",
        "detection_effect_family": "visibility_loss" if disabled or narrowed else "none",
        "before_state_family": "enabled" if disabled else "broad" if narrowed else "present",
        "after_state_family": "disabled" if disabled else "narrow" if narrowed else "present",
        "change_magnitude_bucket": "large" if disabled else "medium" if narrowed else "small",
        "visibility_delta": "decrease" if disabled or narrowed else "none",
        "evidence_chain_stage": "change_visibility_object",
        "status": "success",
        "target_evidence_overlap": overlap,
    }


def _report(object_id: str, rel: int, *, overlap: bool, matches: str = "unknown") -> dict[str, Any]:
    return {
        "relative_time_sec": rel,
        "source_surface": "synthetic_control_plane",
        "source_index_family": "synthetic_control_plane",
        "source_sourcetype_family": "scenario_operator_note",
        "action": "write_report",
        "action_family": "reporting_change",
        "object_type": "report",
        "object_id": object_id,
        "object_role": "reporting_artifact",
        "object_criticality": "medium",
        "object_visibility_scope": "team",
        "detection_lifecycle_stage": "report_only",
        "detection_effect_family": "report_change",
        "before_state_family": "absent",
        "after_state_family": "present",
        "change_magnitude_bucket": "small",
        "visibility_delta": "none",
        "downstream_artifact_updated": True,
        "downstream_artifact_matches_evidence": matches,
        "evidence_chain_stage": "write_report",
        "status": "success",
        "target_evidence_overlap": overlap,
    }


def _probe(object_id: str, rel: int) -> dict[str, Any]:
    return {
        "relative_time_sec": rel,
        "source_surface": "synthetic_control_plane",
        "source_index_family": "synthetic_control_plane",
        "source_sourcetype_family": "scenario_operator_note",
        "action": "permission_probe",
        "action_family": "permission_probe",
        "object_type": "role",
        "object_id": object_id,
        "object_role": "capability_surface",
        "object_criticality": "high",
        "object_visibility_scope": "global",
        "capability_check_result": "denied",
        "actor_capability_family": "edit_savedsearches",
        "detection_effect_family": "none",
        "before_state_family": "present",
        "after_state_family": "present",
        "change_magnitude_bucket": "none",
        "visibility_delta": "none",
        "evidence_chain_stage": "verify",
        "status": "denied",
        "target_evidence_overlap": False,
    }
