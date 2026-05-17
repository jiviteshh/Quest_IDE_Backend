"""
AI Assistant Service
────────────────────────────────────────────────────────────────
COMPLETELY ISOLATED from execution flow, parser, and judge.
Uses the same NVIDIA LLM provider but with different prompts.

Does NOT modify:
- judge_service.py
- evaluation_service.py
- llm_service.py (parser)
- testcase schema
- execution contracts
────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from dotenv import load_dotenv
from openai import APIConnectionError, APIError, AuthenticationError, OpenAI, RateLimitError

from app.config import (
    LLM_TIMEOUT_SECONDS,
    NVIDIA_API_BASE_URL,
    NVIDIA_MODEL,
)

load_dotenv()
logger = logging.getLogger(__name__)


class AIAssistError(RuntimeError):
    """Non-critical error — AI features should never crash the platform."""


# ── System prompts per action ────────────────────────────────

PROMPTS: dict[str, str] = {
    "chat": (
        "You are QuestIDE's contextual coding assistant inside an AI-native IDE. "
        "Answer the user's current question using the provided workspace context: "
        "problem statement, current code, selected language, latest run result, "
        "latest submit result, failed testcase, stdout/stderr, and execution metadata. "
        "Be practical, concise, and specific. Do not claim you executed code. "
        "Never modify or invent hidden testcase data. When useful, include short "
        "markdown sections and fenced code snippets."
    ),
    "hint": (
        "You are a coding tutor. Given a problem description and user's code, "
        "provide a SUBTLE HINT without revealing the full solution. "
        "Guide the student toward the right approach. Be concise (2-4 sentences max)."
    ),
    "explain_approach": (
        "You are a coding tutor. Given a problem description, explain the optimal "
        "algorithmic approach step by step. Include: intuition, key observations, "
        "data structures to use, and time/space complexity. Do NOT write code."
    ),
    "optimize": (
        "You are a code reviewer. Given a problem and user's code, suggest specific "
        "optimizations. Focus on: algorithmic improvements, unnecessary operations, "
        "better data structures. Be specific and actionable."
    ),
    "find_bug": (
        "You are a debugging assistant. Given a problem, user's code, and a failed "
        "testcase (input, expected output, actual output), identify the probable bug. "
        "Explain: what went wrong, why, and how to fix it. Do NOT rewrite the full solution. "
        "Do NOT expose hidden testcase data beyond what's shown."
    ),
    "complexity_analysis": (
        "You are a complexity analyst. Given a problem and user's code, estimate: "
        "1. Time Complexity (Big-O) "
        "2. Space Complexity (Big-O) "
        "Explain your reasoning briefly. Format the answer clearly."
    ),
    "explain_solution": (
        "You are a coding tutor. The student's solution was ACCEPTED. "
        "Explain: why this approach works, the intuition behind it, "
        "edge cases it handles, and any alternative approaches. "
        "This is a learning opportunity — be thorough but clear."
    ),
    "generate_testcases": (
        "You are a test engineer. Given a problem description, generate 3-5 additional "
        "testcases focusing on: edge cases, boundary conditions, stress tests, and tricky inputs. "
        "Format each testcase as:\n"
        "Input:\n<stdin input>\n"
        "Expected Output:\n<expected output>\n\n"
        "Each input must be stdin-compatible (one value per line or space-separated as needed). "
        "Each output must be the exact expected stdout."
    ),
}


def _get_client() -> OpenAI:
    api_key = os.getenv("NVIDIA_API_KEY", "").strip()
    if not api_key:
        raise AIAssistError("NVIDIA_API_KEY not configured.")
    return OpenAI(base_url=NVIDIA_API_BASE_URL, api_key=api_key, timeout=LLM_TIMEOUT_SECONDS)


def get_ai_assistance(
    action: str,
    query: Optional[str],
    problem_description: str,
    user_code: str,
    language: str,
    failed_testcase: Optional[dict[str, str]] = None,
    last_verdict: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Generate AI assistance content based on the requested action.
    This is ISOLATED from execution — it only generates text advice.
    """
    system_prompt = PROMPTS.get(action)
    if not system_prompt:
        raise AIAssistError(f"Unknown AI action: {action}")

    # Build user message. This is advisory-only context and remains isolated from judge execution.
    parts = []

    if query:
        parts.append(f"## User Question\n{query}\n")

    parts.append(f"## Problem\n{problem_description}\n")

    if user_code.strip():
        parts.append(f"## User Code ({language})\n```{language.lower()}\n{user_code}\n```\n")

    if last_verdict:
        parts.append(f"## Last Verdict: {last_verdict}\n")

    if failed_testcase and action == "find_bug":
        parts.append(
            f"## Failed Testcase\n"
            f"Input:\n{failed_testcase.get('input', 'N/A')}\n\n"
            f"Expected Output:\n{failed_testcase.get('expected_output', 'N/A')}\n\n"
            f"Actual Output:\n{failed_testcase.get('actual_output', 'N/A')}\n"
        )

    if failed_testcase and action == "chat":
        parts.append(
            f"## Failed Testcase\n"
            f"Input:\n{failed_testcase.get('input', 'N/A')}\n\n"
            f"Expected Output:\n{failed_testcase.get('expected_output', 'N/A')}\n\n"
            f"Actual Output:\n{failed_testcase.get('actual_output', 'N/A')}\n"
        )

    if context:
        parts.append(
            "## Workspace Context JSON\n"
            "```json\n"
            f"{json.dumps(context, ensure_ascii=False, indent=2, default=str)[:12000]}\n"
            "```\n"
        )

    user_message = "\n".join(parts)

    client = _get_client()
    logger.info("AI assist request: action=%s, code_len=%d", action, len(user_code))

    try:
        response = client.chat.completions.create(
            model=NVIDIA_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            top_p=0.9,
            max_tokens=2048,
        )
    except (AuthenticationError, RateLimitError, APIConnectionError, APIError) as exc:
        logger.error("AI assist LLM error: %s", exc)
        raise AIAssistError(f"AI service error: {type(exc).__name__}") from exc
    except Exception as exc:
        logger.exception("Unexpected AI assist failure")
        raise AIAssistError("Unexpected AI service failure.") from exc

    content = (response.choices[0].message.content if response.choices else "") or ""

    # Strip thinking tags if model uses them
    import re
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

    return {
        "content": content,
        "action": action,
    }
