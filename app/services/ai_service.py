

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
# DESIGN: Concise, structured, developer-focused responses
# Target: 3-8 lines, ~120 words max unless explicitly asked for detailed explanation

PROMPTS: dict[str, str] = {
    "chat": (
        "You are QuestIDE's AI debugging companion. Answer concisely and directly. "
        "Use workspace context (code, failed testcases, execution results) to provide "
        "actionable insights. Keep responses SHORT (3-8 lines). Use structured format: "
        "⚠ Issue | Likely Cause | Fix | Edge Case. Never invent hidden testcase data. "
        "Avoid essays — be sharp and specific."
    ),
    "hint": (
        "Provide ONE subtle hint to guide the user without spoiling. Keep it 1-2 sentences. "
        "Example: '⚠ Off-by-one error in loop condition' or '💡 Consider edge case: empty array'. "
        "No lengthy explanations."
    ),
    "explain_approach": (
        "Explain the optimal algorithm in 5-7 lines max. Format:\n"
        "Approach: [name]\n"
        "Intuition: [one sentence]\n"
        "Complexity: O(time) / O(space)\n"
        "Key insight: [one sentence]\n"
        "Do NOT write code. Be concise."
    ),
    "optimize": (
        "Identify 1-3 specific optimizations. Format:\n"
        "Current: O(time/space)\n"
        "✅ Optimization: [specific fix]\n"
        "Improvement: [new complexity]\n"
        "Example: [tiny code snippet if helpful]\n"
        "Keep total response under 100 words."
    ),
    "find_bug": (
        "Analyze the failed testcase concisely. Format:\n"
        "⚠ Issue: [what's wrong]\n"
        "Cause: [why it fails]\n"
        "Fix: [specific solution]\n"
        "Example fix: [minimal code or logic change]\n"
        "Keep under 80 words. Be direct."
    ),
    "complexity_analysis": (
        "Provide complexity analysis concisely:\n"
        "Time: O(...)\n"
        "Space: O(...)\n"
        "Reasoning: [one-sentence explanation]\n"
        "Bottleneck: [where most time/space goes]\n"
        "Total: 4-5 lines max."
    ),
    "explain_solution": (
        "Explain why the accepted solution works. Format:\n"
        "Why it works: [one sentence intuition]\n"
        "Key insight: [core observation]\n"
        "Edge cases handled: [list 2-3]\n"
        "Complexity: O(time/space)\n"
        "Alternative: [brief mention of other approach]\n"
        "Keep under 100 words."
    ),
    "generate_testcases": (
        "Generate 3-5 additional testcases. Format EXACTLY as:\n"
        "Input:\n<stdin>\n"
        "Expected Output:\n<output>\n\n"
        "Focus on: edge cases (empty, single element), boundary conditions, duplicates, negatives. "
        "Each input must be stdin-compatible. Each output must be exact expected stdout."
    ),
}


def _remove_repeated_lines(text: str, max_repeats: int = 1) -> str:
    """
    Remove repeated or near-identical consecutive lines.
    Prevents response loops like "The 0 is..." repeated endlessly.
    """
    lines = text.split('\n')
    if not lines:
        return text
    
    result = [lines[0]]
    repeat_count = 0
    
    for i in range(1, len(lines)):
        current = lines[i].strip()
        previous = lines[i - 1].strip()
        
        # Check for exact match or very similar lines (>80% similarity)
        if current and previous:
            if current == previous:
                repeat_count += 1
                if repeat_count > max_repeats:
                    continue  # Skip repeated line
            else:
                # Check for substring repetition (common word sequences)
                if len(current) > 10 and current in previous or previous in current:
                    repeat_count += 1
                    if repeat_count > max_repeats:
                        continue
                repeat_count = 0
        
        result.append(lines[i])
    
    return '\n'.join(result)


def _truncate_response(text: str, action: str) -> str:
    """
    Truncate responses to sensible limits based on action.
    Prevents verbose/looping outputs.
    """
    # Target word counts per action (generous limits to allow structure)
    limits: dict[str, int] = {
        "chat": 150,
        "hint": 60,
        "explain_approach": 120,
        "optimize": 100,
        "find_bug": 100,
        "complexity_analysis": 80,
        "explain_solution": 150,
        "generate_testcases": 2000,  # Testcases can be longer
    }
    
    max_words = limits.get(action, 150)
    words = text.split()
    
    if len(words) > max_words:
        text = ' '.join(words[:max_words])
        # Truncate at sentence boundary if possible
        if '.' in text:
            text = text.rsplit('.', 1)[0] + '.'
    
    return text


def _get_client(user_api_key: Optional[str] = None) -> OpenAI:
    """
    Get OpenAI client with priority system:
    1. User-provided API key (from x-user-api-key header)
    2. Fallback to server-side NVIDIA_API_KEY from environment
    
    Args:
        user_api_key: Optional API key provided by user via request header
        
    Raises:
        AIAssistError: If no valid API key is available
    """
    # Priority 1: User-provided API key
    api_key = (user_api_key or "").strip() or os.getenv("NVIDIA_API_KEY", "").strip()
    
    # Safe debug logging (never log full key)
    if user_api_key:
        logger.info("Using user-provided NVIDIA API key")
    else:
        logger.info("Using fallback server NVIDIA API key")
    
    if not api_key:
        raise AIAssistError("NVIDIA_API_KEY not configured. Please provide your API key.")
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
    user_api_key: Optional[str] = None,
) -> dict[str, Any]:
    """
    Generate AI assistance content based on the requested action.
    This is ISOLATED from execution — it only generates text advice.
    
    Args:
        user_api_key: Optional API key provided by user (from x-user-api-key header)
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
            f"{json.dumps(context, ensure_ascii=False, indent=2, default=str)[:5000]}\n"
            "```\n"
        )

    user_message = "\n".join(parts)

    client = _get_client(user_api_key=user_api_key)
    logger.info("AI assist request: action=%s, code_len=%d", action, len(user_code))

    # Determine token limit based on action (optimize for latency)
    max_tokens_map = {
        "chat": 300,
        "hint": 100,
        "explain_approach": 250,
        "optimize": 200,
        "find_bug": 200,
        "complexity_analysis": 150,
        "explain_solution": 300,
        "generate_testcases": 1500,
    }
    max_tokens = max_tokens_map.get(action, 300)

    try:
        response = client.chat.completions.create(
            model=NVIDIA_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.0,  # Deterministic, concise responses
            top_p=1.0,
            max_tokens=max_tokens,
        )
    except (AuthenticationError, RateLimitError, APIConnectionError, APIError) as exc:
        logger.error("AI assist LLM error: %s", exc)
        raise AIAssistError(f"AI service error: {type(exc).__name__}") from exc
    except Exception as exc:
        logger.exception("Unexpected AI assist failure")
        raise AIAssistError("Unexpected AI service failure.") from exc

    content = (response.choices[0].message.content if response.choices else "") or ""

    # Post-process response for quality
    import re
    
    # Strip thinking tags if model uses them
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    
    # Remove repetition (prevents loops like "The 0 is... The 0 is...")
    content = _remove_repeated_lines(content, max_repeats=1)
    
    # Truncate to sensible limits per action
    content = _truncate_response(content, action)
    
    # Final cleanup
    content = content.strip()

    return {
        "content": content,
        "action": action,
    }
