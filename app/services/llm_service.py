from __future__ import annotations

import json
import logging
import os
import re
import ast
from json import JSONDecodeError
from typing import Any

from dotenv import load_dotenv
from openai import APIConnectionError, APIError, AuthenticationError, OpenAI, RateLimitError

from app.config import (
    LLM_TIMEOUT_SECONDS,
    NVIDIA_API_BASE_URL,
    NVIDIA_MAX_TOKENS,
    NVIDIA_MODEL,
    NVIDIA_TEMPERATURE,
    NVIDIA_TOP_P,
)

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SYSTEM PROMPT — strict stdin/stdout online judge parser
# ---------------------------------------------------------------------------
# Loaded from external text file to avoid Python string escaping issues.
# The .txt file contains the prompt exactly as the AI should see it.
import pathlib as _pathlib

_PROMPT_PATH = _pathlib.Path(__file__).resolve().parent.parent / "prompts" / "parser_prompt.txt"
SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")


class LLMServiceError(ValueError):
    """Base parsing failure for user-safe route responses."""


class LLMAuthenticationError(LLMServiceError):
    """Raised when NVIDIA key is invalid or missing."""


class LLMRateLimitError(LLMServiceError):
    """Raised for provider rate limit responses."""


class LLMProviderError(LLMServiceError):
    """Raised for upstream failures not caused by user input."""


def _get_nvidia_client() -> OpenAI:
    api_key = os.getenv("NVIDIA_API_KEY", "").strip()
    if not api_key:
        raise LLMAuthenticationError(
            "NVIDIA_API_KEY is missing. Add it to your environment or .env file."
        )

    try:
        api_key.encode("ascii")
    except UnicodeEncodeError as exc:
        raise LLMAuthenticationError(
            "NVIDIA_API_KEY contains non-ASCII characters. Re-copy the key from NVIDIA Build dashboard."
        ) from exc

    return OpenAI(base_url=NVIDIA_API_BASE_URL, api_key=api_key, timeout=LLM_TIMEOUT_SECONDS)


def _extract_json_text(content: str) -> str:
    cleaned = content.strip()
    # Strip markdown code fences if present
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    if not cleaned:
        raise LLMServiceError("Model returned an empty response. Please retry.")

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise LLMServiceError("Model returned non-JSON output. Please retry.")

    return cleaned[start : end + 1]


def _decode_json_lenient(json_text: str) -> dict[str, Any]:
    """
    Decode strict JSON first, then repair common LLM near-JSON mistakes.

    NVIDIA occasionally returns structurally correct objects with small JSON
    violations such as unquoted keys or trailing commas. This keeps the parser
    schema unchanged while avoiding avoidable 400s for recoverable responses.
    """
    try:
        parsed = json.loads(json_text)
    except JSONDecodeError as first_exc:
        repaired = json_text
        repaired = repaired.replace("“", '"').replace("”", '"').replace("’", "'")
        repaired = re.sub(
            r'(?P<prefix>[{,]\s*)(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*:',
            r'\g<prefix>"\g<key>":',
            repaired,
        )
        repaired = re.sub(r",\s*([}\]])", r"\1", repaired)

        try:
            parsed = json.loads(repaired)
        except JSONDecodeError:
            try:
                parsed = ast.literal_eval(repaired)
            except (SyntaxError, ValueError) as fallback_exc:
                logger.exception("Malformed JSON received from NVIDIA model.")
                raise LLMServiceError("Model returned invalid JSON. Please retry.") from fallback_exc

        logger.warning(
            "Recovered malformed NVIDIA JSON. original_error=%s",
            first_exc,
        )

    if not isinstance(parsed, dict):
        logger.error("Parsed output is not an object.")
        raise LLMServiceError("Model returned an invalid JSON structure. Please retry.")

    return parsed


def _fix_newlines(value: str) -> str:
    """
    Convert literal backslash-n sequences to real newlines.

    The AI may produce JSON with \\n (literal backslash+n) instead of \n
    (actual newline). This safety net ensures stdin always has real newlines
    so programs can read input line by line.
    """
    if not value:
        return value
    # Replace literal two-char sequence '\n' with actual newline
    # (json.loads already converts JSON \n to real newline, but if the AI
    # double-escapes it, we get literal backslash+n which we fix here)
    return value.replace("\\n", "\n")


def _sanitize_output(value: str) -> str:
    """Strip any explanation/prose from expected_output."""
    text = str(value).strip()
    # If it starts with explanation keywords, it's bad — return empty
    lowered = text.lower()
    bad_prefixes = ("because", "therefore", "hence", "explanation", "the answer", "output:", "result:")
    for prefix in bad_prefixes:
        if lowered.startswith(prefix):
            return ""
    return text


