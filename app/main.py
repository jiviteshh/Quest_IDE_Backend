"""
AI Coding Judge — Application Entry Point
==========================================
Registers all routers and configures the FastAPI application instance.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.health import router as health_router
from app.routes.parser import router as parser_router
from app.routes.judge import router as judge_router
from app.routes.ai import router as ai_router

# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title="AI Coding Judge API",
    description="Backend API for parsing coding problems and executing code.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------
app.include_router(health_router)
app.include_router(parser_router)
app.include_router(judge_router)
app.include_router(ai_router)


@app.get("/", tags=["Root"])
def root():
    return {"message": "AI Coding Judge Backend Running"}
