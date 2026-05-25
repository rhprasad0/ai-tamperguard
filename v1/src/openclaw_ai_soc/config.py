"""Configuration for Sergeant Openclaw AI SOC analyst v1."""

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

V1_OPENAI_BASE_URL = "http://kube1.lan:4001/v1"
V1_OPENAI_BASE_URL_FALLBACK = "http://192.168.0.101:4001/v1"
V1_ALLOWED_OPENAI_BASE_URLS = frozenset(
    {V1_OPENAI_BASE_URL, V1_OPENAI_BASE_URL_FALLBACK}
)
V1_MODEL = "gpt-5.4-mini"


class OpenclawSettings(BaseSettings):
    """Validated startup settings for the conservative v1 analyst."""

    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=False,
        extra="ignore",
        validate_assignment=True,
    )

    # Bridge (chat completions + embeddings).
    openai_base_url: str = V1_OPENAI_BASE_URL
    openai_api_key: str = Field(default="replace-with-codex-bridge-api-key", repr=False)
    codex_bridge_api_key: str = Field(
        default="replace-with-codex-bridge-api-key", repr=False
    )
    ai_soc_model: str = V1_MODEL

    # Graphiti incident precedent / case-law memory.
    graphiti_mcp_url: str = "http://kube1.lan:8010/mcp/"
    graphiti_group_id: str = "policy-bonfire-2"

    # Splunk evidence access and bounds.
    splunk_mcp_server_name: str = "splunk-mcp-server"
    splunk_default_earliest: str = "-2h"
    splunk_default_latest: str = "now"
    splunk_max_results: int = 100
    splunk_max_window: str = "24h"

    # Optional local service credentials; never required by default unit tests.
    splunk_host: str = "https://192.168.0.102:8089"
    splunk_username: str = "replace-with-splunk-user-if-needed"
    splunk_password: str = Field(
        default="replace-with-splunk-password-if-needed", repr=False
    )
    splunk_token: str = Field(default="replace-with-splunk-token-if-needed", repr=False)
    splunk_hec_url: str = "https://192.168.0.102:8088/services/collector/event"
    splunk_hec_token: str = Field(
        default="replace-with-agentops-hec-token-if-app-emits-events", repr=False
    )

    # LangSmith (external; trace policy gates later decide detail level).
    langsmith_tracing: bool = True
    langsmith_api_key: str = Field(default="replace-with-langsmith-api-key", repr=False)
    langsmith_project: str = "sergeant-openclaw-ai-soc-analyst"

    # Slack notification output for summaries only in v1.
    slack_bot_token: str = Field(
        default="replace-with-slack-bot-token-if-used", repr=False
    )
    slack_channel_id: str = "replace-with-channel-id-if-used"

    # v1 product flags.
    ai_soc_trigger_mode: str = "manual_hermes"
    ai_soc_memory_backend: str = "graphiti"
    ai_soc_notify_mode: str = "summary_only"
    ai_soc_full_langsmith_for_synthetic_only: bool = True
    ai_soc_remediation_enabled: bool = False
    ai_soc_default_incident_mode: Literal[
        "synthetic", "real_home_telemetry", "private_test"
    ] = "synthetic"
    ai_soc_log_level: str = "INFO"
    ai_soc_log_format: Literal["json", "plain"] = "json"

    @field_validator("openai_base_url")
    @classmethod
    def require_v1_bridge_url(cls, value: str) -> str:
        if value not in V1_ALLOWED_OPENAI_BASE_URLS:
            raise ValueError(
                "OPENAI_BASE_URL must equal an allowed LAN Codex bridge endpoint"
            )
        return value

    @field_validator("ai_soc_model")
    @classmethod
    def require_v1_model(cls, value: str) -> str:
        if value != V1_MODEL:
            raise ValueError(f"AI_SOC_MODEL must equal the v1 model ({V1_MODEL})")
        return value

    @field_validator("ai_soc_trigger_mode")
    @classmethod
    def require_manual_hermes_trigger(cls, value: str) -> str:
        if value != "manual_hermes":
            raise ValueError("AI_SOC_TRIGGER_MODE must be manual_hermes in v1")
        return value

    @field_validator("ai_soc_memory_backend")
    @classmethod
    def require_graphiti_memory(cls, value: str) -> str:
        if value != "graphiti":
            raise ValueError("AI_SOC_MEMORY_BACKEND must be graphiti in v1")
        return value

    @field_validator("ai_soc_notify_mode")
    @classmethod
    def require_summary_only_notifications(cls, value: str) -> str:
        if value != "summary_only":
            raise ValueError("AI_SOC_NOTIFY_MODE must be summary_only in v1")
        return value

    @field_validator("ai_soc_remediation_enabled")
    @classmethod
    def reject_remediation_enabled(cls, value: bool) -> bool:
        if value is not False:
            raise ValueError("AI_SOC_REMEDIATION_ENABLED must be false in v1")
        return value

    @field_validator("ai_soc_log_level")
    @classmethod
    def require_supported_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(
                "AI_SOC_LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL"
            )
        return normalized

    @field_validator("splunk_max_window")
    @classmethod
    def require_positive_bounded_splunk_window(cls, value: str) -> str:
        unit = value[-1:]
        amount_text = value[:-1]
        if unit not in {"m", "h"} or not amount_text.lstrip("-").isdigit():
            raise ValueError(
                "SPLUNK_MAX_WINDOW must be a positive duration such as 24h"
            )

        amount = int(amount_text)
        hours = amount / 60 if unit == "m" else amount
        if hours <= 0 or hours > 24:
            raise ValueError("SPLUNK_MAX_WINDOW must be greater than 0 and at most 24h")
        return value

    @field_validator("splunk_max_results")
    @classmethod
    def require_bounded_splunk_results(cls, value: int) -> int:
        if value <= 0 or value > 1000:
            raise ValueError("SPLUNK_MAX_RESULTS must be between 1 and 1000")
        return value


def load_config(*, env_file: str | None = ".env") -> OpenclawSettings:
    """Load runtime settings, optionally including the private local .env file."""

    return OpenclawSettings(_env_file=env_file)  # type: ignore[call-arg]


Settings = OpenclawSettings