def _normalize_parsed_problem(data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize AI parser output into a clean structure.
    Keeps it simple: directly maps visible_testcases and hidden_testcases.
    No complex fallback logic.
    """
    title = str(data.get("title", "")).strip() or "Untitled Problem"
    difficulty = str(data.get("difficulty", "Medium")).strip() or "Medium"
    description = str(data.get("description", "")).strip()

    # Constraints
    constraints_raw = data.get("constraints", [])
    constraints = (
        [str(item).strip() for item in constraints_raw if str(item).strip()]
        if isinstance(constraints_raw, list)
        else []
    )

    # Starter code
    starter_raw = data.get("starter_code", {})
    starter_code = {"python": "", "java": "", "cpp": ""}
    if isinstance(starter_raw, str):
        starter_code = {"python": starter_raw, "java": starter_raw, "cpp": starter_raw}
    elif isinstance(starter_raw, dict):
        for lang in ("python", "java", "cpp"):
            starter_code[lang] = str(starter_raw.get(lang, ""))

    # --- Build testcase lists ---
    def _build_testcases(raw: Any, hidden: bool) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        if not isinstance(raw, list):
            return result
        for item in raw:
            if not isinstance(item, dict):
                continue
            stdin_val = _fix_newlines(str(item.get("input", "")).strip())
            expected = _fix_newlines(_sanitize_output(item.get("expected_output", "")))
            # Skip empty/bad testcases
            if not stdin_val or not expected:
                continue
            result.append({
                "stdin": stdin_val,
                "expected_output": expected,
                "is_hidden": hidden,
            })
        return result

    visible_cases = _build_testcases(data.get("visible_testcases", []), hidden=False)
    hidden_cases = _build_testcases(data.get("hidden_testcases", []), hidden=True)

    # --- Auto-fix hidden testcase format to match visible format ---
    # The AI sometimes collapses multi-line hidden inputs onto one line
    # (e.g. "2 7 11 15 9" instead of "2 7 11 15\n9").
    # Detect this and fix by matching the visible testcase line structure.
    if visible_cases and hidden_cases:
        # Determine expected line count from visible testcases
        visible_line_counts = [tc["stdin"].count("\n") + 1 for tc in visible_cases]
        expected_lines = max(visible_line_counts)  # how many lines each input should have

        if expected_lines > 1:
            for tc in hidden_cases:
                actual_lines = tc["stdin"].count("\n") + 1
                if actual_lines < expected_lines:
                    # Hidden testcase has fewer lines — try to fix by splitting
                    # trailing tokens onto separate lines
                    tokens = tc["stdin"].split()
                    missing_lines = expected_lines - actual_lines
                    if len(tokens) > missing_lines:
                        # Pop the last N tokens as separate lines
                        tail = tokens[-missing_lines:]
                        head = tokens[:-missing_lines]
                        fixed = " ".join(head) + "\n" + "\n".join(tail)
                        print(f"  [AUTO-FIX] Hidden testcase format repaired:")
                        print(f"    Before: {repr(tc['stdin'])}")
                        print(f"    After:  {repr(fixed)}")
                        tc["stdin"] = fixed

    # Assign sequential IDs and build the unified testcases list
    all_testcases: list[dict[str, Any]] = []
    idx = 1
    for tc in visible_cases:
        all_testcases.append({
            "id": idx,
            "display_input": tc["stdin"],
            "display_output": tc["expected_output"],
            "stdin": tc["stdin"],
            "expected_output": tc["expected_output"],
            "is_hidden": False,
        })
        idx += 1
    for tc in hidden_cases:
        all_testcases.append({
            "id": idx,
            "display_input": "Hidden",
            "display_output": "",
            "stdin": tc["stdin"],
            "expected_output": tc["expected_output"],
            "is_hidden": True,
        })
        idx += 1

    # Build separate payload lists for the API response
    visible_payload = [
        {"input": tc["stdin"], "expected_output": tc["expected_output"], "is_hidden": False}
        for tc in all_testcases
        if not tc["is_hidden"]
    ]
    hidden_payload = [
        {"input": tc["stdin"], "expected_output": tc["expected_output"], "is_hidden": True}
        for tc in all_testcases
        if tc["is_hidden"]
    ]

    # Build examples from visible testcases (for the problem panel)
    examples = [
        {"input": tc["stdin"], "output": tc["expected_output"]}
        for tc in all_testcases
        if not tc["is_hidden"]
    ]

    return {
        "title": title,
        "difficulty": difficulty,
        "description": description,
        "constraints": constraints,
        "examples": examples,
        "visible_testcases": visible_payload,
        "hidden_testcases": hidden_payload,
        "testcases": all_testcases,
        "starter_code": starter_code,
    }


def parse_problem(problem_text: str) -> dict[str, Any]:
    if not problem_text or len(problem_text.strip()) < 10:
        raise LLMServiceError("problem_text must be at least 10 characters.")

    client = _get_nvidia_client()
    logger.info("Parsing problem with NVIDIA model. length=%d", len(problem_text))

    try:
        response = client.chat.completions.create(
            model=NVIDIA_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": problem_text.strip()},
            ],
            temperature=NVIDIA_TEMPERATURE,
            top_p=NVIDIA_TOP_P,
            max_tokens=NVIDIA_MAX_TOKENS,
        )
    except AuthenticationError as exc:
        logger.exception("NVIDIA authentication failed.")
        raise LLMAuthenticationError("Invalid NVIDIA_API_KEY. Please verify your API key.") from exc
    except RateLimitError as exc:
        logger.exception("NVIDIA rate limit hit.")
        raise LLMRateLimitError("NVIDIA API rate limit reached. Please retry shortly.") from exc
    except APIConnectionError as exc:
        logger.exception("NVIDIA network connection error.")
        raise LLMProviderError("Unable to reach NVIDIA API. Check network and retry.") from exc
    except APIError as exc:
        logger.exception("NVIDIA API error.")
        raise LLMProviderError("NVIDIA API returned an error. Please retry.") from exc
    except Exception as exc:
        logger.exception("Unexpected NVIDIA client failure.")
        raise LLMProviderError("Unexpected model provider failure.") from exc

    content = (response.choices[0].message.content if response.choices else "") or ""
    logger.debug("Raw LLM response content: %s", content[:500])

    json_text = _extract_json_text(content)

    parsed = _decode_json_lenient(json_text)

    normalized = _normalize_parsed_problem(parsed)
    logger.info(
        "Problem parsing successful. title=%s visible=%d hidden=%d",
        normalized.get("title", ""),
        len(normalized.get("visible_testcases", [])),
        len(normalized.get("hidden_testcases", [])),
    )
    return normalized
