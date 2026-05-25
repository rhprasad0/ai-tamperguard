from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Callable

LABEL_POSITIVE_FAMILIES = {
    "evidence_laundering",
    "alert_suppression",
    "report_alibi_generation",
    "input_or_token_tamper",
    "routing_or_transform_tamper",
    "successful_synthetic_tamper",
}

WRITE_ACTIONS = {"modify", "disable", "enable", "create", "delete"}


def label_index(answer_key: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["scenario_run_id"]: row for row in answer_key}


def derive_windows(events: list[dict[str, Any]], answer_key: list[dict[str, Any]], *, size_sec: int) -> list[dict[str, Any]]:
    labels = label_index(answer_key)
    ordered_events = sorted(events, key=lambda e: (e.get("scenario_run_id") or "", int(e.get("relative_time_sec", 0)), e["event_id"]))
    rarity = _rarity_buckets(ordered_events)
    buckets: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for event in ordered_events:
        run_id = event.get("scenario_run_id") or "background"
        actor = event["actor_id"]
        bucket = int(event.get("relative_time_sec", 0)) // size_sec
        buckets[(run_id, actor, bucket)].append(event)
    rows: list[dict[str, Any]] = []
    for index, ((run_id, actor, bucket), bucket_events) in enumerate(sorted(buckets.items()), 1):
        actions = Counter(e["action"] for e in bucket_events)
        objects = Counter(e["object_type"] for e in bucket_events)
        answer = labels.get(run_id, {})
        family = answer.get("label_family", "background_unlabeled")
        label = 1 if family in LABEL_POSITIVE_FAMILIES else 0
        row = {
            "window_id": f"window_{size_sec}_{index:06d}",
            "scenario_run_id": run_id,
            "actor_id": actor,
            "window_start_relative_sec": bucket * size_sec,
            "window_end_relative_sec": (bucket + 1) * size_sec,
            "feature_event_count": len(bucket_events),
            "feature_search_count": actions.get("search", 0),
            "feature_config_change_count": sum(actions.get(a, 0) for a in WRITE_ACTIONS),
            "feature_visibility_object_read_count": _count_events(bucket_events, lambda e: e.get("object_role") == "detection_or_visibility_artifact" and e["action"] in {"read", "search"}),
            "feature_visibility_object_write_count": _count_events(bucket_events, lambda e: e.get("object_role") == "detection_or_visibility_artifact" and e["action"] in WRITE_ACTIONS),
            "feature_saved_search_modify_count": _count_events(bucket_events, lambda e: e["object_type"] == "saved_search" and e["action"] == "modify"),
            "feature_dashboard_modify_count": _count_events(bucket_events, lambda e: e["object_type"] == "dashboard" and e["action"] == "modify"),
            "feature_alert_modify_count": _count_events(bucket_events, lambda e: e["object_type"] == "alert" and e["action"] in {"modify", "disable"}),
            "feature_permission_denied_count": _count_events(bucket_events, lambda e: e["status"] == "denied"),
            "feature_distinct_object_type_count": len(objects),
            "feature_search_then_modify_flag": int(_has_order(bucket_events, {"search"}, {"modify", "disable"})),
            "feature_modify_then_requery_flag": int(_has_order(bucket_events, {"modify", "disable"}, {"search"})),
            "feature_actor_admin_context_flag": int(any(e.get("actor_role_family") == "admin" for e in bucket_events)),
            "feature_capability_denied_count": _count_events(bucket_events, lambda e: e.get("capability_check_result") == "denied" or e.get("status") == "denied"),
            "feature_capability_allowed_change_count": _count_events(bucket_events, lambda e: e.get("capability_check_result") == "allowed" and e.get("action") in WRITE_ACTIONS),
            "feature_permission_probe_before_change_flag": int(_has_order(bucket_events, {"permission_probe"}, WRITE_ACTIONS)),
            "feature_high_criticality_object_touch_count": _count_events(bucket_events, lambda e: e.get("object_criticality") == "high"),
            "feature_high_criticality_object_write_count": _count_events(bucket_events, lambda e: e.get("object_criticality") == "high" and e.get("action") in WRITE_ACTIONS),
            "feature_detection_disable_count": _count_events(bucket_events, lambda e: e.get("detection_lifecycle_stage") == "disabled" or e.get("action") == "disable"),
            "feature_detection_throttle_or_narrow_count": _count_events(bucket_events, lambda e: e.get("detection_lifecycle_stage") == "throttled" or e.get("after_state_family") == "narrow"),
            "feature_global_visibility_object_write_count": _count_events(bucket_events, lambda e: e.get("object_visibility_scope") == "global" and e.get("object_role") == "detection_or_visibility_artifact" and e.get("action") in WRITE_ACTIONS),
            "feature_visibility_decrease_count": _count_events(bucket_events, lambda e: e.get("visibility_delta") == "decrease"),
            "feature_large_change_count": _count_events(bucket_events, lambda e: e.get("change_magnitude_bucket") == "large"),
            "feature_enabled_to_disabled_count": _count_events(bucket_events, lambda e: e.get("before_state_family") == "enabled" and e.get("after_state_family") == "disabled"),
            "feature_broad_to_narrow_count": _count_events(bucket_events, lambda e: e.get("before_state_family") == "broad" and e.get("after_state_family") == "narrow"),
            "feature_state_changed_after_evidence_access_flag": int(_has_stage_order(bucket_events, "search", "change_visibility_object")),
            "feature_protected_evidence_seen_count": _count_events(bucket_events, lambda e: bool(e.get("protected_evidence_seen"))),
            "feature_downstream_omission_count": _count_events(bucket_events, lambda e: e.get("downstream_artifact_matches_evidence") == "omits_relevant_evidence"),
            "feature_downstream_contradiction_count": _count_events(bucket_events, lambda e: e.get("downstream_artifact_matches_evidence") == "contradicts_evidence"),
            "feature_evidence_then_report_omission_flag": int(_has_stage_order(bucket_events, "search", "write_report") and any(e.get("downstream_artifact_matches_evidence") == "omits_relevant_evidence" for e in bucket_events)),
            "feature_evidence_target_overlap_count": _count_events(bucket_events, lambda e: bool(e.get("target_evidence_overlap"))),
            "feature_report_write_count": actions.get("write_report", 0),
            "feature_search_to_change_min_gap_bucket": _min_gap_bucket(bucket_events, {"search"}, WRITE_ACTIONS),
            "feature_change_to_requery_min_gap_bucket": _min_gap_bucket(bucket_events, WRITE_ACTIONS, {"search"}),
            "feature_distinct_surface_count": len({e.get("source_surface", "unknown") for e in bucket_events}),
            "feature_action_switch_count": _action_switch_count(bucket_events),
            "feature_search_modify_report_sequence_flag": int(_has_action_sequence(bucket_events, ["search", "modify", "write_report"])),
            "feature_read_modify_report_sequence_flag": int(_has_action_sequence(bucket_events, ["read", "modify", "write_report"])),
            "feature_probe_denied_then_report_flag": int(_has_denied_probe_then_report(bucket_events)),
            "feature_actor_action_rarity_bucket": rarity["actor_action"].get((actor, _dominant_action(bucket_events)), 0),
            "feature_object_type_actor_rarity_bucket": rarity["object_actor"].get((actor, _dominant_object_type(bucket_events)), 0),
            "feature_high_risk_combo_count": _high_risk_combo_count(bucket_events),
            "label_binary": label,
            "label_family": family,
            "label_source": answer.get("label_source", "background_unlabeled"),
            "split_id": "unassigned",
        }
        rows.append(row)
    return rows


