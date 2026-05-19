"""
AI Assistant Route
────────────────────────────────────────────────────────────────
COMPLETELY SEPARATE from /judge/* and /parse-problem routes.
Does NOT affect execution flow or testcase contracts.
Supports BYOK (Bring Your Own Key) via x-user-api-key header.
────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from app.services.ai_service import AIAssistError, get_ai_assistance

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["AI Assistant"])


class AIAssistRequest(BaseModel):
    action: str
    query: Optional[str] = None
    problem_description: str
    user_code: str = ""
    language: str = "python"
    failed_testcase: Optional[dict[str, str]] = None
    last_verdict: Optional[str] = None
    context: Optional[dict] = None


class AIAssistResponse(BaseModel):
    content: str
    action: str
    error: Optional[str] = None


@router.post(
    "/assist",
    response_model=AIAssistResponse,
    summary="Get AI assistance (isolated from execution)",
    description=(
        "Provides AI-powered hints, explanations, bug finding, and complexity "
        "analysis. This endpoint is completely isolated from code execution. "
        "Supports BYOK via x-user-api-key header."
    ),
)
async def ai_assist(
    request: AIAssistRequest,
    x_user_api_key: Optional[str] = Header(None)
) -> AIAssistResponse:
    """
    AI assistance endpoint.
    
    Supports BYOK (Bring Your Own Key) via x-user-api-key header.
    If provided, user's API key takes priority over server-side key.
    """
    # Safe debug logging
    if x_user_api_key:
        logger.info("Received x-user-api-key header - using user-provided API key")
    else:
        logger.info("No x-user-api-key header - will use fallback server key")
    
    try:
        result = get_ai_assistance(
            action=request.action,
            query=request.query,
            problem_description=request.problem_description,
            user_code=request.user_code,
            language=request.language,
            failed_testcase=request.failed_testcase,
            last_verdict=request.last_verdict,
            context=request.context,
            user_api_key=x_user_api_key,
        )
        return AIAssistResponse(**result)
    except AIAssistError as exc:
        logger.warning("AI assist error: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected AI assist error")
        raise HTTPException(
            status_code=500,
            detail="AI service encountered an unexpected error.",
        ) from exc
