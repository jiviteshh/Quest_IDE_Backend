"""Submission evaluation pipeline for multi-testcase judging."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from app.models.schemas import SubmissionResponse, Testcase, TestcaseResult
from app.services.judge_service import (
    ExecutionServiceError,
    UnsupportedLanguageError,
    UpstreamResponseError,
    UpstreamTimeoutError,
    run_code,
)
from app.utils.helpers import compare_outputs

logger = logging.getLogger(__name__)

Verdict = Literal[
    "Accepted",
    "Wrong Answer",
    "Runtime Error",
    "Compilation Error",
    "Time Limit Exceeded",
    "Internal Error",
]


@dataclass(frozen=True)
class ExecutionClassification:
    """Derived execution status used for verdict generation."""

    verdict: Verdict
    is_terminal: bool


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def _classify_failed_execution(stderr: str) -> ExecutionClassification:
    """
    Best-effort provider-independent error classification.
    """
    if _contains_any(stderr, ("time limit", "timed out", "timeout")):
        return ExecutionClassification(verdict="Time Limit Exceeded", is_terminal=True)

    if _contains_any(
        stderr,
        (
            "compilation",
            "compile error",
            "syntaxerror",
            "javac",
            "cannot find symbol",
            "error:",
            "g++",
            "ld:",
            "undefined reference",
        ),
    ):
        return ExecutionClassification(verdict="Compilation Error", is_terminal=True)

    return ExecutionClassification(verdict="Runtime Error", is_terminal=True)


async def evaluate_submission(
    source_code: str,
    language_id: int,
    testcases: list[Testcase],
) -> SubmissionResponse:
    """
    Evaluate a submission against a testcase set.

    Execution stops early for compilation/runtime/time-limit/internal errors.
    """
    logger.info(
        "Submission received: language_id=%s total_testcases=%s",
        language_id,
        len(testcases),
    )

    results: list[TestcaseResult] = []
    passed_count = 0
    final_verdict: Verdict = "Accepted"
    language = ""
    version = ""

    for index, testcase in enumerate(testcases, start=1):
        # ===================== DEBUG: TESTCASE DATA =====================
        print(f">>>>>> TESTCASE {index}/{len(testcases)} >>>>>>")
        print(f"  stdin (repr): {repr(testcase.stdin)}")
        print(f"  stdin length: {len(testcase.stdin)}")
        print(f"  expected_output: {repr(testcase.expected_output)}")
        print(f"  is_hidden: {testcase.is_hidden}")
        print(f"<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
        # ================================================================
        try:
            execution = await run_code(
                source_code=source_code,
                language_id=language_id,
                stdin=testcase.stdin,
            )
        except UnsupportedLanguageError:
            logger.warning("Unsupported language during submission evaluation: %s", language_id)
            raise
        except UpstreamTimeoutError as exc:
            logger.error("Execution timeout on testcase=%s: %s", index, exc)
            final_verdict = "Time Limit Exceeded"
            results.append(
                TestcaseResult(
                    testcase=index,
                    status="Failed",
                    stdout="",
                    stderr=str(exc),
                    expected_output=None if testcase.is_hidden else testcase.expected_output,
                    is_hidden=testcase.is_hidden,
                )
            )
            break
        except (UpstreamResponseError, ExecutionServiceError) as exc:
            logger.error("Execution provider failure on testcase=%s: %s", index, exc)
            final_verdict = "Internal Error"
            results.append(
                TestcaseResult(
                    testcase=index,
                    status="Failed",
                    stdout="",
                    stderr=str(exc),
                    expected_output=None if testcase.is_hidden else testcase.expected_output,
                    is_hidden=testcase.is_hidden,
                )
            )
            break

        language = execution.get("language", language)
        version = execution.get("version", version)
        stdout = str(execution.get("stdout", ""))
        stderr = str(execution.get("stderr", ""))
        exit_code = execution.get("exit_code")

        if exit_code not in (None, 0) or stderr.strip():
            classification = _classify_failed_execution(stderr)
            final_verdict = classification.verdict
            logger.info(
                "Terminal execution verdict=%s testcase=%s exit_code=%s",
                final_verdict,
                index,
                exit_code,
            )
            results.append(
                TestcaseResult(
                    testcase=index,
                    status="Failed",
                    stdout=stdout,
                    stderr=stderr,
                    expected_output=None if testcase.is_hidden else testcase.expected_output,
                    is_hidden=testcase.is_hidden,
                )
            )
            if classification.is_terminal:
                break
            continue

        is_match = compare_outputs(stdout, testcase.expected_output)
        if is_match:
            passed_count += 1
            results.append(
                TestcaseResult(
                    testcase=index,
                    status="Passed",
                    stdout=stdout,
                    stderr=stderr,
                    expected_output=None if testcase.is_hidden else testcase.expected_output,
                    is_hidden=testcase.is_hidden,
                )
            )
        else:
            final_verdict = "Wrong Answer"
            logger.info("Wrong answer on testcase=%s", index)
            results.append(
                TestcaseResult(
                    testcase=index,
                    status="Failed",
                    stdout=stdout,
                    stderr=stderr,
                    expected_output=None if testcase.is_hidden else testcase.expected_output,
                    is_hidden=testcase.is_hidden,
                )
            )

    total = len(testcases)

    if final_verdict == "Accepted" and passed_count != total:
        # Safety net for partially evaluated/failed flows.
        final_verdict = "Wrong Answer"

    logger.info(
        "Submission evaluated verdict=%s passed=%s total=%s",
        final_verdict,
        passed_count,
        total,
    )

    return SubmissionResponse(
        verdict=final_verdict,
        passed_testcases=passed_count,
        total_testcases=total,
        results=results,
        language=language,
        version=version,
    )
