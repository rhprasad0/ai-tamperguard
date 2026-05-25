from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from jsonschema import Draft202012Validator

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"


def load_schema(filename: str) -> dict[str, Any]:
    path = SCHEMA_DIR / filename
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_row(filename: str, row: dict[str, Any]) -> None:
    Draft202012Validator(load_schema(filename)).validate(row)


def validate_rows(filename: str, rows: list[dict[str, Any]]) -> None:
    validator = Draft202012Validator(load_schema(filename))
    for idx, row in enumerate(rows):
        try:
            validator.validate(row)
        except Exception as exc:
            raise type(exc)(f"row {idx} failed {filename}: {exc}") from exc
