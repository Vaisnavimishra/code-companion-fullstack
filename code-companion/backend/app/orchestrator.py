"""
The Review Orchestrator (aka Review Manager).

Responsibilities (per the assignment spec):
  1. Receive submitted code.
  2. Run it through the appropriate language analyzer to produce raw,
     structured findings.
  3. Dispatch findings to the appropriate specialized agent by category.
  4. Optionally enrich with an LLM-based agent.
  5. Deduplicate findings.
  6. Compute an overall review summary/score.
  7. Return a single structured response for the API layer.

The orchestrator never contains language-specific analysis logic itself —
that lives in `app/analyzers/*` — which keeps this module small and makes
it trivial to add a new language (register an analyzer) or a new agent
(add to `ALL_AGENTS`) without touching this file's core flow.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List

from app.agents import ALL_AGENTS
from app.analyzers import java_analyzer, python_analyzer
from app.models import Language, ReviewResponse, ReviewSummary
from app.services.llm_service import llm_service

_ANALYZERS = {
    Language.PYTHON: python_analyzer,
    Language.JAVA: java_analyzer,
}


def _dedupe(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove exact duplicate findings (same category/line/message) that can
    occur when multiple checks — or a fallback tool plus the primary
    analyzer — legitimately flag the same underlying issue."""
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for f in findings:
        key = (f.get("category"), f.get("line"), f.get("message"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(f)
    return deduped


def _compute_summary(findings: List[Dict[str, Any]]) -> ReviewSummary:
    errors = sum(1 for f in findings if f.get("severity") == "error")
    warnings = sum(1 for f in findings if f.get("severity") == "warning")
    info = sum(1 for f in findings if f.get("severity") == "info")
    success = sum(1 for f in findings if f.get("severity") == "success")

    # Score starts at 100 and is penalized by severity. Floors at 0.
    score = 100 - (errors * 15) - (warnings * 5) - (info * 1)
    score = max(0, min(100, score))

    if errors > 0:
        verdict = "Needs work — blocking issues found"
    elif warnings > 3:
        verdict = "Needs attention — several warnings found"
    elif warnings > 0:
        verdict = "Mostly good — minor warnings found"
    else:
        verdict = "Looks good — no significant issues found"

    return ReviewSummary(
        total_findings=len(findings),
        errors=errors,
        warnings=warnings,
        info=info,
        success=success,
        score=score,
        verdict=verdict,
    )


class ReviewOrchestrator:
    """Coordinates analyzers + agents into one structured review."""

    async def review(self, code: str, language: Language) -> ReviewResponse:
        analyzer = _ANALYZERS[language]

        raw_findings = analyzer.analyze(code)

        # If the code doesn't even parse/compile, we still return a full,
        # well-formed response — just with a single, very clear syntax
        # finding and everything else empty (there's nothing meaningful to
        # say about logic/quality/security of code that doesn't parse).
        has_blocking_syntax_error = any(
            f.get("category") == "syntax" and f.get("severity") == "error" for f in raw_findings
        )

        llm_findings: List[Dict[str, Any]] = []
        if not has_blocking_syntax_error and llm_service.enabled:
            llm_findings = await llm_service.review(code, language.value)

        all_findings = _dedupe(raw_findings + llm_findings)

        agent_results = [agent.run(all_findings) for agent in ALL_AGENTS]

        summary = _compute_summary(all_findings)

        if has_blocking_syntax_error:
            documentation = "Documentation analysis skipped: fix the syntax error first."
            fixed_code = None
        else:
            documentation = analyzer.build_documentation_notes(code)
            fixed_code = analyzer.generate_fixed_code(code, all_findings)

        all_finding_models = [f for ar in agent_results for f in ar.findings]

        return ReviewResponse(
            language=language,
            findings=all_finding_models,
            agents=agent_results,
            summary=summary,
            documentation=documentation,
            fixed_code=fixed_code,
            llm_enabled=llm_service.enabled,
        )


orchestrator = ReviewOrchestrator()
