"""
AI Coding Judge — Application Entry Point
==========================================
Registers all routers and configures the FastAPI application instance.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.health import router as health_router
from app.routes.parser import router as parser_router
from app.routes.judge import router as judge_router
from app.routes.ai import router as ai_router

# ---------------------------------------------------------------------------
# CORS Configuration
# ---------------------------------------------------------------------------
# Parse allowed origins from environment variable or use defaults
ALLOWED_ORIGINS_ENV = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000,https://quest-ide-frontend.vercel.app,https://quest-ide-frontend-git-main-jivinaragam-2921s-projects.vercel.app,https://paddle-comma-omnivore.ngrok-free.dev",
)
ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS_ENV.split(",")]

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
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],  # This already includes custom headers like x-user-api-key
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
