# c:\Users\jivin\Documents\AI CODING\Backend\app\models\schemas.py
"""Pydantic schemas for parser and judge routes."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class ProblemRequest(BaseModel):
    """Request body for problem parsing."""

    problem_text: str = Field(
        ...,
        min_length=10,
        description="Raw coding problem text to parse.",
        examples=["Given an array of integers, return indices of two numbers that add up to target."],
    )


class CodeExecutionRequest(BaseModel):
    """Request body for code execution."""

    source_code: str = Field(
        ...,
        min_length=1,
        description="Source code to execute.",
        examples=["print('Hello, World!')"],
    )
    language_id: int = Field(
        ...,
        description="Execution language id (71=Python, 62=Java, 54=C++).",
        examples=[71, 62, 54],
    )
    stdin: Optional[str] = Field(
        default="",
        description="Optional stdin passed to the program.",
        examples=[""],
    )


class CodeExecutionResponse(BaseModel):
    """Normalized execution response independent of provider."""

    stdout: str = Field(default="", description="Program standard output.")
    stderr: str = Field(default="", description="Program standard error.")
    compile_output: str = Field(default="", description="Compilation-stage output when available.")
    exit_code: Optional[int] = Field(default=None, description="Program exit code.")
    time: Optional[str] = Field(default=None, description="Execution time in milliseconds.")
    memory: Optional[int] = Field(default=None, description="Memory usage in bytes.")
    status: Optional[dict[str, str]] = Field(
        default=None,
        description="Provider status metadata.",
    )
    language: str = Field(default="", description="Language used for execution.")
    version: str = Field(default="", description="Language version used for execution.")


class ErrorResponse(BaseModel):
    """Standard error response envelope."""

    detail: str = Field(..., description="Error message.")


class Testcase(BaseModel):
    """Single testcase used for submission evaluation."""

    id: Optional[int] = Field(default=None, ge=1, description="Optional testcase id.")
    display_input: Optional[str] = Field(default="", description="Display input for UI.")
    display_output: Optional[str] = Field(default="", description="Display output for UI.")
    stdin: str = Field(
        default="",
        description="stdin payload for this testcase.",
        examples=["2 3"],
    )
    expected_output: str = Field(
        ...,
        description="Expected stdout for this testcase.",
        examples=["5"],
    )
    is_hidden: bool = Field(
        default=False,
        description="Whether testcase is hidden from users.",
    )

    @field_validator("expected_output")
    @classmethod
    def validate_expected_output(cls, value: str) -> str:
        if value is None:
            raise ValueError("expected_output must be provided.")
        return value

    @field_validator("stdin")
    @classmethod
    def validate_stdin(cls, value: str) -> str:
        return value if value is not None else ""


class SubmissionRequest(BaseModel):
    """Request body for multi-testcase submission evaluation."""

    source_code: str = Field(
        ...,
        min_length=1,
        description="User source code to evaluate.",
    )
    language_id: int = Field(
        ...,
        description="Execution language id (71=Python, 62=Java, 54=C++).",
    )
    testcases: list[Testcase] = Field(
        ...,
        min_length=1,
        description="List of public/hidden testcases for evaluation.",
    )

    @field_validator("source_code")
    @classmethod
    def validate_source_code(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("source_code must not be empty.")
        return value


class TestcaseResult(BaseModel):
    """Result for a single testcase execution."""

    testcase: int = Field(..., ge=1, description="1-based testcase index.")
    status: Literal["Passed", "Failed", "Skipped"] = Field(
        ...,
        description="Per-testcase evaluation status.",
    )
    stdout: str = Field(default="", description="Captured stdout.")
    stderr: str = Field(default="", description="Captured stderr.")
    expected_output: Optional[str] = Field(
        default=None,
        description="Expected output. Hidden testcases can omit this.",
    )
    is_hidden: bool = Field(default=False, description="Whether testcase is hidden.")
    execution_time_ms: Optional[int] = Field(
        default=None,
        description="Execution time in milliseconds when available.",
    )
    memory_kb: Optional[int] = Field(
        default=None,
        description="Memory usage in KB when available.",
    )


class SubmissionResponse(BaseModel):
    """Aggregated submission verdict and testcase results."""

    verdict: Literal[
        "Accepted",
        "Wrong Answer",
        "Runtime Error",
        "Compilation Error",
        "Time Limit Exceeded",
        "Internal Error",
    ] = Field(..., description="Final verdict for the submission.")
    passed_testcases: int = Field(..., ge=0, description="Number of passed testcases.")
    total_testcases: int = Field(..., ge=1, description="Total number of testcases.")
    results: list[TestcaseResult] = Field(..., description="Per-testcase results.")
    language: str = Field(default="", description="Execution language used.")
    version: str = Field(default="", description="Execution language version used.")
