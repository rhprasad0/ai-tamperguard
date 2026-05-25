from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

LABEL_POSITIVE_FAMILIES = {
    "evidence_laundering",
    "alert_suppression",
    "report_alibi_generation",
    "input_or_token_tamper",
    "routing_or_transform_tamper",
    "successful_synthetic_tamper",
}


def label_index(answer_key: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["scenario_run_id"]: row for row in answer_key}


def derive_windows(events: list[dict[str, Any]], answer_key: list[dict[str, Any]], *, size_sec: int) -> list[dict[str, Any]]:
    labels = label_index(answer_key)
    buckets: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for event in sorted(events, key=lambda e: (e.get("scenario_run_id") or "", int(e.get("relative_time_sec", 0)), e["event_id"])):
        run_id = event.get("scenario_run_id") or "background"
        actor = event["actor_id"]
        bucket = int(event.get("relative_time_sec", 0)) // size_sec
        buckets[(run_id, actor, bucket)].append(event)
    rows: list[dict[str, Any]] = []
    for index, ((run_id, actor, bucket), bucket_events) in enumerate(sorted(buckets.items()), 1):
        actions = Counter(e["action"] for e in bucket_events)
        families = Counter(e["action_family"] for e in bucket_events)
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
            "feature_config_change_count": sum(actions.get(a, 0) for a in ("modify", "disable", "enable", "create", "delete")),
            "feature_visibility_object_read_count": sum(1 for e in bucket_events if e.get("object_role") == "detection_or_visibility_artifact" and e["action"] in {"read", "search"}),
            "feature_visibility_object_write_count": sum(1 for e in bucket_events if e.get("object_role") == "detection_or_visibility_artifact" and e["action"] in {"modify", "disable", "enable", "create", "delete"}),
            "feature_saved_search_modify_count": sum(1 for e in bucket_events if e["object_type"] == "saved_search" and e["action"] == "modify"),
            "feature_dashboard_modify_count": sum(1 for e in bucket_events if e["object_type"] == "dashboard" and e["action"] == "modify"),
            "feature_alert_modify_count": sum(1 for e in bucket_events if e["object_type"] == "alert" and e["action"] in {"modify", "disable"}),
            "feature_permission_denied_count": sum(1 for e in bucket_events if e["status"] == "denied"),
            "feature_distinct_object_type_count": len(objects),
            "feature_search_then_modify_flag": int(_has_order(bucket_events, {"search"}, {"modify", "disable"})),
            "feature_modify_then_requery_flag": int(_has_order(bucket_events, {"modify", "disable"}, {"search"})),
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


def _has_order(events: list[dict[str, Any]], first: set[str], second: set[str]) -> bool:
    seen=False
    for e in sorted(events, key=lambda e:int(e.get("relative_time_sec",0))):
        if e["action"] in first:
            seen=True
        if seen and e["action"] in second:
            return True
    return False
