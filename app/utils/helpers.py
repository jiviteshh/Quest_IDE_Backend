"""Utility helpers shared across services."""

from __future__ import annotations

import re


def normalize_output(output: str) -> str:
    """
    Normalize program output for resilient comparison.

    Rules:
    - trim outer whitespace/newlines
    - remove trailing/leading spaces per line
    - collapse repeated internal whitespace to a single space
    - ignore extra blank lines at the beginning/end
    """
    if output is None:
        return ""

    text = output.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return ""

    normalized_lines: list[str] = []
    for line in text.split("\n"):
        cleaned = re.sub(r"\s+", " ", line.strip())
        normalized_lines.append(cleaned)

    return "\n".join(normalized_lines).strip()


def compare_outputs(actual: str, expected: str) -> bool:
    """Compare execution output while tolerating formatting-only differences."""
    return normalize_output(actual) == normalize_output(expected)
