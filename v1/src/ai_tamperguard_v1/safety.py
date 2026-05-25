from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

PRIVATE_PREFIX_PARTS = [
    ("data", "private"),
    ("models", "private"),
    ("reports", "private"),
    ("splunk", "private"),
]
TEXT_SUFFIXES = {".md", ".txt", ".py", ".toml", ".yaml", ".yml", ".json", ".jsonl", ".csv", ".spl"}
FORBIDDEN_CLAIMS = (
    "confirmed attack",
    "confirmed compromise",
    "splunk exploit",
    "detects malicious activity",
    "production-ready detection",
    "proves malicious intent",
)
SECRET_PATTERNS = [
    ("aws access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private key", re.compile(r"BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY")),
    ("jwt-like token", re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")),
    ("secret assignment", re.compile(r"(?i)(password|passwd|api[_-]?key|secret|bearer)\s*[:=]")),
    ("private url", re.compile(r"https?://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+|[^\s/]+\.lan)")),
    ("ip address", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("email address", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("absolute timestamp", re.compile(r"\b20\d\d-\d\d-\d\d[T ]\d\d:\d\d:\d\d")),
    ("local path", re.compile(r"/(home|Users|var|etc)/[A-Za-z0-9._/-]+")),
]
ALLOWLIST_REASON_SNIPPETS = (
    "(?i)(password|passwd|api[_-]?key|secret|token|bearer)",
    "AKIA[0-9A-Z]",
    "BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY",
    "eyJ[A-Za-z0-9_-]",
)

@dataclass(frozen=True)
class Finding:
    path: str
    reason: str


def normalize_path(path: Path) -> str:
    try:
        text = path.relative_to(Path.cwd()).as_posix() if path.is_absolute() else path.as_posix()
    except ValueError:
        text = path.as_posix()
    return text.removeprefix("./")


def scan_paths(paths: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for raw in paths:
        path = Path(raw)
        norm = normalize_path(path)
        if _is_private_path(norm):
            findings.append(Finding(norm, "secret/private config path must not be included in public scan"))
            continue
        if not path.exists():
            findings.append(Finding(norm, "missing path explicitly passed to scanner"))
            continue
        if path.is_dir():
            for child in sorted(path.rglob("*")):
                child_norm = normalize_path(child)
                if child.is_dir() or "/.git/" in f"/{child_norm}/" or _is_private_path(child_norm):
                    continue
                findings.extend(_scan_file(child, child_norm))
        else:
            findings.extend(_scan_file(path, norm))
    return findings


def _scan_file(path: Path, norm: str) -> list[Finding]:
    findings: list[Finding] = []
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return findings
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return findings
    except OSError as exc:
        return [Finding(norm, f"unreadable text file: {exc.__class__.__name__}")]
    lower = text.lower()
    for phrase in FORBIDDEN_CLAIMS:
        if phrase in lower:
            findings.append(Finding(norm, f"forbidden public claim: {phrase}"))
    if any(snippet in text for snippet in ALLOWLIST_REASON_SNIPPETS) and ("public_safety" in norm or "test_public_safety" in norm):
        return findings
    for label, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group(0)
            if _allowed_fixture_value(value):
                continue
            findings.append(Finding(norm, f"forbidden public/private marker: {label}"))
            break
    return findings


def _allowed_fixture_value(value: str) -> bool:
    return value.startswith("evt_") or value.startswith("object_") or value.startswith("actor_")


def _is_private_path(norm: str) -> bool:
    parts = tuple(part for part in norm.split("/") if part)
    return any(parts[:2] == prefix or parts[-2:] == prefix for prefix in PRIVATE_PREFIX_PARTS)
