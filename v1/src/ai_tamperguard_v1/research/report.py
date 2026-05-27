from __future__ import annotations

from typing import Any


def render_markdown_report(payload: dict[str, Any]) -> str:
    dataset = payload.get("dataset", {})
    policy = payload.get("feature_policy", {})
    leakage = payload.get("leakage_probes", {})
    candidates = payload.get("candidates", [])
    selected = payload.get("selected_candidate")
    lines: list[str] = [
        "# AI TamperGuard External Technique Bakeoff",
        "",
        "## Dataset",
        f"- source CSV: `{dataset.get('source_csv', 'unknown')}`",
        f"- source CSV sha256: `{dataset.get('source_csv_sha256', 'unknown')}`",
        f"- source batch IDs: {dataset.get('source_batch_ids', [])}",
        f"- rows: {dataset.get('rows', 'unknown')}",
        f"- label distribution: {dataset.get('label_distribution', {})}",
        f"- split strategy: {dataset.get('split_strategy', 'unknown')}",
        f"- split distribution: {dataset.get('split_distribution', {})}",
    ]
    if dataset.get("smoke_test_sized_fixture"):
        lines.append("- fixture warning: this is a smoke-test-sized fixture; metric numbers are plumbing diagnostics only.")
    lines += [
        "",
        "## Feature Policy",
        f"- policy file: `{policy.get('policy_path', 'unknown')}`",
        f"- policy sha256: `{policy.get('policy_sha256', 'unknown')}`",
        f"- allowlist size: {len(policy.get('allowlist_resolved', []))}",
        f"- allowlist resolved: {policy.get('allowlist_resolved', [])}",
        f"- denylist_generator_signature applied: {policy.get('denylist_generator_signature_applied', [])}",
        f"- denylist_cross_split_population applied: {policy.get('denylist_cross_split_population_applied', [])}",
        f"- unclassified feature_* columns: {policy.get('csv_feature_columns_unclassified', [])}",
        f"- selection mode: {policy.get('selection_mode', 'unknown')}",
        "",
        "## Gate Summary",
        "| gate | status | notes |",
        "|---|---|---|",
    ]
    for gate in payload.get("gate_summary", []):
        lines.append(f"| {gate.get('gate')} | {gate.get('status')} | {gate.get('notes', '')} |")
    lines += [
        "",
        "## Leakage Probes",
        f"- single-feature AUC max: {leakage.get('single_feature_auc_max', 'n/a')}",
        f"- top single-feature AUCs: {leakage.get('top_single_feature_auc', [])}",
        f"- negative control validation AP drop: {leakage.get('negative_control_validation_ap_drop', 'n/a')}",
        f"- allowlist ablation validation AP drop: {leakage.get('allowlist_ablation_validation_ap_drop', 'n/a')}",
        f"- cross-split correlation probe: {leakage.get('cross_split_correlation_probe_passed', 'n/a')}",
        f"- overall verdict: {leakage.get('verdict', 'unknown')}",
        "",
        "## Candidate Summary",
        "| technique | profile | status | validation AP | validation balanced acc | deployability | leakage verdict | notes |",
        "|---|---|---:|---:|---:|---|---|---|",
    ]
    for candidate in candidates:
        val = candidate.get("metrics", {}).get("validation", {})
        lines.append(
            "| {technique} | {profile} | {status} | {ap} | {ba} | {deploy} | {leak} | {notes} |".format(
                technique=candidate.get("technique"),
                profile=candidate.get("profile"),
                status=candidate.get("status"),
                ap=_fmt(val.get("average_precision")),
                ba=_fmt(val.get("balanced_accuracy")),
                deploy=candidate.get("deployability_class"),
                leak=candidate.get("leakage_verdict", leakage.get("verdict")),
                notes="; ".join(candidate.get("notes", [])),
            )
        )
    lines += [
        "",
        "## Selected Candidate",
        f"Selected: {selected or 'None'}",
        "",
        "## Why This Won / Why Baseline Stayed",
        f"- {payload.get('decision', 'No promotion decision recorded.')}",
        "",
        "## Why Other Candidates Lost",
    ]
    for candidate in candidates:
        if selected != candidate.get("name"):
            lines.append(f"- {candidate.get('name')}: {'; '.join(candidate.get('notes', ['not selected']))}")
    lines += [
        "",
        "## Deployment Notes",
        "- Direct SPL candidates are previews only until a separate Splunk-side equivalence check exists.",
        "- Offline-only candidates are diagnostic comparisons, not deployable replacements.",
        "- Equivalence checks completed: local exported-artifact-vs-estimator only for exported linear artifacts.",
        "",
        "## Non-Claims",
        "- weak proxy labels, not malicious ground truth",
        "- not production detection quality",
        "- not a public benchmark result",
        "- local bakeoff metrics do not prove Splunk-side success",
        "- feature set restricted to explicit allowlist; any future prefix-based widening must be reviewed for generator-signature leakage",
        "",
    ]
    return "\n".join(lines)


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)
