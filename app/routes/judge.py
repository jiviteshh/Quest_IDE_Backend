# c:\Users\jivin\Documents\AI CODING\Backend\app\routes\judge.py
"""Judge routes for code execution, run-against-visible, and full submission."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.models.schemas import (
    CodeExecutionRequest,
    CodeExecutionResponse,
    ErrorResponse,
    SubmissionRequest,
    SubmissionResponse,
)
from app.services.evaluation_service import evaluate_submission
from app.services.judge_service import (
    ExecutionServiceError,
    UnsupportedLanguageError,
    UpstreamResponseError,
    UpstreamTimeoutError,
    get_supported_languages,
    run_code,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/judge", tags=["Code Execution"])


# ---------------------------------------------------------------------------
# POST /judge/run-code — raw single execution (custom input)
# ---------------------------------------------------------------------------
@router.post(
    "/run-code",
    response_model=CodeExecutionResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request or unsupported language"},
        502: {"model": ErrorResponse, "description": "Execution provider failure"},
        504: {"model": ErrorResponse, "description": "Execution provider timeout"},
    },
    summary="Execute source code with custom stdin",
    description="Run code through the configured execution provider and return normalized output.",
)
async def execute_code(request: CodeExecutionRequest) -> CodeExecutionResponse:
    try:
        result: dict[str, Any] = await run_code(
            source_code=request.source_code,
            language_id=request.language_id,
            stdin=request.stdin,
        )
        return CodeExecutionResponse(**result)
    except UnsupportedLanguageError as exc:
        logger.warning("Unsupported language request: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except UpstreamTimeoutError as exc:
        logger.error("Execution provider timeout: %s", exc)
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc)) from exc
    except UpstreamResponseError as exc:
        logger.error("Invalid provider response: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except ExecutionServiceError as exc:
        logger.error("Execution provider failure: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error in /judge/run-code")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected server error during code execution.",
        ) from exc


# ---------------------------------------------------------------------------
# GET /judge/supported-languages
# ---------------------------------------------------------------------------
@router.get(
    "/supported-languages",
    status_code=status.HTTP_200_OK,
    summary="Get supported languages",
    description="Return currently configured language-id mapping.",
)
async def supported_languages() -> dict[str, dict[int, dict[str, str]]]:
    return {"languages": get_supported_languages()}


# ---------------------------------------------------------------------------
# POST /judge/submit — evaluate against ALL testcases (visible + hidden)
# ---------------------------------------------------------------------------
@router.post(
    "/submit",
    response_model=SubmissionResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request or unsupported language"},
        502: {"model": ErrorResponse, "description": "Execution provider failure"},
        504: {"model": ErrorResponse, "description": "Execution provider timeout"},
    },
    summary="Evaluate submission against all testcases",
    description=(
        "Execute source code against a list of public/hidden testcases, "
        "compare outputs, and return a structured final verdict."
    ),
)
async def submit_code(request: SubmissionRequest) -> SubmissionResponse:
    try:
        return await evaluate_submission(
            source_code=request.source_code,
            language_id=request.language_id,
            testcases=request.testcases,
        )
    except UnsupportedLanguageError as exc:
        logger.warning("Unsupported language in /judge/submit: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except UpstreamTimeoutError as exc:
        logger.error("Execution timeout in /judge/submit: %s", exc)
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc)) from exc
    except UpstreamResponseError as exc:
        logger.error("Invalid provider response in /judge/submit: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except ExecutionServiceError as exc:
        logger.error("Execution provider failure in /judge/submit: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error in /judge/submit")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected server error during submission evaluation.",
        ) from exc
