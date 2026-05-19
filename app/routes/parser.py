import logging

from fastapi import APIRouter, HTTPException, Header
from typing import Optional

from app.models.schemas import ProblemRequest
from app.services.llm_service import (
    LLMAuthenticationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMServiceError,
    parse_problem,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/parse-problem")
def parse_problem_route(
    request: ProblemRequest,
    x_user_api_key: Optional[str] = Header(None)
):
    """
    Parse a coding problem statement.
    
    Supports BYOK (Bring Your Own Key) via x-user-api-key header.
    If provided, user's API key takes priority over server-side key.
    """
    logger.info("Received /parse-problem request")
    try:
        result = parse_problem(request.problem_text, user_api_key=x_user_api_key)
    except LLMAuthenticationError as exc:
        logger.warning("LLM authentication error: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMRateLimitError as exc:
        logger.warning("LLM rate limit error: %s", exc)
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except LLMServiceError as exc:
        logger.warning("LLM parsing validation error: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMProviderError as exc:
        logger.error("LLM provider failure: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Failed to parse problem via upstream model provider.",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected parse route failure")
        raise HTTPException(
            status_code=502,
            detail="Failed to parse problem via upstream model provider.",
        ) from exc
    # ===================== DEBUG: PARSED TESTCASES =====================
    print("========== PARSED PROBLEM TESTCASES ==========")
    for tc in result.get("testcases", []):
        print(f"  TC {tc.get('id')}: stdin={repr(tc.get('stdin', ''))} expected={repr(tc.get('expected_output', ''))} hidden={tc.get('is_hidden')}")
    print("===============================================")
    # ================================================================

    return {"parsed_problem": result}