def derive_episodes(events: list[dict[str, Any]], answer_key: list[dict[str, Any]]) -> list[dict[str, Any]]:
    labels = label_index(answer_key)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[(event.get("scenario_run_id") or "background", event["actor_id"])].append(event)
    rows=[]
    for idx, ((run_id, actor), evs) in enumerate(sorted(grouped.items()), 1):
        ordered=sorted(evs, key=lambda e:(int(e.get("relative_time_sec",0)), e["event_id"]))
        answer=labels.get(run_id,{})
        rows.append({
            "episode_id": f"episode_{idx:06d}",
            "scenario_run_id": run_id,
            "actor_id": actor,
            "start_relative_sec": int(ordered[0].get("relative_time_sec",0)),
            "end_relative_sec": int(ordered[-1].get("relative_time_sec",0)),
            "action_sequence": [f"{e['action']}:{e['object_type']}" for e in ordered],
            "object_type_sequence": [e["object_type"] for e in ordered],
            "relative_time_sequence_sec": [int(e.get("relative_time_sec",0)) for e in ordered],
            "label_family": answer.get("label_family", "background_unlabeled"),
            "outcome": answer.get("outcome", "benign"),
            "paired_control_episode_id": None,
        })
    return rows


def derive_edges(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows=[]
    edge_map={"search":"searched", "read":"read", "modify":"modified", "disable":"disabled", "enable":"enabled", "create":"created", "delete":"deleted", "write_report":"wrote", "permission_probe":"probed"}
    for idx,e in enumerate(sorted(events, key=lambda e:(e.get("scenario_run_id") or "", int(e.get("relative_time_sec",0)), e["event_id"])),1):
        rows.append({
            "edge_id": f"edge_{idx:06d}",
            "scenario_run_id": e.get("scenario_run_id"),
            "relative_time_sec": int(e.get("relative_time_sec",0)),
            "src_type": "actor",
            "src_id": e["actor_id"],
            "edge_type": edge_map.get(e["action"], e["action"]),
            "dst_type": e["object_type"],
            "dst_id": e["object_id"],
            "object_role": e.get("object_role", "unknown"),
            "target_evidence_overlap": bool(e.get("target_evidence_overlap", False)),
            "status": e.get("status", "unknown"),
        })
    return rows


def _count_events(events: list[dict[str, Any]], predicate: Callable[[dict[str, Any]], bool]) -> int:
    return sum(1 for event in events if predicate(event))


def _has_order(events: list[dict[str, Any]], first: set[str], second: set[str]) -> bool:
    seen=False
    for e in sorted(events, key=lambda e:int(e.get("relative_time_sec",0))):
        if e["action"] in first:
            seen=True
        if seen and e["action"] in second:
            return True
    return False


def _has_denied_probe_then_report(events: list[dict[str, Any]]) -> bool:
    seen_denied_probe = False
    for event in sorted(events, key=lambda e: int(e.get("relative_time_sec", 0))):
        if event.get("action") == "permission_probe" and (
            event.get("status") == "denied" or event.get("capability_check_result") == "denied"
        ):
            seen_denied_probe = True
        if seen_denied_probe and event.get("action") == "write_report":
            return True
    return False


def _has_stage_order(events: list[dict[str, Any]], first_stage: str, second_stage: str) -> bool:
    seen = False
    for event in sorted(events, key=lambda e: int(e.get("relative_time_sec", 0))):
        if event.get("evidence_chain_stage") == first_stage:
            seen = True
        if seen and event.get("evidence_chain_stage") == second_stage:
            return True
    return False


def _has_action_sequence(events: list[dict[str, Any]], sequence: list[str]) -> bool:
    position = 0
    for event in sorted(events, key=lambda e: int(e.get("relative_time_sec", 0))):
        if position < len(sequence) and event.get("action") == sequence[position]:
            position += 1
    return position == len(sequence)


def _min_gap_bucket(events: list[dict[str, Any]], first_actions: set[str], second_actions: set[str]) -> int:
    ordered = sorted(events, key=lambda e: int(e.get("relative_time_sec", 0)))
    first_times = [int(e.get("relative_time_sec", 0)) for e in ordered if e.get("action") in first_actions]
    if not first_times:
        return 0
    gaps: list[int] = []
    for event in ordered:
        if event.get("action") not in second_actions:
            continue
        second_time = int(event.get("relative_time_sec", 0))
        prior = [first_time for first_time in first_times if first_time <= second_time]
        if prior:
            gaps.append(second_time - max(prior))
    if not gaps:
        return 0
    gap = min(gaps)
    if gap <= 300:
        return 1
    if gap <= 1800:
        return 2
    return 3


def _action_switch_count(events: list[dict[str, Any]]) -> int:
    ordered = sorted(events, key=lambda e: int(e.get("relative_time_sec", 0)))
    return sum(1 for left, right in zip(ordered, ordered[1:]) if left.get("action") != right.get("action"))


def _dominant_action(events: list[dict[str, Any]]) -> str:
    counts = Counter(e.get("action", "unknown") for e in events)
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] if counts else "unknown"


