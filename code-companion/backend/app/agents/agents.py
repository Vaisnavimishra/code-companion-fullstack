"""Concrete, single-responsibility review agents."""
from __future__ import annotations

from typing import Any, Dict, List

from app.agents.base import BaseAgent
from app.models import Category


class SyntaxAgent(BaseAgent):
    name = "Syntax & Compilation Agent"
    category = Category.SYNTAX
    description = (
        "Verifies the code actually parses/compiles. Uses CPython's own "
        "compiler for Python and (when a JDK is available) the real `javac` "
        "compiler for Java, falling back to structural checks otherwise."
    )

    def _select(self, all_findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [f for f in all_findings if f.get("category") == "syntax"]


class LogicAgent(BaseAgent):
    name = "Logic & Bug Detection Agent"
    category = Category.LOGIC
    description = (
        "Looks for genuine runtime-bug patterns: bare/broad exception "
        "handling, mutable default arguments, reference-vs-value comparison "
        "bugs, unterminated loops, unreachable/duplicated logic, and more."
    )

    def _select(self, all_findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [f for f in all_findings if f.get("category") == "logic"]


class QualityAgent(BaseAgent):
    name = "Code Quality Agent"
    category = Category.QUALITY
    description = (
        "Flags readability and maintainability issues: missing "
        "documentation, overly long/complex functions, unused imports, "
        "style inconsistencies, and TODO/FIXME markers."
    )

    def _select(self, all_findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [f for f in all_findings if f.get("category") == "quality"]


class SecurityAgent(BaseAgent):
    name = "Security Agent"
    category = Category.SECURITY
    description = (
        "Scans for common vulnerability classes: injection (SQL/command), "
        "unsafe deserialization, hardcoded secrets, weak cryptography, and "
        "insecure use of eval/exec/reflection."
    )

    def _select(self, all_findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [f for f in all_findings if f.get("category") == "security"]


class PerformanceAgent(BaseAgent):
    name = "Performance Agent"
    category = Category.PERFORMANCE
    description = (
        "Detects algorithmic inefficiencies: nested loops with quadratic "
        "behavior, unmemoized recursion, and string concatenation in loops."
    )

    def _select(self, all_findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [f for f in all_findings if f.get("category") == "performance"]


ALL_AGENTS = [
    SyntaxAgent(),
    LogicAgent(),
    QualityAgent(),
    SecurityAgent(),
    PerformanceAgent(),
]
