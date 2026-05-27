from __future__ import annotations

import pytest

from ai_tamperguard_v1.research.feature_policy import FeaturePolicyError, resolve_feature_policy


def test_feature_policy_blocks_prefix_all_training(tmp_path):
    policy = tmp_path / "policy.yaml"
    policy.write_text(
        "\n".join(
            [
                "schema_version: feature_policy_v1",
                "allowlist:",
                "  - feature_allowed_count",
                "denylist_generator_signature:",
                "  - feature_generator_proxy",
                "denylist_cross_split_population:",
                "  - feature_actor_action_rarity_bucket",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    resolved = resolve_feature_policy(
        policy,
        csv_columns=[
            "window_id",
            "label_binary",
            "feature_allowed_count",
            "feature_generator_proxy",
            "feature_actor_action_rarity_bucket",
        ],
    )

    assert resolved.feature_order == ["feature_allowed_count"]
    assert resolved.selection_mode == "explicit_allowlist_only"
    assert "feature_generator_proxy" not in resolved.feature_order
    assert "feature_actor_action_rarity_bucket" not in resolved.feature_order


def test_feature_policy_fails_unclassified_feature_columns(tmp_path):
    policy = tmp_path / "policy.yaml"
    policy.write_text(
        "schema_version: feature_policy_v1\nallowlist:\n  - feature_allowed_count\n"
        "denylist_generator_signature: []\ndenylist_cross_split_population: []\n",
        encoding="utf-8",
    )

    with pytest.raises(FeaturePolicyError, match="unclassified feature_ columns"):
        resolve_feature_policy(
            policy,
            csv_columns=["window_id", "label_binary", "feature_allowed_count", "feature_leaky_metadata_proxy"],
        )


def test_feature_policy_fails_if_metadata_is_allowlisted(tmp_path):
    policy = tmp_path / "policy.yaml"
    policy.write_text(
        "schema_version: feature_policy_v1\nallowlist:\n  - window_start_relative_sec\n"
        "denylist_generator_signature: []\ndenylist_cross_split_population: []\n",
        encoding="utf-8",
    )

    with pytest.raises(FeaturePolicyError, match="forbidden metadata"):
        resolve_feature_policy(policy, csv_columns=["window_start_relative_sec", "label_binary"])
