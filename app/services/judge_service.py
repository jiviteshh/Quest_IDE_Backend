"""
Execution service abstraction.

This module isolates provider-specific execution details so the route layer
and schemas stay unchanged if we swap Piston for Judge0 later.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

import httpx

from app.config import (
    EXECUTION_TIMEOUT_SECONDS,
    LANGUAGE_MAP,
    PISTON_API_KEY,
    PISTON_URL,
)

logger = logging.getLogger(__name__)


class ExecutionServiceError(RuntimeError):
    """Base error for upstream execution failures."""


class UnsupportedLanguageError(ValueError):
    """Raised when the requested language_id is not configured."""


class UpstreamTimeoutError(ExecutionServiceError):
    """Raised when upstream execution provider times out."""


class UpstreamResponseError(ExecutionServiceError):
    """Raised for malformed or invalid upstream responses."""


class UpstreamExecutionError(ExecutionServiceError):
    """Raised when upstream returns an execution/provider error."""


def get_supported_languages() -> dict[int, dict[str, str]]:
    """Return configured language mapping."""
    return LANGUAGE_MAP


def _wrap_java_source_if_needed(source_code: str) -> str:
    """
    Ensure Java submissions are executable as Main.java for Piston.

    If the user submits a method-only snippet, wrap it into `public class Main`
    and keep any top-level `import` statements above the class.
    """
    if re.search(r"\bclass\s+\w+", source_code):
        return source_code

    lines = source_code.splitlines()
    import_lines: list[str] = []
    body_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("import ") and stripped.endswith(";"):
            import_lines.append(stripped)
        else:
            body_lines.append(line)

    if (
        "import java.util.*;" not in import_lines
        and re.search(r"\b(HashMap|Map|List|ArrayList|Set|HashSet|Queue|Deque|Arrays)\b", source_code)
    ):
        import_lines.insert(0, "import java.util.*;")

    body = "\n".join(f"    {line}" if line.strip() else "" for line in body_lines).strip("\n")
    wrapped = "public class Main {\n"
    if body:
        wrapped += f"{body}\n"
    wrapped += "}\n"

    if import_lines:
        return "\n".join(import_lines) + "\n\n" + wrapped

    return wrapped


def _fix_stdin_newlines(value: str) -> str:
    """
    Last-mile safety net: convert any literal backslash-n sequences in stdin
    to real newline characters before sending to Piston.

    This handles the case where the AI double-escapes newlines in JSON,
    or where old testcases stored in the frontend have literal \\n.
    """
    if not value:
        return ""
    # Replace literal two-char '\n' with real newline
    return value.replace("\\n", "\n")


def _build_payload(
    source_code: str,
    language_id: int,
    stdin: Optional[str]
) -> dict[str, Any]:

    lang_info = LANGUAGE_MAP.get(language_id)

    if not lang_info:
        raise UnsupportedLanguageError(
            f"Unsupported language_id: {language_id}"
        )

    language = lang_info["language"]
    version = lang_info["version"]

    # CRITICAL: fix any literal \n to real newlines before sending to Piston
    fixed_stdin = _fix_stdin_newlines(stdin or "")

    # IMPORTANT:
    # Java requires filename Main for Piston (it appends .java)
    if language == "java":
        prepared_source = _wrap_java_source_if_needed(source_code)
        files = [
            {
                "name": "Main",
                "content": prepared_source
            }
        ]
    else:
        files = [
            {
                "content": source_code
            }
        ]

    return {
        "language": language,
        "version": version,
        "files": files,
        "stdin": fixed_stdin
    }


def _normalize_response(
    data: dict[str, Any],
    language_id: int
) -> dict[str, Any]:

    lang_info = LANGUAGE_MAP[language_id]

    # DEBUG
    logger.error("FULL PISTON RESPONSE: %s", data)

    compile_result = data.get("compile", {})
    run_result = data.get("run", {})

    # Handle malformed response
    if not isinstance(compile_result, dict):
        compile_result = {}

    if not isinstance(run_result, dict):
        run_result = {}

    # Extract outputs
    compile_stdout = compile_result.get("stdout", "")
    compile_stderr = compile_result.get("stderr", "")

    run_stdout = run_result.get("stdout", "")
    run_stderr = run_result.get("stderr", "")
    run_output = run_result.get("output", "")
    run_message = str(run_result.get("message", "") or "")
    run_status = str(run_result.get("status", "") or "")

    # IMPORTANT:
    # Java sometimes only populates compile stage
    stdout = run_stdout or compile_stdout or run_output

    stderr_parts = []

    if compile_stderr:
        stderr_parts.append(compile_stderr)

    if run_stderr:
        stderr_parts.append(run_stderr)

    if run_status == "TO" or "time limit" in run_message.lower():
        stderr_parts.append(run_message or "Time limit exceeded")
    elif run_message and not run_stdout and not run_stderr:
        stderr_parts.append(run_message)

    stderr = "\n".join(stderr_parts)

    exit_code = run_result.get("code")

    if exit_code is None:
        exit_code = compile_result.get("code")
    if exit_code is None and (run_status == "TO" or "time limit" in run_message.lower()):
        exit_code = 124

    normalized = {
        "stdout": str(stdout),
        "stderr": str(stderr),
        "compile_output": str(compile_stderr),
        "exit_code": exit_code,
        "time": str(run_result.get("cpu_time")) if run_result.get("cpu_time") is not None else None,
        "memory": run_result.get("memory"),
        "status": {
            "id": run_status,
            "description": run_message,
        } if run_status or run_message else None,
        "language": lang_info["language"],
        "version": lang_info["version"],
    }

    return normalized


async def run_code(
    source_code: str,
    language_id: int,
    stdin: Optional[str] = ""
) -> dict[str, Any]:

    payload = _build_payload(
        source_code=source_code,
        language_id=language_id,
        stdin=stdin
    )

    # ===================== DEBUG LOGGING =====================
    print("========== PISTON EXECUTION DEBUG ==========")
    print(f"LANGUAGE_ID: {language_id}")
    print(f"SOURCE_CODE length: {len(source_code)} chars")
    print(f"STDIN (repr): {repr(payload['stdin'])}")
    print(f"STDIN length: {len(payload['stdin'])} chars")
    print(f"STDIN has real newlines: {chr(10) in payload['stdin']}")
    print(f"STDIN first 200 chars: {payload['stdin'][:200]}")
    print("============================================")
    # =========================================================

    headers: dict[str, str] = {}

    if PISTON_API_KEY:
        headers["Authorization"] = f"Bearer {PISTON_API_KEY}"

    logger.info(
        "Executing language_id=%s using provider=%s",
        language_id,
        PISTON_URL
    )

    try:

        async with httpx.AsyncClient(
            timeout=EXECUTION_TIMEOUT_SECONDS
        ) as client:

            response = await client.post(
                PISTON_URL,
                json=payload,
                headers=headers
            )

    except httpx.TimeoutException as exc:

        logger.error("Execution timeout")

        raise UpstreamTimeoutError(
            "Execution request timed out."
        ) from exc

    except httpx.RequestError as exc:

        logger.error("Provider request failed: %s", exc)

        raise UpstreamExecutionError(
            "Could not reach execution provider."
        ) from exc

    if response.status_code >= 400:

        logger.error(
            "Provider returned HTTP %s: %s",
            response.status_code,
            response.text
        )

        raise UpstreamExecutionError(
            f"Execution provider error (HTTP {response.status_code})."
        )

    try:

        data = response.json()

    except ValueError as exc:

        logger.error("Provider returned invalid JSON")

        raise UpstreamResponseError(
            "Execution provider returned invalid JSON."
        ) from exc

    if not isinstance(data, dict):

        raise UpstreamResponseError(
            "Execution provider returned invalid response shape."
        )

    return _normalize_response(
        data=data,
        language_id=language_id
    )

    