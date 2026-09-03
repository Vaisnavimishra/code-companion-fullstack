"""
Central application configuration.

All configuration is sourced from environment variables (optionally loaded
from a local .env file via python-dotenv). Nothing sensitive is ever
hardcoded here — see .env.example for the full list of supported variables.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List

try:
    # Loads a local .env file into os.environ if python-dotenv is installed
    # and a .env file is present. This is optional — the app works fine
    # with real environment variables too (e.g. in Docker/production).
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - dotenv is a light optional dep
    pass


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _get_list(name: str, default: List[str]) -> List[str]:
    val = os.getenv(name)
    if not val:
        return default
    return [item.strip() for item in val.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    # --- Server ---
    app_name: str = "CodeAgent Multi-Agent Review API"
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    debug: bool = _get_bool("DEBUG", True)

    # --- CORS ---
    cors_origins: List[str] = field(
        default_factory=lambda: _get_list(
            "CORS_ORIGINS",
            [
                "http://localhost:8080",
                "http://127.0.0.1:8080",
                "http://localhost:5173",
                "http://127.0.0.1:5173",
            ],
        )
    )

    # --- LLM provider (optional) ---
    # If no provider/key is configured, the app runs purely on static
    # analysis, which remains fully functional on its own.
    llm_provider: str = os.getenv("LLM_PROVIDER", "").strip().lower()  # "anthropic" | "openai" | ""
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    llm_model: str = os.getenv(
        "LLM_MODEL",
        "claude-sonnet-4-6" if os.getenv("LLM_PROVIDER", "").lower() == "anthropic" else "gpt-4o-mini",
    )
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "20"))

    # --- Analysis behaviour ---
    max_code_length: int = int(os.getenv("MAX_CODE_LENGTH", "100000"))
    external_tools_timeout: float = float(os.getenv("EXTERNAL_TOOLS_TIMEOUT", "8"))

    @property
    def llm_enabled(self) -> bool:
        if self.llm_provider == "anthropic":
            return bool(self.anthropic_api_key)
        if self.llm_provider == "openai":
            return bool(self.openai_api_key)
        return False


settings = Settings()
