"""
Pydantic data models shared by the orchestrator, agents, and the API layer.

These mirror (and are kept in sync with) the TypeScript types in
`src/lib/apiClient.ts` on the frontend.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class Language(str, Enum):
    PYTHON = "python"
    JAVA = "java"


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    SUCCESS = "success"


class Category(str, Enum):
    SYNTAX = "syntax"
    LOGIC = "logic"
    QUALITY = "quality"
    SECURITY = "security"
    PERFORMANCE = "performance"
    AI = "ai"


class Finding(BaseModel):
    """A single, structured issue reported by an agent."""

    id: str
    agent: str
    category: Category
    severity: Severity
    line: Optional[int] = None
    column: Optional[int] = None
    message: str
    explanation: Optional[str] = None
    suggestion: Optional[str] = None
    fixed_snippet: Optional[str] = None
    rule: Optional[str] = None
    source: str = "static-analysis"  # static-analysis | llm


class AgentResult(BaseModel):
    """Everything a single agent produced for one review run."""

    agent: str
    category: Category
    description: str
    findings: List[Finding] = Field(default_factory=list)
    execution_time_ms: float = 0.0
    tool: Optional[str] = None  # underlying tool/technique used, if any


class ReviewSummary(BaseModel):
    total_findings: int
    errors: int
    warnings: int
    info: int
    success: int
    score: int  # 0-100, higher is better
    verdict: str


class ReviewRequest(BaseModel):
    code: str
    language: Language
    filename: Optional[str] = None

    @field_validator("code")
    @classmethod
    def code_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("code must not be empty")
        return v


class ReviewResponse(BaseModel):
    language: Language
    findings: List[Finding]
    agents: List[AgentResult]
    summary: ReviewSummary
    documentation: str
    fixed_code: Optional[str] = None
    llm_enabled: bool
    analyzed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class HealthResponse(BaseModel):
    status: str
    version: str
    llm_enabled: bool
    llm_provider: Optional[str] = None
    supported_languages: List[Language]
    available_tools: dict


class SampleCode(BaseModel):
    id: str
    title: str
    language: Language
    description: str
    code: str


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
