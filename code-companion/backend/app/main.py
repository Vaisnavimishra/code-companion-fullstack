"""
FastAPI application entrypoint for the CodeAgent multi-agent review API.

Run locally with:
    uvicorn app.main:app --reload --port 8000

or simply:
    python run.py
"""
from __future__ import annotations

import logging
import shutil
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.models import (
    ErrorResponse,
    HealthResponse,
    Language,
    ReviewRequest,
    ReviewResponse,
    SampleCode,
)
from app.orchestrator import orchestrator
from app.samples import SAMPLES
from app.services.llm_service import llm_service

logging.basicConfig(level=logging.INFO if not settings.debug else logging.DEBUG)
logger = logging.getLogger("codeagent")

app = FastAPI(
    title=settings.app_name,
    description=(
        "Real, multi-agent static code review API. Submits Python or Java "
        "source code through specialized Syntax, Logic, Quality, Security, "
        "and Performance agents (plus an optional LLM agent) and returns a "
        "structured, deduplicated review with an overall score."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time-Ms"] = str(round((time.perf_counter() - start) * 1000, 2))
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error while processing %s %s", request.method, request.url)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="internal_server_error",
            detail="Something went wrong while processing your request. Please try again.",
        ).model_dump(),
    )


@app.get("/api/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    """Health check + capability report (which optional tools are active)."""
    available_tools = {
        "javac": shutil.which("javac") is not None,
        "pyflakes": shutil.which("pyflakes") is not None or _module_available("pyflakes"),
        "bandit": shutil.which("bandit") is not None,
        "radon": shutil.which("radon") is not None,
        "llm": llm_service.enabled,
    }
    return HealthResponse(
        status="ok",
        version="1.0.0",
        llm_enabled=llm_service.enabled,
        llm_provider=llm_service.provider if llm_service.enabled else None,
        supported_languages=[Language.PYTHON, Language.JAVA],
        available_tools=available_tools,
    )


@app.get("/api/languages", tags=["meta"])
async def languages() -> dict:
    return {"languages": [lang.value for lang in [Language.PYTHON, Language.JAVA]]}


@app.get("/api/samples", response_model=list[SampleCode], tags=["samples"])
async def get_samples() -> list[SampleCode]:
    """Sample code inputs — handy for quickly testing the pipeline end-to-end."""
    return SAMPLES


@app.post("/api/review", response_model=ReviewResponse, tags=["review"])
async def review_code(payload: ReviewRequest) -> ReviewResponse:
    """
    Run the full multi-agent review pipeline over submitted source code.

    This is the single endpoint the frontend calls when the user clicks
    "Analyze". It performs real static analysis (no mocked/random data);
    see README.md for the full list of checks per language.
    """
    if len(payload.code) > settings.max_code_length:
        raise HTTPException(
            status_code=413,
            detail=f"Code exceeds the maximum allowed length of {settings.max_code_length} characters.",
        )

    try:
        return await orchestrator.review(payload.code, payload.language)
    except Exception as exc:  # analyzers should not raise, but never trust that blindly
        logger.exception("Review pipeline failed")
        raise HTTPException(status_code=500, detail=f"Review failed: {exc}") from exc


def _module_available(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


@app.get("/", tags=["meta"])
async def root() -> dict:
    return {
        "name": settings.app_name,
        "docs": "/docs",
        "health": "/api/health",
    }
