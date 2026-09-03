"""
Base class for all review agents.

Each concrete agent is responsible for exactly one concern (syntax, logic,
quality, security, performance). Agents are intentionally "dumb wrappers"
around the language analyzers: they select the findings that belong to
their category, attach agent metadata, and time their own execution. This
keeps agents trivially swappable/testable/replaceable, per the assignment's
"clean modular architecture" requirement — you can add a new agent by
subclassing `BaseAgent` without touching the orchestrator or the analyzers.
"""
from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from app.models import AgentResult, Category, Finding


class BaseAgent(ABC):
    name: str = "Base Agent"
    category: Category = Category.QUALITY
    description: str = ""

    @abstractmethod
    def _select(self, all_findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return the subset of raw findings this agent owns."""
        raise NotImplementedError

    def run(self, all_findings: List[Dict[str, Any]]) -> AgentResult:
        start = time.perf_counter()
        raw = self._select(all_findings)
        findings: List[Finding] = []
        for item in raw:
            findings.append(
                Finding(
                    id=str(uuid.uuid4()),
                    agent=self.name,
                    category=item.get("category", self.category),
                    severity=item["severity"],
                    line=item.get("line"),
                    column=item.get("column"),
                    message=item["message"],
                    explanation=item.get("explanation"),
                    suggestion=item.get("suggestion"),
                    fixed_snippet=item.get("code_snippet") or item.get("fixed_snippet"),
                    rule=item.get("rule"),
                    source=item.get("source", "static-analysis"),
                )
            )
        elapsed_ms = (time.perf_counter() - start) * 1000
        return AgentResult(
            agent=self.name,
            category=self.category,
            description=self.description,
            findings=findings,
            execution_time_ms=round(elapsed_ms, 3),
            tool=self._tool_summary(raw),
        )

    @staticmethod
    def _tool_summary(raw: List[Dict[str, Any]]) -> str:
        tools = sorted({item.get("tool") for item in raw if item.get("tool")})
        return ", ".join(tools) if tools else "built-in analyzer"
