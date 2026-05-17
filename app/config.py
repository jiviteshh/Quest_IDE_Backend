# c:\Users\jivin\Documents\AI CODING\Backend\app\config.py
"""Application configuration for execution providers and constants."""

from __future__ import annotations

import os

# Provider endpoint and auth
PISTON_URL = os.getenv("PISTON_URL", "http://localhost:2000/api/v2/execute")
PISTON_API_KEY = os.getenv("PISTON_API_KEY", "")

# Upstream execution timeout in seconds
EXECUTION_TIMEOUT_SECONDS = 15

# LLM provider settings (provider-agnostic service layer)
NVIDIA_API_BASE_URL = os.getenv("NVIDIA_API_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "qwen/qwen3-coder-480b-a35b-instruct")
NVIDIA_TEMPERATURE = float(os.getenv("NVIDIA_TEMPERATURE", "0"))
NVIDIA_TOP_P = float(os.getenv("NVIDIA_TOP_P", "1"))
NVIDIA_MAX_TOKENS = int(os.getenv("NVIDIA_MAX_TOKENS", "4096"))
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "90"))

# Language mapping kept provider-agnostic by using internal language IDs.
# These IDs match common Judge0 ids, which eases future migration.
LANGUAGE_MAP: dict[int, dict[str, str]] = {
    71: {"language": "python", "version": "3.10.0"},
    62: {"language": "java", "version": "15.0.2"},
    54: {"language": "cpp", "version": "10.2.0"},
}