def _dominant_object_type(events: list[dict[str, Any]]) -> str:
    counts = Counter(e.get("object_type", "unknown") for e in events)
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] if counts else "unknown"


def _rarity_buckets(events: list[dict[str, Any]]) -> dict[str, dict[tuple[str, str], int]]:
    actor_action = Counter((e.get("actor_id", "unknown"), e.get("action", "unknown")) for e in events)
    object_actor = Counter((e.get("actor_id", "unknown"), e.get("object_type", "unknown")) for e in events)
    return {
        "actor_action": {key: _rarity_bucket(count, len(events)) for key, count in actor_action.items()},
        "object_actor": {key: _rarity_bucket(count, len(events)) for key, count in object_actor.items()},
    }


def _rarity_bucket(count: int, total: int) -> int:
    if total < 3 or count <= 0:
        return 0
    ratio = count / total
    if count == 1:
        return 3
    if ratio <= 0.25:
        return 2
    return 1


def _high_risk_combo_count(events: list[dict[str, Any]]) -> int:
    return _count_events(
        events,
        lambda e: (
            e.get("object_criticality") == "high"
            and e.get("action") in WRITE_ACTIONS | {"permission_probe"}
            and (e.get("visibility_delta") == "decrease" or e.get("capability_check_result") == "denied" or e.get("status") == "denied")
        ),
    )
