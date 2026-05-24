from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PRIVATE_GENERATED_PREFIXES = (
    "data/private/",
    "models/private/",
    "reports/private/",
    "splunk/private/",
)

FORBIDDEN_ARTIFACT_SUFFIXES = (
    ".csv",
    ".pkl",
    ".joblib",
    ".onnx",
    ".mlmodel",
)

FORBIDDEN_PUBLIC_CLAIMS = (
    "detects tampering",
    "detects malicious activity",
    "production-ready detection",
    "validated soc efficacy",
    "trained on real attacks",
    "real-world detection performance",
)

CLAIM_ALLOWLIST_PATHS = {
    "docs/v0-model-pipeline-spec.md",
    "docs/v0-model-pipeline-spec-adversarial.md",
    "src/ai_tamperguard/public_safety.py",
    "tests/test_public_safety.py",
}


@dataclass(frozen=True)
class Finding:
    path: str
    reason: str


def scan_paths(paths: list[str]) -> list[Finding]:
    """Scan explicit public repo paths for v0 private-artifact leaks.

    The scanner intentionally ships only generic, public-safe patterns. Any
    lab-specific hostnames, users, or denylist terms must stay outside the repo
    or under an ignored private path.
    """

    findings: list[Finding] = []
    for raw_path in paths:
        path = Path(raw_path)
        normalized = _normalize_path(path)
        if _is_git_path(normalized):
            continue

        if not path.exists():
            findings.extend(_scan_path_metadata(normalized))
            findings.append(Finding(normalized, "missing path explicitly passed to scanner"))
            continue

        if path.is_dir():
            findings.extend(_scan_path_metadata(normalized))
            for child in sorted(path.rglob("*")):
                child_normalized = _normalize_path(child)
                if _is_git_path(child_normalized) or child.is_dir():
                    continue
                findings.extend(_scan_existing_file(child, child_normalized))
            continue

        findings.extend(_scan_existing_file(path, normalized))

    return findings


def _scan_existing_file(path: Path, normalized: str) -> list[Finding]:
    findings = _scan_path_metadata(normalized)
    if _should_scan_text(path):
        findings.extend(_scan_text(path, normalized))
    return findings


def _scan_path_metadata(normalized: str) -> list[Finding]:
    findings: list[Finding] = []
    if any(normalized == prefix.rstrip("/") or normalized.startswith(prefix) for prefix in PRIVATE_GENERATED_PREFIXES):
        findings.append(Finding(normalized, "private generated path must not be tracked"))

    if Path(normalized).suffix.lower() in FORBIDDEN_ARTIFACT_SUFFIXES:
        findings.append(Finding(normalized, "forbidden generated artifact extension"))

    return findings


def _scan_text(path: Path, normalized: str) -> list[Finding]:
    if normalized in CLAIM_ALLOWLIST_PATHS:
        return []

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    except OSError as exc:
        return [Finding(normalized, f"unreadable text file: {exc.__class__.__name__}")]

    lower_text = text.lower()
    findings: list[Finding] = []
    for phrase in FORBIDDEN_PUBLIC_CLAIMS:
        if phrase in lower_text:
            findings.append(Finding(normalized, f"forbidden claim phrase: {phrase}"))
    return findings


def _should_scan_text(path: Path) -> bool:
    return path.suffix.lower() in {".md", ".txt", ".py", ".toml", ".yaml", ".yml", ".json", ".spl"}


def _is_git_path(normalized: str) -> bool:
    return normalized == ".git" or normalized.startswith(".git/")


def _normalize_path(path: Path) -> str:
    text = path.as_posix()
    if path.is_absolute():
        try:
            text = path.relative_to(Path.cwd()).as_posix()
        except ValueError:
            text = path.as_posix()
    return text.removeprefix("./")
